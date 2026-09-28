# Nahda Syria fleet frontend

This folder is the static frontend. Existing Supabase authentication, tenant isolation, trip history, and driver API are retained. No passwords, driver tokens, user records, or service-role secrets are included.

Render settings:
- Branch: nahda-fleet-hosting
- Build command: true
- Publish path: nahda-fleet
- Environment: SKIP_INSTALL_DEPS=true
- No SPA fallback: index.html and driver.html are real pages.

Supabase JS is vendored at version 2.117.2. Driver links use the serving origin, so links generated here remain on this host. Previously sent links keep their old host; generate and send fresh links from the new deployment.


## Khotwati driver accounts
The UI brand is خطواتي. Developer contact is a public tel: link authorized by the owner.
Drivers sign in through /driver.html with provisioned Supabase Auth credentials. The browser stores a refreshable session under khotwati-driver-session (not a hardware identifier or a plaintext password). Logging out or clearing browser data requires signing in again. Tracking remains manual.
Company admins use the trip's driver-account dialog to create or assign an existing company driver and reset passwords. Authorization checks the current user, active driver/company and assigned open trip on every driver request. Legacy unauthenticated driver tokens no longer grant access.
Backend source and the applied additive schema change are in ../fleet-backend, outside the public publish directory. fleet_drivers is server-only, RLS enabled, without browser grants.
