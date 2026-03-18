# Profit Sharing API - Application Flowchart

## Table of Contents

- [System Overview](#system-overview)
- [Application Startup](#application-startup)
- [Authentication Flow](#authentication-flow)
- [Role-Based Access Control (RBAC)](#role-based-access-control-rbac)
- [Fish Analysis Pipeline](#fish-analysis-pipeline)
- [Training Samples Flow](#training-samples-flow)
- [CRUD Operations](#crud-operations)
- [Cash Advance Flow](#cash-advance-flow)
- [Profit Sharing Flow](#profit-sharing-flow)
- [License Management](#license-management)
- [Weather Integration](#weather-integration)
- [Audit Logging](#audit-logging)
- [Data Storage Map](#data-storage-map)

---

## System Overview

```
                          +---------------------------+
                          |      Mobile / Web App     |
                          +------------+--------------+
                                       |
                                  HTTP / REST
                                       |
                          +------------v--------------+
                          |     FastAPI Application    |
                          |      (uvicorn server)      |
                          +---+-----+-----+-----+-----+
                              |     |     |     |
              +---------------+  +--+--+  |  +--+---------------+
              |                  |     |  |  |                   |
     +--------v--------+  +-----v-+  +v--v--v------+  +---------v--------+
     | Authentication  |  | RBAC  |  | API Routes  |  | ML Inference     |
     | JWT + Sessions  |  | Guard |  | (REST CRUD) |  | (YOLO + Joblib)  |
     +---------+-------+  +---+---+  +------+------+  +---------+--------+
               |               |            |                    |
               +-------+-------+            |          +---------v--------+
                       |                    |          | Local Filesystem |
                       v                    v          | app/models/*.pt  |
              +--------+--------------------+---+      | uploads/*        |
              |       MongoDB Atlas             |      +------------------+
              |       (smart_catch database)    |
              |                                 |
              |  users, roles, permissions,     |
              |  companies, fish_analyses,      |
              |  fish_species, fish_models,     |
              |  fish_training_samples,         |
              |  app_licenses, audit_logs,      |
              |  boats, vessels, trips,         |
              |  catches, fish_sales, expenses, |
              |  crew, profit_shares,           |
              |  profit_sharing_policies,       |
              |  cash_advances, forecasts       |
              +---------------------------------+
```

---

## Application Startup

```
Server Start (uvicorn app.main:app)
    |
    v
[Load .env file]
    |
    v
[Create FastAPI app]
    |
    v
[Register Middleware]
    |-- CORS (allow all origins)
    |-- Static files (/uploads)
    |
    v
[Include API Router (/api)]
    |
    v
@app.on_event("startup")
    |
    v
+-----------------------------------+
| 1. connect_db()                   |  --> MongoDB Atlas connection
|    AsyncIOMotorClient             |      (TLS via certifi)
+-----------------------------------+
    |
    v
+-----------------------------------+
| 2. Seed Roles & Permissions       |
|    seed_broker_role()             |  --> 37 permissions
|    seed_boat_owner_role()         |  --> 25 permissions
|    seed_fisherman_role()          |  --> 5 permissions
|    seed_admin_role()              |  --> ALL permissions (admin + super)
+-----------------------------------+
    |
    v
+-----------------------------------+
| 3. Seed Users                     |
|    backfill_default_user_role()   |  --> Assign 'user' role to unassigned
|    seed_default_role_users()      |  --> Create default super user
+-----------------------------------+
    |
    v
+-----------------------------------+
| 4. Seed Fish Data                 |
|    seed_fish_species()            |  --> 41 species (Bangus...Tuna)
|    seed_fish_models()             |  --> Model metadata records
+-----------------------------------+
    |
    v
+-----------------------------------+
| 5. Preload ML Models              |
|    preload_models()               |
|    +-- Detector  (YOLO .pt)      |  --> 6.0 MB
|    +-- Classifier (YOLO .pt)     |  --> 3.0 MB
|    +-- Weight    (Joblib)        |  --> 77 KB
|    +-- Price     (Joblib)        |  --> 77 KB
+-----------------------------------+
    |
    v
[Server Ready - Accepting Requests]
```

---

## Authentication Flow

### Registration

```
POST /api/auth/register
    |
    v
[Validate: email, password, firstName, lastName]
    |
    +-- Has companyName? ----------> [Create as ADMIN]
    |                                    |
    |                                    v
    |                              [Create Company]
    |                                    |
    |                                    v
    |                              [Generate Company Code]
    |                                    |
    +-- Has companyCode? ----------> [Join Existing Company]
    |                                    |
    |                                    v
    |                              [Check License maxUsers]
    |                                    |
    |                                    +-- Limit reached? --> 403 Forbidden
    |                                    |
    +-- Neither? ------------------> [Create as USER role]
    |
    v
[Hash password (bcrypt)]
    |
    v
[Insert user into DB]
    |
    v
[Generate JWT access + refresh tokens]
    |
    v
[Return { accessToken, refreshToken, user }]
```

### Login

```
POST /api/auth/login
    |
    v
[Find user by email]
    |
    +-- Not found? ---------> 401 "Invalid credentials"
    |
    v
[Verify password (bcrypt)]
    |
    +-- Wrong? --------------> 401 "Invalid credentials"
    |
    v
[Generate new sessionId (UUID)]
    |
    v
[Store sessionId in user document]
    |
    v
[Generate JWT tokens with sessionId claim]
    |
    v
[Return { accessToken, refreshToken, user }]
```

### Token Refresh

```
POST /api/auth/refresh
    |
    v
[Decode refresh token (JWT_REFRESH_SECRET)]
    |
    +-- Invalid/expired? ----> 401 Unauthorized
    |
    v
[Find user by token.sub]
    |
    v
[Check token.sid == user.sessionId]
    |
    +-- Mismatch? -----------> 401 "Session expired"
    |
    v
[Generate new access token]
    |
    v
[Return { accessToken }]
```

### Request Authentication

```
Any Protected Request
    |
    v
[Extract "Bearer <token>" from Authorization header]
    |
    +-- Missing? ------------> 401 Unauthorized
    |
    v
[Decode JWT (JWT_SECRET, HS256)]
    |
    +-- Invalid/expired? ----> 401 Unauthorized
    |
    v
[Find user by token.sub (userId)]
    |
    +-- Not found? ----------> 401 Unauthorized
    |
    v
[Check token.sid == user.sessionId]
    |
    +-- Mismatch? -----------> 401 "Session invalid"
    |                          (token was revoked / user re-logged)
    v
[Return user dict to route handler]
```

---

## Role-Based Access Control (RBAC)

### Role Hierarchy

```
+------------------------------------------------------------------+
|                         SUPER                                     |
|  All permissions + cross-company access                          |
|  Cannot edit/delete self                                         |
+------------------------------------------------------------------+
        |
+------------------------------------------------------------------+
|                         ADMIN                                     |
|  All permissions (company-scoped)                                |
|  Can manage users, roles, models, species, training, audit       |
+------------------------------------------------------------------+
        |
+---------------------------+--------------------------------------+
|        BROKER             |              OWNER                    |
| boats, vessels, trips,    | boats, fishermen, catches,           |
| vessel-owners, fish-sales,| profit-sharing-policies,             |
| expenses, cash-advances   | profit-shares, cash-advances,        |
| (read/approve/decline),   | forecasts, training-samples          |
| training-samples, user:read|                                     |
| forecasts, catches        |                                      |
+---------------------------+--------------------------------------+
        |                              |
+------------------------------------------------------------------+
|                         CREW                                      |
|  profit-shares:read, catches:read, fish-sales:read,             |
|  cash-advances:create/read                                       |
+------------------------------------------------------------------+
        |
+------------------------------------------------------------------+
|                         USER                                      |
|  No permissions (base role)                                      |
+------------------------------------------------------------------+
```

### Permission Check Flow

```
Incoming Request to Protected Route
    |
    v
[Depends(require_permissions("resource:action"))]
    |
    v
[get_current_user()] --> user dict
    |
    v
[Lookup user.roleId in roles collection]
    |
    +-- Role not found? -------> 403 Forbidden
    |
    v
[Get role.permissions array]
    |
    v
[Resolve permissions to name strings]
    |-- If ObjectIds --> query permissions collection
    |-- If objects   --> extract .name field
    |-- If strings   --> use directly
    |
    v
[Check: required permissions subset of role permissions?]
    |
    +-- Missing any? ----------> 403 Forbidden
    |
    v
[Allow request to proceed]
```

### Company Isolation (Multi-Tenancy)

```
Request with user context
    |
    v
[Is user Super?]
    |
    +-- YES --> No company filter (sees all data)
    |
    +-- NO ---> Filter by user.companyId
               |
               +-- READ:   query += {companyId: user.companyId}
               +-- CREATE: auto-set companyId = user.companyId
               +-- UPDATE: verify item.companyId == user.companyId
               +-- DELETE: verify item.companyId == user.companyId
```

---

## Fish Analysis Pipeline

```
POST /api/fish/analyze  (multipart/form-data)
    |
    |  Parameters:
    |  - image (required) - Fish image file
    |  - singleFish       - Limit to 1 detection
    |  - scaleReferenceCm - Scale reference for size estimation
    |  - confidence       - Detection confidence threshold
    |  - iou              - Intersection over Union threshold
    |  - caughtBy         - Fisher ID
    |  - caughtByName     - Fisher name
    |
    v
+=================================================+
| STEP 1: Image Processing                        |
+=================================================+
    |
    [await image.read()] --> image_bytes
    |
    [save_upload()] --> saves to uploads/fish/
    |                   returns image_url
    |
    [Image.open().convert("RGB")] --> pil_image
    |                                 (width, height)
    v
+=================================================+
| STEP 2: Load Active Species from DB              |
+=================================================+
    |
    [list_active_species_name_map()]
    |
    |  Query: fish_species WHERE isActive=true
    |  Result: {"bangus": "Bangus", "tilapia": "Tilapia", ...}
    |          (41 species, lowercase key -> canonical name)
    |
    v
+=================================================+
| STEP 3: Fish Detection (YOLO Detector)           |
+=================================================+
    |
    [detect_fish(pil_image, confidence, iou)]
    |
    |  Model: app/models/detector/best.pt
    |  Task:  Object Detection (YOLOv8)
    |  Classes: {0: "Tuna", 1: "Tune"}
    |
    |  Returns per detection:
    |  - species name
    |  - confidence score
    |  - bounding box (x, y, width, height)
    |
    v
[Normalize species names]
    |  "Tune" --> alias --> "tuna" --> species_map --> "Tuna"
    |  "Tuna" --> "tuna" --> species_map --> "Tuna"
    |
    v
[Filter by active species]
    |  Keep only detections where species is in DB
    |
    v
[Any detections remaining?]
    |
    +-- YES --> Skip to STEP 5
    |
    +-- NO --+
             |
             v
+=================================================+
| STEP 4: Fish Classification (YOLO Classifier)    |
|         (Fallback when detector finds nothing)    |
+=================================================+
    |
    [classify_fish(pil_image)]
    |
    |  Model: app/models/classifier/best.pt
    |  Task:  Image Classification (YOLOv8)
    |  Classes: 40 species
    |    0: Bangus         10: Goby
    |    1: Big Head Carp   11: Gold Fish
    |    2: Black Sea Sprat 12: Gourami
    |    3: Black Spotted   13: Grass Carp
    |    4: Catfish         14: Green Spotted Puffer
    |    5: Climbing Perch  15: Hourse Mackerel
    |    6: Fourfinger      16: Indian Carp
    |    7: Freshwater Eel  17: Indo-Pacific Tarpon
    |    8: Gilt-Head Bream 18: Jaguar Gapote
    |    9: Glass Perchlet  19: Janitor Fish
    |    20: Knifefish      30: Sea Bass
    |    21: Long-Snouted   31: Shrimp
    |    22: Mosquito Fish  32: Silver Barb
    |    23: Mudfish        33: Silver Carp
    |    24: Mullet         34: Silver Perch
    |    25: Pangasius      35: Snakehead
    |    26: Perch          36: Striped Red Mullet
    |    27: Red Mullet     37: Tenpounder
    |    28: Red Sea Bream  38: Tilapia
    |    29: Scat Fish      39: Trout
    |
    |  Returns: (species_name, confidence_score)
    |
    v
[Normalize species name via aliases + species_map]
    |
    v
[species == "Unknown" OR confidence == 0.0?]
    |
    +-- YES --> species = "Generic Fish", confidence = 0.5
    |
    +-- NO ---> [species in active species DB?]
                    |
                    +-- NO --> 400 "No fish detected"
                    |
                    +-- YES -> Create full-image detection:
                               {species, confidence, bbox: full image}
    |
    v
+=================================================+
| STEP 5: Weight & Price Estimation                |
+=================================================+
    |
    For each detection:
    |
    +--[get_species_index(species)]
    |      Query fish_species.classIndex by name
    |
    +--[estimate_cm_from_scale(bbox, scaleReferenceCm)]
    |      Calculate length_cm, width_cm from pixel ratio
    |
    +--[estimate_weight(species_index, bbox_w, bbox_h, ...)]
    |      |
    |      +-- Joblib model available?
    |      |     YES --> weight_model.predict([features])
    |      |     NO  --> fallback: width * height * 0.000001
    |      |
    |      v
    |   estimated_weight (kg)
    |
    +--[classify_size(weight)]
    |      weight <= 0.5 kg  --> "Small"
    |      weight <= 1.5 kg  --> "Medium"
    |      weight > 1.5 kg   --> "Large"
    |
    +--[estimate_price(species_index, weight)]
    |      |
    |      +-- Joblib model available?
    |      |     YES --> price_per_kg = price_model.predict()
    |      |             total = price_per_kg * weight
    |      |     NO  --> fallback: weight * 8.50
    |      |
    |      v
    |   estimated_price
    |
    +--[get_species_info(species)]
    |      Returns: scientificName, englishName, localName
    |
    v
    Enriched detection:
    {
      species, confidence, boundingBox,
      estimatedWeight, sizeCategory,
      lengthCm, widthCm, pixelLength,
      keypoints: {mouth, tail},
      scientificName, englishName, localName
    }
    |
    v
+=================================================+
| STEP 6: Build & Save Analysis                    |
+=================================================+
    |
    [build_analysis()]
    |   Aggregate all detections:
    |   - totalEstimatedWeight (sum)
    |   - predictedPrice (sum)
    |   - speciesCount ({species: count})
    |   - Metadata: imageUrl, userId, scannedBy,
    |     caughtBy, caughtByName, timestamps
    |
    v
    [save_analysis()] --> Insert into fish_analyses
    |
    v
    Return JSON response:
    {
      id, imageUrl, userId,
      detections: [...],
      totalEstimatedWeight,
      predictedPrice,
      speciesCount,
      analyzedAt, scannedBy,
      caughtBy, caughtByName
    }
```

---

## Training Samples Flow

```
+=================================================+
| Upload Training Sample                           |
+=================================================+

POST /api/fish/training-samples  (multipart/form-data)
    |
    |  Parameters:
    |  - image (required)     - Fish image
    |  - species (required)   - Species name
    |  - weightKg (required)  - Actual weight in kg
    |  - boundingBox          - Manual annotation
    |  - scaleReferenceCm     - Scale reference
    |  - notes                - Optional notes
    |
    v
[Auth: require_permissions("training-samples:create")]
    |
    v
[save_training_upload(image)] --> uploads/fish-training/
    |
    v
[build_sample_doc()]
    |  Set: uploadedBy, companyId, imageUrl,
    |       species, weightKg, timestamps
    |
    v
[Insert into fish_training_samples collection]
    |
    v
Return sample document


+=================================================+
| Export Training Dataset (Admin Only)              |
+=================================================+

POST /api/fish/training-samples/export
    |
    v
[Auth: require_roles("admin", "super")]
    |
    v
[export_dataset()]
    |
    v
+-- Query all training samples from DB
|
+-- Create export directory:
|     exports/fish-training/{timestamp}/
|
+-- Generate files:
|     |
|     +-- images/          (copy sample images)
|     +-- labels/          (YOLO format annotations)
|     |     classIndex x_center y_center width height
|     |     (normalized 0-1 coordinates)
|     |
|     +-- weight_data.csv  (species_index, bbox_w, bbox_h, weight)
|     +-- price_data.csv   (species_index, weight, price)
|     +-- classes.txt      (one species name per line)
|     +-- manifest.json    (export metadata)
|
v
[AUTO_TRAIN_ON_SAMPLE=true?]
    |
    +-- YES --> Launch auto_train.py subprocess
    |           (retrain models with new data)
    |
    +-- NO ---> Return export path

Return { exportPath, sampleCount, ... }
```

---

## CRUD Operations

### Shared CRUD Router Pattern

```
build_crud_router(collection_name, permissions, allowed_actions)
    |
    Generates these endpoints:
    |
    +-- GET /                     LIST
    |   |
    |   [require_permissions("resource:read")]
    |   [Company isolation filter]
    |   [Query params: limit, offset, any field filter]
    |   [Sort: createdAt DESC]
    |   |
    |   v
    |   {results: [...], total, limit, offset}
    |
    +-- GET /{item_id}            GET ONE
    |   |
    |   [require_permissions("resource:read")]
    |   [Company isolation check]
    |   |
    |   v
    |   {id, ...fields, createdAt, updatedAt}
    |
    +-- POST /                    CREATE
    |   |
    |   [require_permissions("resource:create")]
    |   [Auto-set: companyId, createdAt, updatedAt]
    |   |
    |   v
    |   {id, ...fields, createdAt}
    |
    +-- PATCH /{item_id}          UPDATE
    |   |
    |   [require_permissions("resource:update")]
    |   [Company isolation check]
    |   [Auto-set: updatedAt]
    |   |
    |   v
    |   {id, ...updated fields, updatedAt}
    |
    +-- DELETE /{item_id}         DELETE
        |
        [require_permissions("resource:delete")]
        [Company isolation check]
        |
        v
        {status: "deleted"}


Resources using shared CRUD router:
+---------------------------+---------------------------+
| boats                     | vessels                   |
| vessel-owners             | trips                     |
| expenses                  | fish-sales                |
| catches                   | crew                      |
| profit-sharing-policies   | profit-shares             |
| cash-advances             | forecasts                 |
+---------------------------+---------------------------+
```

---

## Cash Advance Flow

```
+=================================================+
| Cash Advance Lifecycle                           |
+=================================================+

POST /api/cash-advances                    [CREATE]
    |  {amount, purpose, ...}
    |  Permission: cash-advances:create
    v
    Status: "pending"
    |
    +------------------------------------------+
    |                                          |
    v                                          v
PATCH /{id}/approve                   PATCH /{id}/decline
    |                                          |
    |  Permission:                             |  Permission:
    |  cash-advances:approve                   |  cash-advances:decline
    |                                          |
    |  Payload:                                |  Payload:
    |  {notes: "optional"}                     |  {declineReason: "required"}
    |                                          |
    v                                          v
    Status: "approved"                    Status: "declined"
    approvedBy: userId                    declineReason: "..."
    approvedDate: now                     declinedDate: now
    |                                          |
    v                                          v
    [Update cash-advance record]          [Update cash-advance record]
```

---

## Profit Sharing Flow

```
+=================================================+
| Profit Sharing System                            |
+=================================================+

[OWNER / ADMIN creates policy]
    |
    v
POST /api/profit-sharing-policies
    |  Permission: profit-sharing-policies:create
    |  {name, description, rules, ...}
    |
    v
    Stored in profit_sharing_policies collection
    |
    v
[Trips completed, catches recorded, fish sold]
    |
    +-- POST /api/catches        (catch records)
    +-- POST /api/fish-sales     (sale records)
    +-- POST /api/expenses       (trip expenses)
    |
    v
[OWNER generates profit shares]
    |
    v
POST /api/profit-shares
    |  Permission: profit-shares:create
    |  Calculates distribution based on:
    |  - Trip revenue (fish sales)
    |  - Trip expenses
    |  - Policy rules (crew shares, owner shares)
    |
    v
    Stored in profit_shares collection
    |
    v
[CREW views their shares]
    |
    v
GET /api/profit-shares
    |  Permission: profit-shares:read
    |  Filtered by companyId (crew sees own company)
    |
    v
    {results: [{crewMember, share, trip, ...}], total}
```

---

## License Management

```
+=================================================+
| License Lifecycle                                |
+=================================================+

[SUPER ADMIN generates license]
    |
    v
POST /api/licenses/generate
    |  {plan: "trial|standard|premium", maxUsers}
    |
    v
    Generate activation code: XXXX-XXXX-XXXX-XXXX
    Status: "pending"
    Duration: trial=30d, standard/premium=365d
    |
    v
[ADMIN validates license for company]
    |
    v
POST /api/licenses/validate  (public)
    |  {activationCode: "XXXX-XXXX-XXXX-XXXX"}
    |
    v
    [Check: exists? not revoked? not expired? not bound?]
    |
    +-- Invalid --> 400 "Invalid activation code"
    |
    v
    Bind to company
    Status: "active"
    activatedAt: now
    expiresAt: now + durationDays
    |
    v
[Check license status]
    |
    v
GET /api/licenses/status
    |  Returns: plan, maxUsers, status, expiresAt
    |  Auto-expires if past expiresAt
    |
    v
[SUPER ADMIN can revoke]
    |
    v
PATCH /api/licenses/{id}/revoke
    |  Status: "revoked"
    |
    v
[License enforced during registration]
    |
    POST /api/auth/register
        |
        [Count company users]
        |
        [users >= license.maxUsers?]
            |
            +-- YES --> 403 "License user limit reached"
            +-- NO  --> Allow registration
```

---

## Weather Integration

```
+=================================================+
| Weather Endpoints                                |
+=================================================+

GET /api/weather/current?lat=X&lon=Y
    |
    v
[Auth: require logged-in user]
    |
    v
[Call OpenWeatherMap API]
    |  GET api.openweathermap.org/data/2.5/weather
    |
    v
[Parse response + generate fishing insights]
    |
    +-- Sea Conditions (wind speed):
    |     > 10 m/s  --> "Rough"
    |     > 7 m/s   --> "Moderate to Rough"
    |     > 4 m/s   --> "Moderate"
    |     <= 4 m/s  --> "Calm"
    |
    +-- Fishing Advisory:
    |     thunderstorm OR wind > 10  --> "danger"
    |     rain/drizzle OR wind > 7   --> "caution"
    |     wind > 5                   --> "moderate"
    |     otherwise                  --> "favorable"
    |
    v
    Return: {weather, temperature, wind,
             seaCondition, fishingAdvisory}


GET /api/weather/forecast?lat=X&lon=Y
    |
    v
[Call OpenWeatherMap 5-day forecast API]
    |  GET api.openweathermap.org/data/2.5/forecast
    |
    v
[Group by day, summarize conditions]
    |
    v
    Return: {daily: [{date, high, low, condition, advisory}]}
```

---

## Audit Logging

```
+=================================================+
| Audit Trail System                               |
+=================================================+

[Admin action occurs]
    |  e.g., bulk-assign-company, update company,
    |        delete user, modify roles
    |
    v
[log_audit_event()]
    |
    v
    Insert into audit_logs:
    {
      action: "company_assigned",
      entityType: "user",
      entityId: "user_id",
      performedBy: "admin_user_id",
      details: {
        newCompanyId, newCompanyName,
        oldCompanyId, oldCompanyName,
        isBulkOperation: true/false
      },
      metadata: {ip, userAgent},
      timestamp: now
    }
    |
    v
[Queryable by admins]
    |
    +-- GET /api/audit-logs
    |     List all (admin/super only)
    |     Filter: action, entityType, entityId
    |
    +-- GET /api/audit-logs/{id}
    |     Single audit record
    |
    +-- GET /api/audit-logs/user/{userId}
    |     All events for a specific user
    |
    +-- GET /api/audit-logs/company/{companyId}
          All events for a specific company

[Retention: delete_old_audit_logs(days=90)]
```

---

## Data Storage Map

```
+=============================================================+
|                    STORAGE ARCHITECTURE                       |
+=============================================================+

+-------------------------------------------------------------+
|  MongoDB Atlas  (smart_catch @ cluster0.flax6pb.mongodb.net) |
|                                                              |
|  +------------------+  +------------------+                  |
|  | users            |  | roles            |                  |
|  | - email          |  | - name           |                  |
|  | - password (hash)|  | - permissions[]  |                  |
|  | - roleId         |  | - isActive       |                  |
|  | - companyId      |  +------------------+                  |
|  | - sessionId      |                                        |
|  +------------------+  +------------------+                  |
|                        | permissions      |                  |
|  +------------------+  | - name           |                  |
|  | companies        |  | - resource       |                  |
|  | - name           |  | - action         |                  |
|  | - code           |  +------------------+                  |
|  | - isActive       |                                        |
|  +------------------+  +------------------+                  |
|                        | app_licenses     |                  |
|  +------------------+  | - activationCode |                  |
|  | fish_species     |  | - status         |                  |
|  | - name           |  | - maxUsers       |                  |
|  | - classIndex     |  | - plan           |                  |
|  | - scientificName |  | - companyId      |                  |
|  | - englishName    |  +------------------+                  |
|  | - localName      |                                        |
|  | - isActive       |  +------------------+                  |
|  +------------------+  | audit_logs       |                  |
|                        | - action         |                  |
|  +------------------+  | - entityType     |                  |
|  | fish_analyses    |  | - performedBy    |                  |
|  | - imageUrl       |  | - details{}      |                  |
|  | - detections[]   |  | - timestamp      |                  |
|  | - totalWeight    |  +------------------+                  |
|  | - predictedPrice |                                        |
|  | - speciesCount{} |  +------------------+                  |
|  | - scannedBy      |  | fish_models      |                  |
|  | - caughtBy       |  | - modelType      |                  |
|  +------------------+  | - version        |                  |
|                        | - isActive       |                  |
|  +--------------------+| - status         |                  |
|  | fish_training_     |+------------------+                  |
|  |   samples          |                                      |
|  | - species          |  CRUD Collections:                   |
|  | - weightKg         |  +----------------+                  |
|  | - imageUrl         |  | boats          |                  |
|  | - uploadedBy       |  | vessels        |                  |
|  | - companyId        |  | vessel_owners  |                  |
|  +--------------------+  | trips          |                  |
|                          | catches        |                  |
|                          | fish_sales     |                  |
|                          | expenses       |                  |
|                          | crew           |                  |
|                          | profit_shares  |                  |
|                          | profit_sharing |                  |
|                          |   _policies    |                  |
|                          | cash_advances  |                  |
|                          | forecasts      |                  |
|                          +----------------+                  |
+-------------------------------------------------------------+

+-------------------------------------------------------------+
|  Local Filesystem                                            |
|                                                              |
|  app/models/                    (Pre-trained ML Models)      |
|  +-- detector/best.pt          YOLOv8 detection    (6.0 MB) |
|  +-- classifier/best.pt        YOLOv8 classify     (3.0 MB) |
|  +-- weight/weight_model.joblib Scikit-learn regr.  (77 KB) |
|  +-- price/price_model.joblib   Scikit-learn regr.  (77 KB) |
|                                                              |
|  uploads/                       (User Uploads)               |
|  +-- fish/                      Analysis images    (39 files)|
|  +-- fish-training/             Training samples   (36 files)|
|  +-- profiles/                  Profile avatars              |
|                                                              |
|  exports/                       (Generated Exports)          |
|  +-- fish-training/{timestamp}/ Exported datasets            |
|      +-- images/                Sample images                |
|      +-- labels/                YOLO annotations             |
|      +-- weight_data.csv        Weight training data         |
|      +-- price_data.csv         Price training data          |
|      +-- classes.txt            Class names                  |
|      +-- manifest.json          Export metadata              |
+-------------------------------------------------------------+
```

---

## Complete API Route Map

```
/                                    GET    Health check
/api
  /auth
    /register                        POST   Register new user
    /login                           POST   Login
    /refresh                         POST   Refresh access token
    /logout                          POST   Logout (revoke session)
  /profile
    /                                GET    Get my profile
    /                                PATCH  Update my profile
    /avatar                          POST   Upload profile avatar
    /change-password                 POST   Change password
  /users
    /                                GET    List users
    /                                POST   Create user (super)
    /{id}                            GET    Get user
    /{id}                            PATCH  Update user
    /{id}                            DELETE Delete user
    /bulk-assign-company             POST   Bulk assign company
  /roles
    /                                GET    List roles
    /                                POST   Create role
    /{id}                            GET    Get role
    /{id}                            PATCH  Update role
    /{id}                            DELETE Delete role
    /{id}/permissions                POST   Add permissions to role
    /{id}/permissions                DELETE Remove permissions
  /permissions
    /                                GET    List permissions
    /                                POST   Create permission
    /{id}                            PATCH  Update permission
    /{id}                            DELETE Delete permission
  /companies
    /                                GET    List companies
    /                                POST   Create company
    /{id}                            GET    Get company
    /{id}                            PATCH  Update company
    /{id}                            DELETE Delete company
  /fish
    /analyze                         POST   Analyze fish image (AI)
    /diagnostic                      GET    Model & species diagnostic
    /analytics                       GET    Analysis statistics
    /analysis-history                GET    User's analysis history
    /models
      /                              GET    List fish models
      /                              POST   Create model record
      /active                        GET    Get active model by type
      /upload                        POST   Upload model file
      /{id}                          PATCH  Update model
      /{id}/activate                 PATCH  Activate model
      /{id}                          DELETE Soft-delete model
    /species
      /                              GET    List all species (admin)
      /active                        GET    List active species
      /                              POST   Create species
      /{id}                          PATCH  Update species
      /{id}                          DELETE Delete species
    /training-samples
      /                              GET    List training samples
      /                              POST   Upload training sample
      /mine                          GET    My training samples
      /export                        POST   Export dataset (admin)
      /{id}                          DELETE Delete sample
  /licenses
    /status                          GET    Check license status
    /generate                        POST   Generate license (super)
    /validate                        POST   Validate activation code
    /                                GET    List all licenses (super)
    /{id}/revoke                     PATCH  Revoke license (super)
  /weather
    /current                         GET    Current weather + advisory
    /forecast                        GET    5-day forecast
  /audit-logs
    /                                GET    List audit logs
    /{id}                            GET    Get audit log
    /user/{userId}                   GET    User audit history
    /company/{companyId}             GET    Company audit history
  /cash-advances
    /                                GET    List (CRUD)
    /                                POST   Create (CRUD)
    /{id}                            GET    Get (CRUD)
    /{id}                            PATCH  Update (CRUD)
    /{id}                            DELETE Delete (CRUD)
    /{id}/approve                    PATCH  Approve advance
    /{id}/decline                    PATCH  Decline advance
  /boats                             CRUD   Boat management
  /vessels                           CRUD   Vessel management
  /vessel-owners                     CRUD   Vessel owner records
  /trips                             CRUD   Fishing trips
  /expenses                          CRUD   Trip expenses
  /fish-sales                        CRUD   Fish sale records
  /catches                           CRUD   Catch records
  /crew                              CRUD   Crew management
  /profit-sharing-policies           CRUD   Sharing policies
  /profit-shares                     CRUD   Profit share records
  /forecasts                         CRUD   Forecast records
```

---

*Generated from codebase analysis on 2026-03-11*
*Framework: FastAPI + Motor (async MongoDB) + YOLOv8 + Scikit-learn*
