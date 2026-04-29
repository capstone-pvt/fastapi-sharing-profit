# Smart Catch — draw.io diagrams

Three editable diagrams reflecting the post-rollout state of the system
(5-species classifier, weight regressor, flat ₱8.50/kg price fallback,
versioning across all three apps).

| File | Description |
| --- | --- |
| [system-flowchart.drawio](system-flowchart.drawio) | End-to-end runtime flow: auth → role routing, AI fish scan pipeline, trip → sales → profit-share lifecycle, admin/forecasts/audit, build/deploy/observability swimlane. |
| [database-schema.drawio](database-schema.drawio) | All MongoDB collections grouped by domain (Auth, Company/Licensing, Vessels & Crew, Trips/Sales/Expenses, Profit Sharing, AI/ML, Audit/Notifications) with key fields and FK relationships. |
| [use-case-diagram.drawio](use-case-diagram.drawio) | UML use-case: 6 actors (Super, Admin, Owner, Broker, Crew, Government) + 1 system-actor (AI Inference), grouped by feature area, with `«include»` and `«extend»` relationships. |

## How to view / edit

**Option 1 — web (no install):**
1. Open https://app.diagrams.net
2. File → Open from → Device → pick the `.drawio` file
3. Edit, then File → Save (overwrites the local file)

**Option 2 — desktop:**
- Install [draw.io Desktop](https://github.com/jgraph/drawio-desktop/releases) (free, cross-platform).
- Double-click any `.drawio` file in this folder.

**Option 3 — VS Code:**
- Install the `Draw.io Integration` extension (Henning Dieterichs).
- Open the `.drawio` file in VS Code; it renders inline and saves on `Ctrl+S`.

## Exporting to PNG / SVG / PDF for thesis defense

Inside draw.io: **File → Export as → PNG / SVG / PDF**.
For high-resolution thesis figures use:
- PDF: tick "Crop" + "Include a copy of my diagram" (re-editable).
- PNG: 300 DPI, transparent background.

## Keeping diagrams in sync

After major architectural changes, update the source `.drawio` files (not the
exported images) and commit. The diagrams are checked into the repo so the
thesis figures are reproducible.
