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
