# Nahda Syria fleet frontend

This folder is the static frontend. Existing Supabase authentication, tenant isolation, trip history, and driver API are retained. No passwords, driver tokens, user records, or service-role secrets are included.

Render settings:
- Branch: nahda-fleet-hosting
- Build command: true
- Publish path: nahda-fleet
- Environment: SKIP_INSTALL_DEPS=true
- No SPA fallback: index.html and driver.html are real pages.

Supabase JS is vendored at version 2.117.2. Driver links use the serving origin, so links generated here remain on this host. Previously sent links keep their old host; generate and send fresh links from the new deployment.
