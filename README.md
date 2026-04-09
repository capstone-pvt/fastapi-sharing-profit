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

#### Option A — Local only (browser / web Flutter)

```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000` and interactive docs at `http://localhost:8000/docs`.

#### Option B — Exposed on the local network (physical Android / iOS device)

When you want to test the Flutter app on a real phone, the API has to listen on **all network interfaces** (`0.0.0.0`) so the phone can reach it over Wi-Fi:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then on your computer, find your LAN IP:

| OS | Command |
|---|---|
| Windows | `ipconfig` → `IPv4 Address` of your active Wi-Fi adapter |
| macOS | `ipconfig getifaddr en0` |
| Linux | `hostname -I \| awk '{print $1}'` |

Verify it works from another device on the same Wi-Fi:

```
http://<your-computer-ip>:8000/docs
```

If the page doesn't load:

1. **Firewall** — Windows Defender / macOS firewall may block inbound 8000. Allow Python or open port 8000 explicitly.
2. **Same network** — phone and computer must be on the same Wi-Fi (watch out for guest networks and 2.4 / 5 GHz isolation).
3. **CORS** — for the web Flutter build hitting your LAN API from a browser, set `ALLOWED_ORIGINS` in `.env` to include the Flutter origin (or `*` for development).

Then point the Flutter app at `http://<your-computer-ip>:8000/api` — see the Flutter README's "Run on a Physical Device" section.

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
