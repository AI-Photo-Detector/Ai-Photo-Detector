# AI Photo Detector

A web app prototype for analyzing uploaded images and estimating whether they are AI-generated.

> **Current status:** Frontend and backend are runnable locally. Frontend uses the backend `/api/detect` endpoint for analysis.

## Features

- Drag-and-drop image upload UI.
- Real upload flow from frontend to backend API.
- Result dashboard showing:
  - AI/real classification badge
  - confidence score
  - per-indicator status (pass/warning/fail)
- Optional OpenAI VLM visual review for hands, text, reflections, geometry, and other visible AI-artifact signals.
- PDF export of a detection report.
- "How to Use" guide tab in the app.

## Tech Stack

- **Frontend:** React + TypeScript + Vite
- **Backend:** FastAPI + Uvicorn
- **UI:** Radix UI primitives + custom styled components
- **Icons:** Lucide React
- **PDF generation:** jsPDF

## Getting Started

### Prerequisites

- Node.js 18+
- npm 9+
- Python 3.11+

### Run the Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL is typically `http://localhost:3000`.

### Run the Backend

From the repo root:

```bash
pip install -r backend/requirements.txt
python -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

Health endpoints:

- `GET /health`
- `GET /api/health`

### Run Full App

Terminal 1:

```bash
python -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```bash
cd frontend
npm run dev
```

Open:

- Frontend: `http://localhost:3000`
- Backend docs: `http://127.0.0.1:8000/docs`

### Build for Production

```bash
cd frontend
npm run build
npm run preview
```

The frontend production bundle is written to `frontend/dist/`.

## Backend API Contract

### Endpoint

- `POST /api/detect`
- `Content-Type: multipart/form-data`
- Upload field: `file`

### Request Rules

- One uploaded image file
- Accepted MIME types:
  - `image/jpeg`
  - `image/png`
  - `image/webp`
- Max size: `10 MB` (`10 * 1024 * 1024` bytes)

### Success Response (200)

```json
{
  "isAIGenerated": true,
  "confidence": 84.62,
  "indicators": [
    {
      "label": "Pixel Consistency",
      "value": 88.39,
      "status": "pass"
    }
  ],
  "metadata": {
    "requestId": "66c9e8b5-c6f8-434d-b95f-22eb8b21a6a9",
    "fileName": "portrait.png",
    "fileSize": 245103,
    "mimeType": "image/png",
    "modelName": "bitmind_api",
    "usedFallback": false,
    "deterministicSeed": null
  }
}
```

### Error Response (4xx/5xx)

```json
{
  "error_code": "UNSUPPORTED_MEDIA_TYPE",
  "message": "Unsupported file type.",
  "details": {
    "requestId": "ec9124bc-8784-49f1-b2db-fb10861f6f3d",
    "mimeType": "image/gif",
    "acceptedMimeTypes": ["image/jpeg", "image/png", "image/webp"]
  }
}
```

## Provider Setup

Provider-backed inference requires `BITMIND_API_KEY`. Copy `.env.example` to `.env` and set your own key before running provider-backed detection. The FastAPI app loads `.env` automatically when `python-dotenv` is installed from `backend/requirements.txt`.

Environment variables:

- `BITMIND_API_KEY` (required for BitMind provider inference)
- `BITMIND_DETECT_URL` (default: `https://api.bitmind.ai/oracle/v1/34/detect-image`)
- `BITMIND_APPLICATION` (default: `oracle-api`)
- `BITMIND_TIMEOUT_SECONDS` (default: `60`)
- `OPENAI_API_KEY` (optional; used only when `DETECTOR_ENABLE_VLM=1`)
- `OPENAI_VLM_MODEL` (default: `gpt-4.1-mini`)
- `OPENAI_VLM_URL` (default: `https://api.openai.com/v1/responses`)
- `OPENAI_VLM_TIMEOUT_SECONDS` (default: `45`)
- `OPENAI_VLM_DETAIL` (`low`, `high`, or `auto`; default: `auto`)
- `DETECTOR_ENABLE_VLM` (`0` keeps the VLM card off; set `1` only when you want the paid demo review)
- `DETECTOR_DISABLE_FALLBACK` (`1` disables heuristic fallback)

The VLM result is added as a supporting forensic card. It does not override the primary detector by itself.

## Project Structure

```text
.
|-- backend/                 # FastAPI service and detector pipeline
|   `-- detector/            # Model/provider, preprocessing, and forensic checks
|-- docs/                    # Project notes and forensic module guidelines
|-- frontend/                # React + TypeScript Vite app
|   `-- src/
|       |-- api/             # Backend API client and response types
|       |-- components/      # App sections and small UI primitives
|       `-- utils/           # PDF export and result normalization helpers
`-- tests/                   # Backend tests and API validation script
```

## Notes

- Detection indicators are derived from model output and supporting heuristic evidence.
- Frontend result view is backend-driven (no simulated random UI output).

## License

This project is licensed under the terms in [`LICENSE`](./LICENSE).
