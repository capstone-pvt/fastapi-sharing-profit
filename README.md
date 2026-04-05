# Profit Sharing API (FastAPI)

This is a FastAPI conversion of the NestJS backend.

## Prerequisites

- Python 3.10+
- MongoDB running locally or a remote MongoDB URI
- (Optional) Trained ML model files for fish analysis

## Local Setup

### 1. Create and activate a virtual environment

```bash
cd profit_sharing_api_fastapi
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```bash
MONGODB_URI=mongodb://localhost:27017/smart_catch
DATABASE_NAME=smart_catch
JWT_SECRET=<your-secret-at-least-32-chars>
JWT_REFRESH_SECRET=<your-secret-at-least-32-chars>
```

Generate secrets with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

See `.env.example` for the full list of optional variables (CORS origins, ML model paths, Cloudinary, etc.).

### 4. Run the API

```bash
uvicorn app.main:app --reload --port 5000
```

The API will be available at `http://localhost:5000` and interactive docs at `http://localhost:5000/docs`.

To expose the API to devices on your local network (e.g. a phone running the Flutter app):

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
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

## Automated Training

You can automate export → dataset build → train → model copy:

```
python scripts/auto_train.py
```

Options:
- `--export-root exports/fish-training/<timestamp>` to use an existing export
- `--skip-detect` when you have no bboxes yet
- `--skip-regression` to skip weight/price models
