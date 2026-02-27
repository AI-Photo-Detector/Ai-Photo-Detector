# Pydantic BaseModel is used to define
# the exact shape of API responses.
from pydantic import BaseModel


# This ensures every /detect response contains:
# - label (string)
# - confidence (float)
# - method (string)
class DetectionResponse(BaseModel):
    label: str
    confidence: float
    method: str
