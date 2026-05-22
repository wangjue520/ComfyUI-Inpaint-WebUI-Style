# ComfyUI-Inpaint-WebUI-Style

WebUI-style inpaint nodes for ComfyUI. Reproduces AUTOMATIC1111 / Forge WebUI's inpaint behavior so you get seamless, color-shift-free local redraws — without learning ComfyUI's idiosyncratic mask handling.

[中文说明 (Chinese)](#中文说明) | [English](#english)

---

## English

### Why this exists

ComfyUI's default inpaint flow (`VAEEncodeForInpaint` → `KSampler` → `VAEDecode`) has two annoying behaviors that WebUI users immediately notice:

1. **The masked region gets replaced with 0.5 gray before encoding**, so low `denoise` values produce gray mush instead of subtle edits.
2. **The entire image goes through VAE encode → decode**, introducing a global color/detail shift even in regions you never wanted to touch.

This pack provides two nodes that together replicate WebUI's behavior exactly: original-image preservation in the latent, mask blur with feathered edges, four "Masked content" modes, and final composite-back-to-original so unmasked pixels are identical to the input.

### Nodes

#### `Load Image (Inpaint WebUI Style)`

A drop-in replacement for `LoadImage` + `VAEEncodeForInpaint` that mirrors the WebUI inpaint input panel.

| Parameter | WebUI equivalent | Default | Description |
|---|---|---|---|
| `mask_blur` | Mask blur | `4` | Gaussian blur radius (px) on the mask, for feathered edges |
| `mask_mode` | Mask mode | `inpaint_masked` | `inpaint_masked` (redraw red region) or `inpaint_not_masked` (invert) |
| `masked_content` | Masked content | `original` | `original` / `fill` / `latent_noise` / `latent_nothing` |
| `only_masked_padding` | Only masked padding, pixels | `32` | Pixel-level mask dilation before blur |
| `grow_mask_by` | — | `6` | Extra latent-level mask dilation (ComfyUI standard) |

**Outputs:** `image` (original), `mask` (processed), `latent` (ready for KSampler), `original_image` (for the composite node)

#### `Inpaint Composite (WebUI Style)`

Pastes the inpainted result back onto the original image, blended by the mask. This is what makes unmasked regions truly identical to the input — no VAE round-trip color shift.

**Inputs:** `original`, `inpainted`, `mask`
**Output:** the composited image

### Recommended wiring

```
Load Image (Inpaint WebUI Style) ─┬─ latent ──────────→ KSampler ──→ VAEDecode ──┐
                                  ├─ original_image ─────────────→ Inpaint Composite ──→ SaveImage
                                  └─ mask ───────────────────────→
```

### Recommended KSampler settings (WebUI defaults)

| Parameter | Value |
|---|---|
| `cfg` | `7` |
| `sampler_name` | `euler_ancestral` (WebUI's "Euler a") |
| `scheduler` | `normal` |
| `denoise` | `0.75` |
| `steps` | `20` |

### Use case presets

| Task | `masked_content` | `denoise` | `mask_blur` |
|---|---|---|---|
| Touch up face / hands (detail fix) | `original` | `0.4–0.6` | `4` |
| Replace head or outfit (medium change) | `original` | `0.75–0.85` | `8` |
| Generate from scratch (full redraw) | `fill` | `1.0` | `8` |
| Repaint background completely | `latent_noise` | `1.0` | `16` |

### Installation

**Via ComfyUI Manager (recommended):**
1. Open Manager → "Install Custom Nodes"
2. Search for `Inpaint WebUI Style`
3. Click Install, restart ComfyUI

**Manual:**
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/wangjue520/ComfyUI-Inpaint-WebUI-Style
```
Restart ComfyUI.

### Requirements

- ComfyUI (any recent version)
- No extra Python packages — uses only PyTorch and ComfyUI's built-in modules

### License

MIT — see [LICENSE](LICENSE).

---

## 中文说明

### 为什么需要这个

ComfyUI 自带的局部重绘流程(`VAEEncodeForInpaint` → `KSampler` → `VAEDecode`)有两个让 WebUI 用户很不适应的行为:

1. **蒙版区域在 VAE 编码前会被替换成 0.5 灰**,导致低 denoise 时蒙版区出来一团灰糊。
2. **整图都会经过 VAE 编码→解码**,即使蒙版外的区域也会有色差和细节漂移。

这个插件提供两个节点,合起来完整复刻了 WebUI 的局部重绘行为:蒙版区保留原图、边缘高斯模糊、四种 Masked content 模式、最后整图按蒙版贴回原图,蒙版外区域 100% 是输入的原始像素。

### 节点说明

#### `Load Image (Inpaint WebUI Style)` —— 加载图片(WebUI 风格局部重绘)

一站式替换 `LoadImage` + `VAEEncodeForInpaint`,参数完全对应 WebUI 的局部重绘输入面板。

| 参数 | 对应 WebUI 选项 | 默认值 | 说明 |
|---|---|---|---|
| `mask_blur` | 蒙版模糊 | `4` | 蒙版边缘高斯模糊像素数,让接缝自然羽化 |
| `mask_mode` | 蒙版模式 | `inpaint_masked` | `inpaint_masked`=重绘红色区,`inpaint_not_masked`=重绘红色以外 |
| `masked_content` | 蒙版区内容 | `original` | `original`(原图)/ `fill`(均值填充)/ `latent_noise`(噪声)/ `latent_nothing`(纯黑) |
| `only_masked_padding` | 仅蒙版区填充 | `32` | 蒙版像素级向外扩展,与 mask_blur 配合 |
| `grow_mask_by` | — | `6` | latent 级蒙版扩展(ComfyUI 标准参数) |

**输出**:`image`(原图)、`mask`(处理后的蒙版)、`latent`(带 noise_mask,直接接 KSampler)、`original_image`(给合成节点用)

#### `Inpaint Composite (WebUI Style)` —— 局部重绘合成(WebUI 风格)

把 KSampler 的重绘结果按蒙版贴回原图。蒙版外的区域是 100% 原始像素,无 VAE 色差。

**输入**:`original`(原图)、`inpainted`(VAEDecode 的重绘结果)、`mask`(蒙版)
**输出**:合成后的最终图

### 推荐连线

```
Load Image (Inpaint WebUI Style) ─┬─ latent ──────────→ KSampler ──→ VAEDecode ──┐
                                  ├─ original_image ─────────────→ Inpaint Composite ──→ SaveImage
                                  └─ mask ───────────────────────→
```

### 推荐 KSampler 参数(WebUI 默认值)

| 参数 | 值 |
|---|---|
| `cfg` | `7` |
| `sampler_name` | `euler_ancestral`(对应 WebUI 的 "Euler a") |
| `scheduler` | `normal` |
| `denoise` | `0.75` |
| `steps` | `20` |

### 场景配置参考

| 用途 | `masked_content` | `denoise` | `mask_blur` |
|---|---|---|---|
| 修脸 / 修手(细节修复) | `original` | `0.4–0.6` | `4` |
| 换头 / 换衣服(中等改动) | `original` | `0.75–0.85` | `8` |
| 凭空生成新内容(完全重绘) | `fill` | `1.0` | `8` |
| 彻底重画背景 | `latent_noise` | `1.0` | `16` |

### 安装方法

**通过 ComfyUI Manager(推荐)**
1. 打开 Manager → "Install Custom Nodes"
2. 搜索 `Inpaint WebUI Style`
3. 点击 Install,重启 ComfyUI

**手动安装**
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/wangjue520/ComfyUI-Inpaint-WebUI-Style
```
重启 ComfyUI 即可。

### 环境要求

- ComfyUI(任意较新版本)
- 无需额外 Python 包,只用 PyTorch 和 ComfyUI 内置模块

### 开源许可证

MIT,详见 [LICENSE](LICENSE)。
