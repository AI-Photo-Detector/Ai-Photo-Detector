import pytest
from fastapi.testclient import TestClient

from backend.app import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + (b"\x00" * 64)


@pytest.fixture
def sample_jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + (b"\x00" * 64)


@pytest.fixture
def sample_webp_bytes() -> bytes:
    return b"RIFF" + (b"\x00" * 4) + b"WEBP" + (b"\x00" * 32)


@pytest.fixture
def text_file_bytes() -> bytes:
    return b"this is not an image"