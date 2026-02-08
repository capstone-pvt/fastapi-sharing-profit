# Audit Logging Integration for User Routes

## Changes Required

### 1. Import Statement (Already Added)
```python
from app.infrastructure.audit.repository import log_company_assignment
```

### 2. Update the update_user function (lines 160-207)

Add this code block after line 204 (`doc = await repo_update_user(user_id, update_payload)`) and before line 207 (`return doc`):

```python
    # Log company assignment if company was changed
    if is_admin and payload.get("companyId"):
        old_company_id = _company_id_value(target_user)
        new_company_id = _company_id_value(doc)

        if old_company_id != new_company_id:
            await log_company_assignment(
                user_id=user_id,
                company_id=new_company_id,
                company_name=doc.get("companyName", ""),
                performed_by_user_id=user.get("id") or str(user.get("_id")),
                old_company_id=old_company_id,
                old_company_name=target_user.get("companyName"),
                is_bulk=False
            )
```

### 3. Update the bulk_assign_company function (lines 228-313)

Replace the section where we append to `updated_users` (around lines 290-296) with:

```python
            doc = await repo_update_user(user_id, update_payload)
            if doc:
                success_count += 1
                updated_users.append({
                    "userId": user_id,
                    "email": doc.get("email"),
                    "companyName": doc.get("companyName")
                })

                # Log company assignment
                old_company_id = _company_id_value(target_user)
                await log_company_assignment(
                    user_id=user_id,
                    company_id=company_id,
                    company_name=company.get("companyName", ""),
                    performed_by_user_id=user.get("id") or str(user.get("_id")),
                    old_company_id=old_company_id,
                    old_company_name=target_user.get("companyName"),
                    is_bulk=True
                )
            else:
                failed_users.append({"userId": user_id, "reason": "Update failed"})
```

## Database Index Creation

Run this command in MongoDB to create indexes for audit logs:

```javascript
db.audit_logs.createIndex({ "timestamp": -1 })
db.audit_logs.createIndex({ "entityType": 1, "entityId": 1 })
db.audit_logs.createIndex({ "performedBy": 1 })
db.audit_logs.createIndex({ "action": 1 })
```

## Registering the Audit Routes

Add this to the main API router file (usually `app/api/v1/__init__.py` or `app/main.py`):

```python
from app.api.v1.audit.routes import router as audit_router

# Add to the API router
app.include_router(audit_router, prefix="/v1")
```

## Testing the Audit Logging

1. Update a user's company assignment
2. Check the audit_logs collection in MongoDB
3. Use the GET /v1/audit-logs endpoint to view logs
4. Use GET /v1/audit-logs/user/{user_id} to see user-specific history
