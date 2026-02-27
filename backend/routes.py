# APIRouter lets us organize endpoints in separate files
from fastapi import APIRouter, UploadFile, File, HTTPException

# Import the detection logic from detector/service.py
from detector.service import detect_image

# Import response schema for validation
from schemas import DetectionResponse


# Create router instance
router = APIRouter()


# -------------------------------
# POST /detect
# -------------------------------
# This endpoint receives an uploaded image
# and returns AI/real prediction result.
@router.post("/detect", response_model=DetectionResponse)
async def detect(file: UploadFile = File(...)):
    
    # ---------------------------
    # Validate uploaded file type
    # ---------------------------
    # Ensure user actually uploads an image
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file.")

    # ---------------------------
    # Read file bytes into memory
    # ---------------------------
    image_bytes = await file.read()

    # Check for empty file
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    # ---------------------------
    # Call detection logic
    # ---------------------------
    # This currently returns a placeholder,
    # but later will call forensic API or ML model.
    return detect_image(image_bytes)
