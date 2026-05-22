"""
ComfyUI-Inpaint-WebUI-Style

WebUI-style inpaint nodes for ComfyUI:
  - Load Image (Inpaint WebUI Style)
  - Inpaint Composite (WebUI Style)

Reproduces AUTOMATIC1111 / Forge WebUI's inpaint behavior in ComfyUI:
mask blur, mask mode (invert), masked content (original/fill/latent_noise/
latent_nothing), only-masked padding, and final composite-back-to-original
for seamless, color-shift-free inpainting.
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

WEB_DIRECTORY = "./web"
