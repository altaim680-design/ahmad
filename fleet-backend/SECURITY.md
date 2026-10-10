# Khotwati security hardening

Applied 2026-09-29:
- Browser CSP: local scripts/styles only, no inline JS or eval, connection allowlist, objects/base URI disabled, upgrade insecure requests. Meta CSP is used; frame-ancestors cannot be enforced by meta. No clickjacking-header claim is made.
- Vendored Supabase SDK pinned and checked using SHA-384 subresource integrity.
- Edge origin allowlist for the Render origin. Origin is defense in depth, not authentication: clients without an Origin still require a valid user token.
- Strict JSON method/body validation with a 16 KB streaming size limit. Initial admin bootstrap endpoint removed.
- Atomic PostgreSQL fixed-window limit: 120 authenticated fleet API requests per user per minute. This is separate from Supabase Auth login throttling and does not cover direct read-only PostgREST calls.
- Audit records for sensitive staff actions and denials: actor UUID, action, response status and supplied trip/company UUIDs. No passwords, tokens or location payloads are recorded. Audit writes are best effort and errors are logged server-side; this is not an immutable external audit service.
- Rate-limit and audit tables: RLS enabled and browser privileges revoked. Rate-limit RPC is service-role only, security invoker.
- Existing current-user verification, company isolation and root-only administrative mutations preserved. Driver requests remain scoped to an active assigned trip and company.

Encryption and limits:
- HTTPS is supplied by Render and Supabase. Passwords are handled by Supabase Auth hashing, not reversible client-side encryption. No new end-to-end encryption layer was added. Provider disk encryption was not independently audited.
- Driver persistent sessions stay in browser storage to honor the remember-login requirement; CSP reduces but does not eliminate the effect of an XSS vulnerability or stolen device.
- User-selected minimum password length remains 6, with numeric-only passwords allowed. This is materially weaker than a long unique password. MFA and leaked-password protection are not enabled by this change. Supabase advisor continues to report leaked-password protection disabled: https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection
- No claim of total protection, penetration-test certification, or DDoS mitigation beyond hosting/provider controls.

Verification: security.cjs request-gate tests, company-readonly.cjs authorization tests, live tracking/UI localization regression tests, transactional real-database rate-limit test, privilege inspection, and published page/API checks.

## Owner controls

Apply `owner-controls.sql` before deploying this API version. The original owner's membership has `is_owner=true` (unique). Browser roles cannot update memberships. Only that active owner may suspend/reactivate other general administrators or permanently delete a company. Self/owner suspension is rejected. Inactive memberships fail both API and RLS checks; the office UI signs out at its next membership refresh.

Company deletion requires its exact name and runs the company/trip/location/access-row deletion in one database transaction, using a service-role-only SECURITY INVOKER RPC that rechecks ownership. Associated Auth users are subsequently removed through the Admin API; a cleanup warning is returned if any fail, while their fleet access has already been removed. Security audit records remain. Existing exported reports are not erased.


## Company shipment access and unified sign-in

All accounts sign in at `/` using the persistent `khotwati-driver-session` storage key. `resolveAccount` validates the authenticated user, active membership/driver and active company before routing. Existing company_admin accounts are company managers with company-wide read-only visibility. New company_staff accounts see only trips assigned through assigned_member_id. Only global administrators manage accounts and assignment. Assignment has a composite company/member foreign key.

`fleet_private.can_trip` constrains trips, updates, the security-invoker status view, reports, PDF metadata and Storage reads. Driver PDF listing and 60-second signed open/download URLs use fleet-api with active driver/company and own open trip checks, including file-to-trip validation. Drivers cannot upload/delete files. Company staff cannot mutate trips or account credentials.

Apply company-staff.sql before deploying the API/UI. Existing trips remain unassigned and visible to managers until an administrator assigns a shipment owner. Tests: company-staff-rls.sql is rolled back after real RLS checks; account-routing-files.cjs verifies driver file authorization and routing. Physical phone download behavior still requires a device test.
