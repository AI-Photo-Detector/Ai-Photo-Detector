import argparse
import base64
import mimetypes
import os
from pathlib import Path

import pytest
import requests

pytestmark = pytest.mark.skip(
    reason="Manual API validation script only; excluded from automated test runs."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manual validation script for BitMind image detection API."
    )
    parser.add_argument(
        "--image",
        required=True,
        help="Path to the local image file to validate.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    api_key = os.getenv("BITMIND_API_KEY")
    if not api_key:
        raise ValueError("BITMIND_API_KEY environment variable is required.")

    url = os.getenv(
        "BITMIND_API_URL",
        "https://api.bitmind.ai/oracle/v1/34/detect-image",
    )

    image_path = Path(args.image)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    mime_type, _ = mimetypes.guess_type(image_path)
    if mime_type is None:
        raise ValueError("Unsupported image type. Use jpg, png, webp, etc.")

    with image_path.open("rb") as f:
        encoded_image = base64.b64encode(f.read()).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "x-bitmind-application": "oracle-api",
        "Content-Type": "application/json",
        "Accept": "*/*",
    }

    payload = {
        "rich": True,
        "source": "local-test-harness",
        "image": f"data:{mime_type};base64,{encoded_image}",
    }

    print(f"Using image: {image_path}")
    print(f"Sending request to: {url}")

    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=60,
    )

    print("Status:", response.status_code)
    print("Response:")
    print(response.text)


if __name__ == "__main__":
    main()