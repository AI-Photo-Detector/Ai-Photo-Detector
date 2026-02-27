# Import FastAPI framework
from fastapi import FastAPI

# Middleware that allows frontend (React) to talk to backend
from fastapi.middleware.cors import CORSMiddleware

# Import API routes defined in routes.py
from routes import router


# Create FastAPI app instance
app = FastAPI(
    title="AI Photo Detector API",   # shown in Swagger docs
    version="0.1.0"
)


# -------------------------------
# CORS CONFIGURATION
# -------------------------------
# This is VERY important.
# Without this, the React frontend cannot call the backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # allow all origins for now (safe for dev)
    allow_credentials=True,
    allow_methods=["*"],      # allow GET, POST, etc.
    allow_headers=["*"],      # allow all headers
)


# -------------------------------
# REGISTER ROUTES
# -------------------------------
# This connects the endpoints in routes.py to the main app
app.include_router(router)


# -------------------------------
# BASIC ENDPOINTS
# -------------------------------

# Root endpoint → just confirms backend is running
@app.get("/")
def root():
    return {"message": "AI Photo Detector backend running"}


# Health endpoint → useful for testing / deployment checks
@app.get("/health")
def health():
    return {"status": "ok"}
