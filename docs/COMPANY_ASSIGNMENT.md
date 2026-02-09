# Company Assignment Feature Documentation

## Overview
The profit-sharing system implements a multi-tenant architecture where super admins can assign companies to admin users, and admin users can manage users within their assigned company.

## User Roles

### Super Admin (Role: "super")
- **Capabilities:**
  - Full access to all companies and users across the system
  - Can create, update, and delete any company
  - Can assign any company to any user
  - Can manage users across all companies
  - No company restriction

### Company Admin (Role: "admin")
- **Capabilities:**
  - Limited to their assigned company (via `companyId` field)
  - Can only view and manage users within their own company
  - Can only update their own company information
  - Cannot assign users to other companies
  - Cannot create new companies

### Other Roles
- **User, Broker, Owner, Crew**: Have varying permissions but no administrative capabilities for company assignment

## Current Implementation

### Backend API Endpoints

#### 1. User Management Endpoints

**File:** `profit_sharing_api_fastapi/app/api/v1/users/routes.py`

##### GET `/users`
- Lists all users with pagination
- **Super Admin:** Returns all users
- **Company Admin:** Returns only users from their company
- **Filtering:** Supports search and pending user filtering
- **Permission Required:** `user:read`

##### GET `/users/{user_id}`
- Retrieves a specific user
- **Super Admin:** Can view any user
- **Company Admin:** Can only view users from their company
- **Permission Required:** `user:read`

##### POST `/users`
- Creates a new user
- **Super Admin:** Can assign any company to the user
- **Company Admin:** Can only assign users to their own company
- **Restrictions:**
  - Cannot assign "admin" or "super" roles
  - Admin users must have a `companyId` set
- **Permission Required:** `user:create`

**Key Logic:**
```python
# Lines 115-121 in routes.py
if is_company_admin and not is_super:
    company_id = _company_id_value(user)
    object_id = _company_object_id(company_id)
    if not object_id:
        raise HTTPException(status_code=403, detail="Company not set for admin")
    payload["companyId"] = object_id
```

##### PATCH `/users/{user_id}`
- Updates an existing user
- **Super Admin:** Can update any user and change their company
- **Company Admin:**
  - Can only update users from their own company
  - Cannot change the `companyId` field (line 175)
- **Special Feature:** When admin approves a user (`companyApproved = true`), user role is automatically set to "crew"
- **Permission Required:** `user:update`

##### DELETE `/users/{user_id}`
- Deletes a user
- **Super Admin:** Can delete any user
- **Company Admin:** Can only delete users from their company
- **Permission Required:** `user:delete`

#### 2. Company Management Endpoints

**File:** `profit_sharing_api_fastapi/app/api/v1/companies/routes.py`

##### GET `/companies`
- Lists all companies with pagination
- **Super Admin:** Returns all companies
- **Company Admin:** Returns only their own company
- **Filtering:** Supports search by company name
- **Permission Required:** `companies:read`

##### POST `/companies`
- Creates a new company
- **Super Admin Only:** Company admins cannot create new companies
- **Upsert Logic:** If company with same name exists, updates it instead
- **Permission Required:** `companies:create`

##### PATCH `/companies/{company_id}`
- Updates a company
- **Super Admin:** Can update any company
- **Company Admin:** Can only update their own company
- **Permission Required:** `companies:update`

##### DELETE `/companies/{company_id}`
- Deletes a company
- **Super Admin:** Can delete any company
- **Company Admin:** Can only delete their own company (if allowed by permissions)
- **Permission Required:** `companies:delete`

### Database Schema

#### Users Collection
```javascript
{
  _id: ObjectId,
  email: String,
  password: String (hashed),
  firstName: String,
  lastName: String,
  role: ObjectId,                   // Reference to roles collection
  companyId: ObjectId (optional),   // Reference to companies collection
  companyApproved: Boolean,          // Approval status
  companyName: String (optional),    // Denormalized for quick access
  companyAddress: String (optional),
  companyPhone: String (optional),
  companyTaxId: String (optional),
  sessionId: String,
  refreshToken: String,
  refreshTokenExpiry: Date,
  createdAt: Date,
  updatedAt: Date
}
```

#### Companies Collection
```javascript
{
  _id: ObjectId,
  companyName: String,
  companyCode: String (optional),
  companyAddress: String (optional),
  companyPhone: String (optional),
  companyTaxId: String (optional),
  createdAt: Date,
  updatedAt: Date
}
```

### Authorization Implementation

#### Role Checking Helper Functions
```python
async def _get_role_flags(user: dict[str, Any]) -> tuple[str, bool, bool]:
    role_name = (await _get_role_name(user)).strip().lower()
    is_super = role_name in SUPER_ROLE_NAMES
    is_company_admin = role_name in ADMIN_ROLE_NAMES
    return role_name, is_super, is_company_admin
```

**Canonical Role Names:** `super | admin | broker | owner | crew | user`

**Super Role Names:** `{"super"}`
**Admin Role Names:** `{"admin"}`

#### Company ID Extraction
```python
def _company_id_value(data: dict[str, Any]) -> str | None:
    company_id = data.get("companyId")
    return str(company_id) if company_id else None
```

### Registration Flow

**File:** `profit_sharing_api_fastapi/app/api/v1/auth/routes.py`

1. User registers with optional `companyCode`
2. If `companyCode` provided:
   - System looks up company by code
   - User is assigned to that company
   - `companyApproved` is set to `False` (pending approval)
3. Admin must approve the user for full access
4. On approval, user role is automatically set to "crew"

## Frontend Models

### User Model
**File:** `profit_sharing/lib/models/user.dart`

```dart
class User {
  final String id;
  final String email;
  final String? firstName;
  final String? lastName;
  final String? roleId;
  final String? roleName;
  final List<String>? permissions;
  final String? companyId;           // Company reference
  final bool companyApproved;         // Approval status
  final String? companyName;
  final String? companyAddress;
  final String? companyPhone;
  final String? companyTaxId;
}
```

### Company Model
**File:** `profit_sharing/lib/models/company.dart`

```dart
class Company {
  final String id;
  final String name;
  final String? code;
  final String? address;
  final String? phone;
  final String? taxId;
}
```

## Security Considerations

### Multi-Tenant Isolation
- Company admins are strictly isolated to their assigned company
- All list operations are filtered by `companyId` for company admins
- All CRUD operations validate company ownership before proceeding

### Permission Guards
- All endpoints are protected by `require_permissions` dependency
- Permissions are role-based and defined in the `roles_permissions` seeder
- JWT tokens include `roleId` and `sessionId` for validation

### Access Control Patterns

#### Company-Scoped Admin Access
```python
if is_company_admin and not is_super:
    company_id = _company_id_value(user)
    if not company_id or company_id != target_company_id:
        raise HTTPException(status_code=403, detail="Forbidden")
```

#### Query Filtering
```python
if is_company_admin and not is_super:
    company_id = _company_id_value(user)
    object_id = _company_object_id(company_id)
    if not object_id:
        return {"results": [], "total": 0}
    query["companyId"] = object_id
```

## Workflow Examples

### Scenario 1: Super Admin Assigns Company to Admin User

1. Super admin logs in
2. Super admin creates or selects an admin user
3. Super admin sets `companyId` field to desired company
4. Admin user can now manage users within that company

**API Call:**
```http
PATCH /users/{user_id}
Authorization: Bearer {super_admin_token}
Content-Type: application/json

{
  "companyId": "507f1f77bcf86cd799439011",
  "roleId": "507f191e810c19729de860ea"
}
```

### Scenario 2: Company Admin Creates User

1. Company admin logs in (already assigned to company X)
2. Company admin creates new user
3. User is automatically assigned to company X
4. Admin cannot assign user to different company

**API Call:**
```http
POST /users
Authorization: Bearer {company_admin_token}
Content-Type: application/json

{
  "email": "newuser@example.com",
  "password": "SecurePass123!",
  "firstName": "John",
  "lastName": "Doe",
  "roleId": "507f191e810c19729de860ea"
}
```

### Scenario 3: User Self-Registration with Company Code

1. User registers via `/auth/register`
2. Provides company code (e.g., "BLUE" or "SUN")
3. System assigns user to company with `companyApproved = false`
4. Company admin reviews pending users
5. Admin approves user via `PATCH /users/{user_id}` with `{"companyApproved": true}`
6. User role is auto-set to "crew" and gains access

## Configuration

### Default Companies
**File:** `profit_sharing_api_fastapi/app/seeders/companies.py`

- **Blue Ocean Co** (Code: BLUE)
- **Sunrise Fisheries** (Code: SUN)

### Role Permissions
**File:** `profit_sharing_api_fastapi/app/seeders/roles_permissions.py`

- Admin and Super roles have all permissions
- Super role: unrestricted global access
- Admin role: company-scoped access

## API Response Examples

### List Users (Company Admin)
```json
{
  "results": [
    {
      "id": "507f1f77bcf86cd799439011",
      "email": "user@company.com",
      "firstName": "John",
      "lastName": "Doe",
      "roleName": "crew",
      "companyId": "507f191e810c19729de860ea",
      "companyName": "Blue Ocean Co",
      "companyApproved": true
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### List Companies (Company Admin)
```json
{
  "results": [
    {
      "id": "507f191e810c19729de860ea",
      "companyName": "Blue Ocean Co",
      "companyCode": "BLUE",
      "companyAddress": "123 Ocean Drive",
      "companyPhone": "+1234567890",
      "companyTaxId": "TAX123"
    }
  ],
  "total": 1,
  "limit": 200,
  "offset": 0
}
```

## Code References

### Key Files
- **User Routes:** `profit_sharing_api_fastapi/app/api/v1/users/routes.py`
  - Lines 47-51: Role flag checking
  - Lines 68-86: User listing with company filtering
  - Lines 105-156: User creation with company assignment
  - Lines 159-206: User update with company validation

- **Company Routes:** `profit_sharing_api_fastapi/app/api/v1/companies/routes.py`
  - Lines 34-38: Role flag checking
  - Lines 46-75: Company listing with filtering
  - Lines 78-122: Company creation (super admin only)

- **Auth Routes:** `profit_sharing_api_fastapi/app/api/v1/auth/routes.py`
  - Registration with company code support

- **User Repository:** `profit_sharing_api_fastapi/app/infrastructure/users/repository.py`
  - User CRUD operations with company handling

- **Frontend Models:**
  - `profit_sharing/lib/models/user.dart`
  - `profit_sharing/lib/models/company.dart`

## Future Enhancements
- Bulk company assignment for multiple users
- Audit logging for company assignments
- UI for company assignment management
- Company assignment history tracking
- Role-based company access analytics
