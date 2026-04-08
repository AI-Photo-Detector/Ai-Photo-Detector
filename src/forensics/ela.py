from PIL import Image, ImageChops, ImageEnhance
from .template import forensic_result_template
import tempfile
import os

def run(image_path: str) -> dict:
    result = forensic_result_template("Error Level Analysis (ELA)")

    temp_path = None

    try:
        with Image.open(image_path) as img:
            original = img.convert("RGB")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            temp_path = temp_file.name

        original.save(temp_path, "JPEG", quality=90)

        with Image.open(temp_path) as compressed:
            compressed = compressed.convert("RGB")
            ela_image = ImageChops.difference(original, compressed)

        extrema = ela_image.getextrema()
        max_diff = max(ex[1] for ex in extrema) if extrema else 1
        scale = 255.0 / max_diff if max_diff != 0 else 1
        ela_image = ImageEnhance.Brightness(ela_image).enhance(scale)

        pixels = list(ela_image.getdata())
        avg_diff = sum(sum(pixel) for pixel in pixels) / (len(pixels) * 3)

        score = min(avg_diff / 255.0, 1.0)
        confidence = min(0.5 + score / 2, 1.0)

        result["score"] = round(score, 3)
        result["confidence"] = round(confidence, 3)

        if score >= 0.6:
            result["verdict"] = "suspicious"
        elif score >= 0.3:
            result["verdict"] = "inconclusive"
        else:
            result["verdict"] = "clean"

        result["details"] = {
            "avg_pixel_difference": round(avg_diff, 3),
            "max_difference": max_diff
        }

    except Exception as e:
        result["score"] = 0.0
        result["confidence"] = 0.0
        result["verdict"] = "inconclusive"
        result["details"] = {"error": str(e)}

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

    return result