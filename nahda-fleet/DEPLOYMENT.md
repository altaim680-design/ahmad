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
Drivers sign in through /driver.html with provisioned Supabase Auth credentials. The browser stores a refreshable session under khotwati-driver-session (not a hardware identifier or a plaintext password). Logging out or clearing browser data requires signing in again. Tracking can be started explicitly by the driver while the page remains visible.
Company admins use the trip's driver-account dialog to create or assign an existing company driver and reset passwords. Authorization checks the current user, active driver/company and assigned open trip on every driver request. Legacy unauthenticated driver tokens no longer grant access.
Backend source and the applied additive schema change are in ../fleet-backend, outside the public publish directory. fleet_drivers is server-only, RLS enabled, without browser grants.

Live tracking uses watchPosition and fresh-position polling, throttled to one upload per 30 seconds. Hidden pages pause and resume on visibility; closing the page stops tracking. No background guarantee, no hardware ID, no stored location queue. Abort signals cancel pending work on stop or trip change. Wake Lock is best effort. Office refreshes every 30 seconds. Tests: node tests/live-tracking.cjs and node tests/driver-live-integration.cjs (simulated GPS and DOM; physical phone behavior still needs device testing).

Localization: Arabic (RTL), English and Turkish (LTR). Language preference uses localStorage and optional ?lang=ar/en/tr. Switching language reloads the page and stops foreground tracking, which the driver can restart. Static interface and source-authored dynamic text are translated; user-provided names, notes, and database status values remain untouched. Reports and WhatsApp drafts use the selected language.

Company memberships are read-only for fleet operations. All staff Edge API operations require super_admin; driver authentication and updates remain separately scoped. Companies retain own-data reads, reports, exports, and sharing. A company user may change their own account password but cannot manage any driver account.

## Trip barcodes

Apply `fleet-backend/trip-barcodes.sql` once before deploying the barcode UI. It backfills existing trips and generates unique KW + 10-digit identifiers on new trips. The existing security-invoker view exposes the identifier under the same company permissions. Barcodes are identifiers, not authentication secrets. Search requires login and includes closed trips visible to that account. A keyboard-mode barcode reader can fill the barcode search field; camera scanning is available through the Scan with camera button.

`barcode-code128.js` vendors JsBarcode 3.12.1 (CODE128 build), with its MIT license in `barcode-LICENSE.txt` and SHA384 integrity pinned in index.html. `trip-barcode.js` renders encoded data as local SVG with no third-party barcode service. Barcode printing uses the existing print dialog and CSS; SVG download is also available. Tests include independent symbol/checksum decoding through ReportLab, but no physical printer/scanner/mobile-device validation has been performed.

## Camera barcode search

`barcode-reader.js` vendors @zxing/library 0.21.3 under its bundled Apache-2.0 license, with SHA384 integrity. `camera-barcode.js` acquires video-only camera access after the Scan button, prefers the rear camera, and decodes CODE128 locally (no frames uploaded). Two valid matching trip codes trigger a permission-scoped search. Closing/cancelling the dialog, switching page/modal, hiding the page or signing out stops tracks; late camera permission resolutions are also released. The existing manual/scanner search remains available. Tests cover actual pixel decoding, denied permission, pending-request cancellation and stream shutdown. Physical device compatibility still requires testing.

## Private trip PDF attachments and scan sound

Apply `fleet-backend/trip-files.sql` once, then deploy the updated Edge API before the frontend. The private `fleet-trip-files` bucket restricts MIME type to application/pdf and size to 10 MiB. Administrators upload/delete; company members may read their own company's records and obtain 60-second signed URLs. Original filenames (including Arabic) live in an RLS-protected metadata table; storage uses random UUID paths. Client validation checks extension, size and PDF header; this is not an antivirus/content sanitization service. Failed metadata saves attempt storage cleanup. Company deletion removes metadata transactionally, then attempts blob cleanup with a warning on failure. Signed URLs already issued remain valid for up to 60 seconds; downloaded copies cannot be revoked.

`scan-sound.js` unlocks Web Audio on the camera button gesture and plays a short tone when a trip barcode is successfully recognized. Unsupported/muted audio never blocks search.

## Driver web push reminders

Apply `fleet-backend/driver-push.sql`, provision a P-256 VAPID key pair and a cryptographically random cron token into the service-only `fleet_push_config` table, and deploy `fleet-backend/fleet-push.ts` as `fleet-push` with verify_jwt=false (the handler verifies Auth tokens or its cron secret). Production credentials are NOT in this repository. Back up this private configuration securely to retain subscriptions during recovery.

Drivers explicitly enable browser notifications. iPhone/iPad requires a Home Screen web app on iOS/iPadOS 16.4+; installing creates a separate app context that may require signing in again. Logout unsubscribes this browser. Notification clicks open an authorized driver trip and never start GPS automatically. The worker does not cache fleet data.

Administrators can send manually (5-minute minimum cooldown) or enable 30/60/120-minute stale-location reminders per trip. Defaults OFF. pg_cron checks every 15 minutes; automatic reminders run 08:00–20:00 Asia/Damascus for active companies/drivers and open trips. Atomic claims suppress overlapping sends. Batch size is 25 eligible trips, at most 5 devices per driver. Dead subscriptions are removed on provider 404/410; failed sends remain subject to cooldown. Provider acceptance is not proof of delivery. Endpoint hosts are allowlisted; private subscription material and VAPID secrets have no browser grants. web-push 3.6.7 is pinned. Actual device delivery still needs a consenting driver's enable-and-test flow.
