# Profit Sharing API (FastAPI)

This is a FastAPI conversion of the NestJS backend.

## Setup

```
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

## Environment

Required variables:
- `MONGODB_URI`
- `DATABASE_NAME`
- `JWT_SECRET`
- `JWT_REFRESH_SECRET`

Optional:
- `UPLOAD_ROOT` (default: `uploads`)
- `MODEL_ROOT` (default: `models`)

## Run

```
uvicorn app.main:app --reload --port 5000
```

## Notes

- Collections use the same names as the NestJS implementation.
- Fish analysis uses a placeholder response in FastAPI; training sample export is implemented.
- ML training/inference is still handled by the Python scripts under `ml_training/`.
