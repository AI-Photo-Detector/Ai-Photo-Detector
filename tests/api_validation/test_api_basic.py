"""
Manual validation script for the BitMind API.

Usage:
  1. Set the BITMIND_API_KEY environment variable.
  2. Update IMAGE_PATH below to point at a real image file.
  3. Run: python -m tests.api_validation.test_api_basic
"""

import base64
import mimetypes
import os
from pathlib import Path

import requests

API_KEY = os.getenv("BITMIND_API_KEY")
if not API_KEY:
    raise RuntimeError("Set BITMIND_API_KEY before running this validation script.")

URL = "https://api.bitmind.ai/oracle/v1/34/detect-image"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "x-bitmind-application": "oracle-api",
    "Content-Type": "application/json",
    "Accept": "*/*",
}

IMAGE_PATH = Path("tests/images/sample.png")

if not IMAGE_PATH.exists():
    raise FileNotFoundError(
        f"Image not found: {IMAGE_PATH}  — update IMAGE_PATH to a real file."
    )

mime_type, _ = mimetypes.guess_type(str(IMAGE_PATH))
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
    timeout=60,
)

assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
data = response.json()
assert "probability" in data or "confidence" in data or "score" in data, (
    f"Response missing expected probability field: {data}"
)
