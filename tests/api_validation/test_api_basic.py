import requests
import base64
import mimetypes
from pathlib import Path

API_KEY = "bitmind-bf76cb20-02ac-11f1-83b3-6f90b3a830e0:b504b9e4"

URL = "https://api.bitmind.ai/oracle/v1/34/detect-image"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "x-bitmind-application": "oracle-api",
    "Content-Type": "application/json",
    "Accept": "*/*",
}

# ----------------------------
# Local image path ONLY
# ----------------------------
# Example:"C:\\Users\\Engineer\\Desktop\\fake-photo\\12.png"
IMAGE_PATH = Path("Ai-Photo-Detector\tests\images\<YOUR_IMAGE_NAME>")  #<- add the image path in here then run the code

if not IMAGE_PATH.exists():
    raise FileNotFoundError(f"Image not found: {IMAGE_PATH}")

mime_type, _ = mimetypes.guess_type(IMAGE_PATH)
if mime_type is None:
    raise ValueError("Unsupported image type. Use jpg, png, webp, etc.")

with IMAGE_PATH.open("rb") as f:
    encoded_image = base64.b64encode(f.read()).decode("utf-8")

payload = {
    "rich": True,
    "source": "local-test-harness",
    "image": f"data:{mime_type};base64,{encoded_image}",
}

response = requests.post(
    URL,
    json=payload,
    headers=HEADERS,
    timeout=60
)

print("Status:", response.status_code)
print(response.text)
