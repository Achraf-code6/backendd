import io
import os
import base64
from PIL import Image
from pydantic import BaseModel
from fastapi import APIRouter
from rembg import remove, new_session

router = APIRouter()

# Initialize rembg session once
rembg_session = None

def get_session():
    global rembg_session
    if rembg_session is None:
        rembg_session = new_session()
    return rembg_session


class ImageRequest(BaseModel):
    image_base64: str
    bg_color: str  # hex color like "#FF5733"
    logo_base64: str | None = None


class ImageResponse(BaseModel):
    processed_image_base64: str


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    elif len(hex_color) == 3:
        return tuple(int(hex_color[i:i+2], 16) // 17 for i in (0, 1, 2))
    return (255, 255, 255)


def apply_background(image: Image.Image, bg_color: tuple[int, int, int]) -> Image.Image:
    """Apply a solid color background to the image."""
    result = Image.new("RGBA", image.size, bg_color + (255,))
    result.paste(image, (0, 0), image)
    return result.convert("RGB")


def apply_watermark(image: Image.Image, logo: Image.Image, opacity: float = 0.30) -> Image.Image:
    """Apply watermark logo to image in bottom-right corner."""
    image = image.convert("RGBA")
    logo = logo.convert("RGBA")

    # Calculate watermark size (max 20% of image width)
    max_w = int(image.width * 0.20)
    ratio = max_w / logo.width
    new_size = (int(logo.width * ratio), int(logo.height * ratio))
    logo = logo.resize(new_size, Image.Resampling.LANCZOS)

    # Create semi-transparent logo
    alpha = logo.split()[3]
    alpha = alpha.point(lambda p: int(p * opacity))
    logo.putalpha(alpha)

    # Position in bottom-right with padding
    padding = 20
    x = image.width - logo.width - padding
    y = image.height - logo.height - padding

    # Composite logo onto image
    image.paste(logo, (x, y), logo)
    return image.convert("RGB")


@router.post("/")
async def process_image(data: ImageRequest):
    session = get_session()

    # Decode input image
    image_data = base64.b64decode(data.image_base64)
    input_image = Image.open(io.BytesIO(image_data)).convert("RGBA")

    # Remove background with rembg
    no_bg = remove(input_image, session=session)

    # Apply background color
    bg_rgb = hex_to_rgb(data.bg_color)
    result_image = apply_background(no_bg, bg_rgb)

    # Apply watermark if provided
    if data.logo_base64:
        try:
            logo_data = base64.b64decode(data.logo_base64)
            logo_image = Image.open(io.BytesIO(logo_data)).convert("RGBA")
            result_image = apply_watermark(result_image, logo_image, opacity=0.30)
        except Exception as e:
            print(f"Watermark application failed: {e}")

    # Convert to base64
    output_buffer = io.BytesIO()
    result_image.save(output_buffer, format="PNG")
    output_base64 = base64.b64encode(output_buffer.getvalue()).decode("utf-8")

    return ImageResponse(processed_image_base64=output_base64)
