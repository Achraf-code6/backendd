import io
import base64
import cv2
import numpy as np
from PIL import Image
from pydantic import BaseModel
from fastapi import APIRouter

router = APIRouter()


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


def remove_background_cv2(image: np.ndarray) -> np.ndarray:
    """Remove background using color-based segmentation (simple approach)."""
    try:
        # Convert to RGBA
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGBA)
        elif image.shape[2] == 3:
            image = cv2.cvtColor(image, cv2.COLOR_RGB2RGBA)
        elif image.shape[2] == 4:
            image = image.copy()
        else:
            return image

        # Simple background removal based on edge detection
        # For product images with clean backgrounds, this works reasonably well
        gray = cv2.cvtColor(image, cv2.COLOR_RGBA2GRAY)

        # Apply Gaussian blur to reduce noise
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        # Threshold to create mask - use simple binary threshold instead of OTSU
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Create mask where background is white/near-white
        lower_white = np.array([240, 240, 240, 255], dtype=np.uint8)
        upper_white = np.array([255, 255, 255, 255], dtype=np.uint8)
        mask = cv2.inRange(image, lower_white, upper_white)

        # Invert mask
        mask_inv = cv2.bitwise_not(mask)

        # Apply mask to image
        result = cv2.bitwise_and(image, image, mask=mask_inv)

        return result
    except Exception as e:
        print(f"Background removal error: {e}")
        # Return original image if processing fails
        if len(image.shape) == 3 and image.shape[2] == 3:
            return cv2.cvtColor(image, cv2.COLOR_RGB2RGBA)
        return image


def apply_background(image: np.ndarray, bg_color: tuple[int, int, int]) -> np.ndarray:
    """Apply a solid color background to the image."""
    # Create background
    bg = np.full(image.shape, (*bg_color, 255), dtype=np.uint8)

    # Convert image to 4 channels if needed
    if len(image.shape) == 3 and image.shape[2] == 3:
        image = cv2.cvtColor(image, cv2.COLOR_RGB2RGBA)
    if len(bg.shape) == 3 and bg.shape[2] == 3:
        bg = cv2.cvtColor(bg, cv2.COLOR_RGB2RGBA)

    # Get alpha channel
    if image.shape[2] == 4:
        alpha = image[:, :, 3]
        mask = alpha // 255  # 0 = background, 255 = foreground
        mask = mask.astype(np.uint8)

        # Expand mask to 3 channels for bitwise operations
        mask_3ch = cv2.merge([mask, mask, mask])

        # Combine background and foreground
        fg = cv2.multiply(image.astype(np.float32), mask_3ch.astype(np.float32) / 255.0)
        bg_masked = cv2.multiply(bg.astype(np.float32), (1 - mask_3ch.astype(np.float32) / 255.0))
        result = cv2.add(fg, bg_masked)
    else:
        result = image

    return result.astype(np.uint8)


def apply_watermark(image: np.ndarray, logo: np.ndarray, opacity: float = 0.30) -> np.ndarray:
    """Apply watermark logo to image in bottom-right corner."""
    h, w = image.shape[:2]

    # Calculate logo size (max 20% of image width)
    max_w = int(w * 0.20)
    ratio = max_w / logo.shape[1]
    new_size = (int(logo.shape[1] * ratio), int(logo.shape[0] * ratio))
    logo_resized = cv2.resize(logo, new_size, interpolation=cv2.INTER_AREA)

    # Position in bottom-right with padding
    padding = 20
    x = w - logo_resized.shape[1] - padding
    y = h - logo_resized.shape[0] - padding

    # Ensure logo fits within image bounds
    if x < 0 or y < 0:
        return image

    # Apply opacity to logo
    logo_with_opacity = logo_resized.astype(np.float32) * opacity
    logo_with_opacity = logo_with_opacity.astype(np.uint8)

    # Create a region of interest
    roi = image[y:y+logo_resized.shape[0], x:x+logo_resized.shape[1]]

    # Blend logo with ROI
    if len(roi.shape) == 3 and roi.shape[2] == 4 and len(logo_with_opacity.shape) == 3:
        # Convert to RGB for blending if needed
        if roi.shape[2] == 4:
            roi_rgb = cv2.cvtColor(roi, cv2.COLOR_RGBA2RGB)
        else:
            roi_rgb = roi

        # Blend
        blended = cv2.addWeighted(roi_rgb, 1, cv2.cvtColor(logo_with_opacity, cv2.COLOR_RGBA2RGB), opacity, 0)
        image[y:y+logo_resized.shape[0], x:x+logo_resized.shape[1]] = blended
    else:
        image[y:y+logo_resized.shape[0], x:x+logo_resized.shape[1]] = logo_with_opacity

    return image


@router.post("/")
async def process_image(data: ImageRequest):
    try:
        # Decode input image
        image_data = base64.b64decode(data.image_base64)
        input_image = Image.open(io.BytesIO(image_data))

        # Convert PIL to OpenCV format
        cv_image = cv2.cvtColor(np.array(input_image), cv2.COLOR_RGB2BGR)

        # Remove background
        no_bg = remove_background_cv2(cv_image)

        # Apply background color
        bg_rgb = hex_to_rgb(data.bg_color)
        result_image = apply_background(no_bg, bg_rgb)

        # Convert back to RGB for PIL
        result_image = cv2.cvtColor(result_image, cv2.COLOR_BGR2RGB)

        # Apply watermark if provided
        if data.logo_base64:
            try:
                logo_data = base64.b64decode(data.logo_base64)
                logo_image = Image.open(io.BytesIO(logo_data))
                logo_cv = cv2.cvtColor(np.array(logo_image), cv2.COLOR_RGB2BGR)
                logo_cv = cv2.cvtColor(logo_cv, cv2.COLOR_BGR2RGBA)
                result_image = apply_watermark(result_image, logo_cv, opacity=0.30)
            except Exception as e:
                print(f"Watermark application failed: {e}")

        # Convert to PIL then to base64
        result_pil = Image.fromarray(result_image)
        output_buffer = io.BytesIO()
        result_pil.save(output_buffer, format="PNG")
        output_base64 = base64.b64encode(output_buffer.getvalue()).decode("utf-8")

        return ImageResponse(processed_image_base64=output_base64)
    except Exception as e:
        print(f"Image processing failed: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}