# B03 — Authentication, RBAC, MFA & Public Alert Access

## Status
DONE — implementation and automated acceptance tests complete.

## Objective
Provide secure authentication and least-privilege authorization for ResQShield while keeping public emergency warnings accessible without login.

## Implemented

### Authentication
- Argon2 password hashing
- Signed JWT Bearer access tokens
- Configurable token expiry
- Invalid/expired token rejection

### MFA
- TOTP-based MFA support
- Sensitive operations require an MFA-verified token
- MFA-sensitive permissions currently include:
  - alert approval
  - threshold updates
  - user administration
  - system administration

### Canonical Roles
1. Citizen
2. Field Responder
3. District Officer
4. NDRF Control Room
5. SDM / Collector
6. PWD Engineer
7. Police
8. Shelter Operator
9. Health Department
10. System Admin
11. Research

### Public Access
`GET /api/v1/public/alerts`

This endpoint intentionally requires no authentication so emergency public warnings remain accessible.

### Protected Authentication Endpoint
`GET /api/v1/auth/me`

Requires a valid Bearer JWT.

### Least-Privilege Examples
- PWD Engineer may update road/bridge state but cannot administer users.
- Police may perform permitted road operations but cannot modify thresholds.
- Shelter Operator may update shelter status but cannot approve alerts.
- Health Department may update permitted medical status but cannot administer users.
- District Officer may approve alerts only after MFA verification.
- System Admin sensitive administration requires MFA.

## Persistence Changes
Alembic revision:

`0002_b03_auth_fields`

Adds to `users`:
- `password_hash`
- `mfa_secret`
- `mfa_enabled`

Migration chain:

`0001_initial_schema -> 0002_b03_auth_fields`

## Representative Development Accounts
`backend/app/seed/seed_auth_accounts.py`

Contains development fixtures for all 11 canonical platform roles.

These accounts are development/demo fixtures only and must not be used as production credentials.

## Automated Acceptance Tests
File:

`backend/tests/test_b03_auth_rbac.py`

B03-specific result:

`15 passed`

Full repository regression result:

`189 passed, 13 skipped, 0 failed`

## Verified Acceptance Cases
- Anonymous -> public alert: PASS
- Anonymous -> protected endpoint: rejected with 401
- Valid JWT -> authenticated principal: PASS
- PWD -> road operation: PASS
- PWD -> user administration: rejected with 403
- Police -> road operation: PASS
- Police -> threshold update: rejected with 403
- Shelter Operator -> shelter update: PASS
- Shelter Operator -> alert approval: rejected with 403
- Health Department -> medical update: PASS
- Health Department -> user administration: rejected with 403
- District Officer without MFA -> alert approval: rejected with 403
- District Officer with MFA -> alert approval: PASS
- System Admin without MFA -> sensitive admin: rejected with 403
- System Admin with MFA -> sensitive admin: PASS

## Security Notes
- Passwords are never stored in plaintext.
- JWT signing key is configurable through environment variables.
- Production must supply a strong independent JWT secret.
- Public-alert access is intentionally separate from privileged publication controls.
- MFA secrets and development credentials must not be used as production credentials.

## B03 Deliverables
- Auth service/API: COMPLETE
- JWT authentication: COMPLETE
- RBAC middleware/dependencies: COMPLETE
- Detailed role-permission matrix: COMPLETE
- MFA-sensitive operation enforcement: COMPLETE
- Anonymous public-alert access: COMPLETE
- Representative accounts: COMPLETE
- Alembic persistence migration: COMPLETE
- Least-privilege acceptance tests: COMPLETE
- Regression verification: COMPLETE
