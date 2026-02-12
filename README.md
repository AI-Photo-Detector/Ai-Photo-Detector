# AI Photo Detector

A web app prototype for analyzing uploaded images and estimating whether they are AI-generated.

> **Current status:** The frontend is implemented and runnable. The backend, model, and test scaffolding are present but mostly placeholders in this repository.

## Features

- Drag-and-drop image upload with multi-file selection UI.
- Simulated image analysis flow with loading state.
- Result dashboard showing:
  - AI/real classification badge
  - confidence score
  - per-indicator status (pass/warning/fail)
- PDF export of a detection report.
- “How to Use” guide tab in the app.

## Tech Stack

- **Frontend:** React + TypeScript + Vite
- **UI:** Radix UI primitives + custom styled components
- **Icons:** Lucide React
- **PDF generation:** jsPDF

## Getting Started

### Prerequisites

- Node.js 18+
- npm 9+

### Run the Frontend

```bash
cd frontend
npm install
npm run dev
```

The app will start on Vite’s default local URL (typically `http://localhost:5173`).

### Build for Production

```bash
cd frontend
npm run build
```

## Project Structure

```text
.
├── frontend/        # Runnable web UI
├── backend/         # API scaffold (currently placeholder)
├── model/           # Model config/artifacts scaffold (currently placeholder)
├── scripts/         # Utility scripts (currently placeholder)
└── tests/           # Test scaffold (currently placeholder)
```

## Notes

- The current detector behavior in the frontend is simulated (randomized demo output), not a real model inference pipeline yet.
- Root-level and backend/model documentation may be expanded as backend and model code are implemented.

## License

This project is licensed under the terms in [`LICENSE`](./LICENSE).
