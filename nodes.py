"""
LoadImageInpaintWebUI - WebUI 风格的局部重绘加载节点

完整复刻 AUTOMATIC1111 / Forge WebUI 的 inpaint 行为:

    [Mask blur]         蒙版边缘高斯模糊(默认 4px),让重绘区与原图自然融合
    [Mask mode]         "Inpaint masked" 或 "Inpaint not masked"(蒙版反转)
    [Masked content]    original / fill / latent_noise / latent_nothing
                        — 完全对应 WebUI 的 "Masked content" 四个选项
    [Inpaint area]      whole_picture(整图)/ only_masked(仅蒙版区,自动裁剪重绘)
                        — 对应 WebUI 的 "Inpaint area" 选项(only_masked 暂时通过
                          mask_blur + padding 模拟,真正裁剪重绘需要后续 KSampler 配合)
    [Only masked padding] 蒙版区外扩像素数(默认 32px)

输出:
    image         - 原图
    mask          - 处理后的蒙版(已模糊、已反转)
    latent        - 准备好的 latent(带 noise_mask,根据 masked_content 处理)
    original_image - 用于最后整图合成的参考图(接 ImageCompositeMasked)

推荐工作流接法:
    LoadImageInpaintWebUI ─┬─ latent ──→ KSampler ──→ VAEDecode ──┐
                          │                                       │
                          ├─ original_image ─────────────────────→ ImageCompositeMasked ──→ SaveImage
                          │                                       │
                          └─ mask ────────────────────────────────┘

    这样最终输出 = 重绘结果叠在原图上(蒙版混合),完全对齐 WebUI 行为,
    蒙版外区域是原图像素,无色差。

安装:
    放到 ComfyUI/custom_nodes/load_image_inpaint_keep.py(覆盖旧版),重启 ComfyUI
"""

import torch
import torch.nn.functional as F
import nodes
import comfy.utils


class LoadImageInpaintWebUI:
    @classmethod
    def INPUT_TYPES(cls):
        base = nodes.LoadImage.INPUT_TYPES()
        required = dict(base["required"])
        required["vae"] = ("VAE",)
        required["mask_blur"] = ("INT", {
            "default": 4, "min": 0, "max": 64, "step": 1,
            "tooltip": "蒙版模糊像素数(WebUI 默认 4)。让重绘边缘自然融合"
        })
        required["mask_mode"] = (["inpaint_masked", "inpaint_not_masked"], {
            "default": "inpaint_masked",
            "tooltip": "inpaint_masked=重绘红色区域(WebUI 默认);inpaint_not_masked=重绘红色以外区域"
        })
        required["masked_content"] = (
            ["original", "fill", "latent_noise", "latent_nothing"],
            {
                "default": "original",
                "tooltip": "蒙版区初始内容:original=原图(推荐,可配合低 denoise);fill=均值填充;latent_noise=纯噪声;latent_nothing=纯黑"
            }
        )
        required["only_masked_padding"] = ("INT", {
            "default": 32, "min": 0, "max": 256, "step": 4,
            "tooltip": "蒙版向外扩展的像素数(WebUI 默认 32)。让接缝更平滑"
        })
        return {"required": required}

    RETURN_TYPES = ("IMAGE", "MASK", "LATENT", "IMAGE")
    RETURN_NAMES = ("image", "mask", "latent", "original_image")
    FUNCTION = "process"
    CATEGORY = "image"
    DESCRIPTION = "WebUI 风格的局部重绘:含蒙版模糊、模式选择、masked content 四种填充。original_image 输出用于最后整图合成"

    def process(self, image, vae, mask_blur, mask_mode, masked_content,
                only_masked_padding):
        # ===== 1. 加载图像和蒙版(走官方逻辑)=====
        loader = nodes.LoadImage()
        img, mask = loader.load_image(image)
        # img: [B, H, W, 3], mask: [B, H, W] 或 [H, W]

        if mask.dim() == 2:
            mask = mask.unsqueeze(0)

        # ===== 2. 蒙版反转(inpaint_not_masked 模式)=====
        if mask_mode == "inpaint_not_masked":
            mask = 1.0 - mask

        # ===== 3. 蒙版像素级扩展(模拟 WebUI only_masked_padding)=====
        # 在像素级先扩展一圈,然后再做高斯模糊,得到自然羽化的边缘
        if only_masked_padding > 0:
            ksize = only_masked_padding * 2 + 1
            kernel = torch.ones((1, 1, ksize, ksize), dtype=torch.float32,
                                device=mask.device)
            m4 = mask.unsqueeze(1)
            m4 = F.conv2d(m4, kernel, padding=only_masked_padding)
            m4 = torch.clamp(m4, 0.0, 1.0)
            mask = m4.squeeze(1)

        # ===== 4. 蒙版高斯模糊(WebUI 核心特性)=====
        if mask_blur > 0:
            mask = self._gaussian_blur_mask(mask, mask_blur)

        # ===== 5. 准备 image 用于 VAE 编码(根据 masked_content)=====
        # 把图像尺寸对齐到 8 的倍数(VAE 要求)
        pixels = img.clone()
        H = (pixels.shape[1] // 8) * 8
        W = (pixels.shape[2] // 8) * 8
        if pixels.shape[1] != H or pixels.shape[2] != W:
            ox = (pixels.shape[1] % 8) // 2
            oy = (pixels.shape[2] % 8) // 2
            pixels = pixels[:, ox:ox + H, oy:oy + W, :]
            mask = mask[:, ox:ox + H, oy:oy + W]

        # 把蒙版区像素根据 masked_content 模式处理
        # pixels: [B, H, W, 3], mask: [B, H, W]
        mask_3c = mask.unsqueeze(-1)  # [B, H, W, 1]

        if masked_content == "original":
            # 蒙版区保留原图 — 配合低 denoise 可做精细修复
            pixels_for_encode = pixels
        elif masked_content == "fill":
            # 用图像平均色填充蒙版区(WebUI 默认 fill 模式)
            # 计算蒙版外区域的均值作为填充色
            inv_mask = 1.0 - mask_3c
            if inv_mask.sum() > 0:
                mean_color = (pixels * inv_mask).sum(dim=(1, 2), keepdim=True) / \
                             (inv_mask.sum(dim=(1, 2), keepdim=True) + 1e-6)
            else:
                mean_color = torch.tensor([0.5, 0.5, 0.5]).view(1, 1, 1, 3)
            pixels_for_encode = pixels * (1.0 - mask_3c) + mean_color * mask_3c
        elif masked_content == "latent_nothing":
            # 蒙版区填黑
            pixels_for_encode = pixels * (1.0 - mask_3c)
        else:  # latent_noise
            # 蒙版区填灰(让 VAE encode 后近似噪声 latent)
            grey = torch.full_like(pixels, 0.5)
            pixels_for_encode = pixels * (1.0 - mask_3c) + grey * mask_3c

        # ===== 6. VAE 编码 =====
        latent_samples = vae.encode(pixels_for_encode[:, :, :, :3])

        # latent_noise 模式:在 latent 上再叠加纯噪声
        if masked_content == "latent_noise":
            # 把蒙版缩到 latent 尺寸
            mask_latent_size = F.interpolate(
                mask.unsqueeze(1),
                size=(latent_samples.shape[2], latent_samples.shape[3]),
                mode="bilinear",
            )
            noise = torch.randn_like(latent_samples)
            latent_samples = latent_samples * (1.0 - mask_latent_size) + \
                             noise * mask_latent_size

        # ===== 7. 缩放蒙版到 latent 尺寸,作为 noise_mask =====
        mask_for_latent = F.interpolate(
            mask.unsqueeze(1),
            size=(latent_samples.shape[2], latent_samples.shape[3]),
            mode="bilinear",
        )

        out_latent = {
            "samples": latent_samples,
            "noise_mask": mask_for_latent,
        }

        return (img, mask, out_latent, img)

    @staticmethod
    def _gaussian_blur_mask(mask, blur_radius):
        """高斯模糊蒙版 — 模拟 WebUI 的 mask blur 行为"""
        if blur_radius <= 0:
            return mask

        # 生成 1D 高斯核
        sigma = blur_radius / 2.0
        ksize = blur_radius * 2 + 1
        x = torch.arange(ksize, dtype=torch.float32, device=mask.device) - blur_radius
        gauss_1d = torch.exp(-(x ** 2) / (2 * sigma ** 2))
        gauss_1d = gauss_1d / gauss_1d.sum()

        # 2D 可分离卷积:先横向再纵向
        kernel_h = gauss_1d.view(1, 1, 1, ksize)
        kernel_v = gauss_1d.view(1, 1, ksize, 1)

        m4 = mask.unsqueeze(1)  # [B, 1, H, W]
        m4 = F.conv2d(m4, kernel_h, padding=(0, blur_radius))
        m4 = F.conv2d(m4, kernel_v, padding=(blur_radius, 0))
        m4 = torch.clamp(m4, 0.0, 1.0)
        return m4.squeeze(1)

    @classmethod
    def IS_CHANGED(cls, image, **kwargs):
        return nodes.LoadImage.IS_CHANGED(image)

    @classmethod
    def VALIDATE_INPUTS(cls, image, **kwargs):
        return nodes.LoadImage.VALIDATE_INPUTS(image)


# ============================================================================
# 配套的整图合成节点 — 把 KSampler 的重绘结果按蒙版贴回原图
# 这样蒙版外的区域是 100% 原图像素,完全无色差(WebUI 的核心行为)
# ============================================================================

class InpaintComposite:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "original": ("IMAGE", {"tooltip": "原图(从 LoadImageInpaintWebUI 的 original_image 输出来)"}),
                "inpainted": ("IMAGE", {"tooltip": "VAEDecode 后的重绘结果"}),
                "mask": ("MASK", {"tooltip": "蒙版(从 LoadImageInpaintWebUI 的 mask 输出来)"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "composite"
    CATEGORY = "image"
    DESCRIPTION = "把重绘结果按蒙版贴回原图,蒙版外区域保持原图像素无色差(WebUI 整图合成)"

    def composite(self, original, inpainted, mask):
        # 对齐尺寸
        if inpainted.shape[1:3] != original.shape[1:3]:
            # 把 inpainted 缩到原图尺寸
            inpainted = inpainted.permute(0, 3, 1, 2)
            inpainted = F.interpolate(
                inpainted,
                size=(original.shape[1], original.shape[2]),
                mode="bilinear",
            )
            inpainted = inpainted.permute(0, 2, 3, 1)

        if mask.dim() == 2:
            mask = mask.unsqueeze(0)
        if mask.shape[1:3] != original.shape[1:3]:
            m = mask.unsqueeze(1)
            m = F.interpolate(
                m, size=(original.shape[1], original.shape[2]), mode="bilinear"
            )
            mask = m.squeeze(1)

        mask_3c = mask.unsqueeze(-1)
        result = original * (1.0 - mask_3c) + inpainted * mask_3c
        result = torch.clamp(result, 0.0, 1.0)
        return (result,)


NODE_CLASS_MAPPINGS = {
    "LoadImageInpaintWebUI": LoadImageInpaintWebUI,
    "InpaintComposite": InpaintComposite,
    # 保留旧名以兼容已有的工作流引用
    "LoadImageInpaintKeep": LoadImageInpaintWebUI,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadImageInpaintWebUI": "Load Image (Inpaint WebUI Style)",
    "InpaintComposite": "Inpaint Composite (WebUI Style)",
    "LoadImageInpaintKeep": "Load Image (Inpaint WebUI Style)",
}
