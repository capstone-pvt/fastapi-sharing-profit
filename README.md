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

## Seed Broker Role/Permissions

The API auto-seeds the Broker/Financer role and its default permissions on startup.
You can also run the seeder manually:

```
python -m app.seeders.run_broker
```

## Seed Boat Owner Role/Permissions

The API auto-seeds the Boat Owner role and its default permissions on startup.
You can also run the seeder manually:

```
python -m app.seeders.run_boat_owner
```

## Seed All Roles/Permissions

To seed Broker/Financer, Boat Owner, and Fisherman in one go:

```
python -m app.seeders.run_all
```

Or run the project root seeder:

```
python seed.py
```

## Backfill Default User Role

The combined seeders will also assign the default `User` role to any existing
users without a role.

## Notes

- Collections use the same names as the NestJS implementation.
- Fish analysis uses a placeholder response in FastAPI; training sample export is implemented.
- ML training/inference is still handled by the Python scripts under `ml_training/`.
