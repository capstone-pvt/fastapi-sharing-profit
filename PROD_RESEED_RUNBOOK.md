# Prod re-seed runbook (post merge of #5 + chore/strip-legacy-species)

**Why this exists**
Both PRs deployed the new 5-species classifier and removed the legacy 65-species seed code. **Prod's `fish_species` collection still contains the 65 legacy docs**, so even though the model now predicts class indices 0–4, the API will look those indices up in Mongo and return wrong species names.

This file walks you through fixing prod. Total time: ~5 min, downtime: zero.

---

## Step 0 — Confirm the new build is live on Railway

1. Open https://railway.app → `fastapi-sharing-profit` project.
2. Latest deployment should be from the merge commit of #5 (or the chore PR if that's later). Wait for status `SUCCESS`.
3. In the build log, confirm `app/models/classifier/best.pt` is included (it'll show the file size — should be ~31 MB).

**Smoke check the deploy is healthy** (replace URL with your prod base):
```bash
curl -fsS https://<your-railway-app>.up.railway.app/health
# expect 200 / {"status": "ok"}
```

If the deploy failed or the health check is red, **stop here** and fix that first — don't re-seed against a degraded backend.

---

## Step 1 — Re-seed `fish_species` against PROD Mongo

You have two options. Pick whichever you have credentials for.

### Option A — Run from your laptop with prod's `MONGODB_URI`

Get the prod Mongo URI from Railway → `fastapi-sharing-profit` → Variables → `MONGODB_URI`.

```bash
cd profit_sharing_api_fastapi

# Make a backup .env, then write a temporary one pointing at prod.
cp .env .env.local.bak
cat > .env <<'EOF'
MONGODB_URI=<paste-prod-uri-here>
DATABASE_NAME=smart_catch
EOF

# Preview — should print 5 docs in classIndex 0..4 order, no writes.
PYTHONPATH=. ./venv/Scripts/python.exe scripts/seed_5_species_only.py --dry-run

# Apply — drops all fish_species docs, inserts the 5 canonical ones.
PYTHONPATH=. ./venv/Scripts/python.exe scripts/seed_5_species_only.py

# Restore your local .env IMMEDIATELY — you don't want to forget you're pointed at prod.
mv .env.local.bak .env
```

### Option B — Run from a Railway shell

Railway dashboard → `fastapi-sharing-profit` service → "Shell" or "Exec" tab.

```bash
PYTHONPATH=. python scripts/seed_5_species_only.py --dry-run
PYTHONPATH=. python scripts/seed_5_species_only.py
```

Railway containers already have `MONGODB_URI` in their env, so no `.env` juggling needed.

---

## Step 2 — Verify in prod Mongo

Connect to prod with `mongosh` (or Mongo Compass) and run:

```js
db.fish_species.find({}, { name: 1, classIndex: 1, _id: 0 }).sort({ classIndex: 1 })
```

Expected output — exactly 5 docs, in this order:

```
[0] Auxis rochei
[1] Elagatis bipinnulata
[2] Euthynnus affinis
[3] Katsuwonus pelamis
[4] Thunnus albacares
```

If you see more than 5 or any of the legacy names (Bangus, Tilapia, Galunggong, etc.), the seed didn't run — repeat Step 1.

---

## Step 3 — Smoke-test the API

Replace `<token>` and `<base-url>` with your prod values.

```bash
# Photo of a yellowfin tuna
curl -X POST "https://<base-url>/api/v1/fish/analyze" \
  -H "Authorization: Bearer <token>" \
  -F "image=@yellowfin.jpg" \
  -F "singleFish=true" | jq .
```

In the response, check:
- `detections[0].species` — must be `"Thunnus albacares"` (or one of the 4 other trained names, depending on the photo).
- `detections[0].scientificName` — same value.
- `detections[0].englishName` — `"Yellowfin tuna"` (or matching common name).
- `detections[0].localName` — `"Barilis/Bariles/Karaw"` (or matching local name from `app/seeders/fish_models.py`).
- `detections[0].estimatedWeight` — should fall inside the species' `weightRange` (1.0–80.0 kg for yellowfin).

Repeat with 2–3 different fish photos to make sure each predicted class resolves to a `fish_species` doc.

---

## Step 4 — Once the FAQ PR is merged on the web

Watch [smart-catch-web/pull/new/chore/faq-update-trained-species](https://github.com/capstone-pvt/smart-catch-web/pull/new/chore/faq-update-trained-species). After it merges, the user-facing help page lists the 5 actual species.

---

## Rollback plan (if Step 3 fails)

1. **The classifier returns wrong indices** — symptom: `species` field is missing or empty. Check the Railway deploy log; the wrong `best.pt` may be loaded. Roll the deploy back to before merge of #5 (Railway → "Deployments" → "Rollback").
2. **The species lookup returns null** — symptom: `species` field has a class index instead of a name. Step 1 wasn't applied. Re-run it.
3. **Weight predictions are wildly off (>30% MAPE on tubs)** — this is expected behavior with the new regressor (CV R² is −30 in training). To restore the previous regressor:
   ```bash
   # The previous weight_model.joblib is preserved in the repo's backup folder
   # (NOT in git — it lives on the Railway deploy disk if the backup was committed).
   # If you need to restore it, copy from app/models/.backup_20260429_020250/weight/
   # in your local clone, push to a hotfix branch, and redeploy.
   ```

---

## Known follow-ups (not blocking)

- **Test fixtures in `smart-catch-web`** still reference `Bangus` / `Tilapia` / `Tuna`. They don't affect runtime behavior but should be updated for hygiene. Out of scope for this rollout.
- **Weight regressor needs more ground-truth data** to be production-grade. 54 rows is too few; CV R² is negative. Plan to collect more rows + add per-photo features (fish count, fill height, coin scale reference) before relying on Tub weight estimates for client-facing reports.
