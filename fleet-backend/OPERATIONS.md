# Shipment operations — 2026-10-15

Apply operations.sql after the existing fleet schema. Deploy fleet-workspace.ts as fleet-workspace and fleet-api.ts as fleet-api. Both verify bearer tokens with auth.getUser and enforce active accounts and company permissions internally; gateway verify_jwt remains false for the existing publishable-key setup.

## User entry points
- Office: «ملفات الشحنات» groups trucks; «مساحة الشحنة» opens conversation, required documents, issues and operations.
- Root administrators create groups, link trips, configure document templates, change vehicles/drivers, and edit company identity from the company card.
- Company managers see company trips. Assigned staff see their own trips only. Both can converse, resolve issues and hand over a trip to an active company colleague with a required summary. Handover checks the expected current assignee and records history atomically.
- Drivers access only their current open trips, their conversation/documents/history, and «عندي مشكلة». Existing PDF controls still open/download trip documents.
- Report retains WhatsApp text and CSV and adds branded print layout, totals and explicit stale-location indicators. Browser Print / Save as PDF uses A4 landscape.

## Limits and verification
- Images/audio up to 10 MiB, private bucket, expiring signed downloads. Microphone requires browser permission; recording stops after two minutes or when page becomes hidden. Conversation refreshes every 20 seconds while visible.
- Shipment document templates are additive; replacing a template does not delete existing requirements or PDFs.
- Conversation and transfer RPCs recheck active membership and assignment under a trip lock. RLS protects direct reads; service-only media has no client grants.
- Schema transaction tests use synthetic accounts and rollback. API tests cover cross-company/trip denial, driver restrictions, root-only mutations, inactive accounts and media/file scoping. Existing account, PDF, tracking and UI regression tests pass.
- Physical phone microphone/camera behavior and print pagination across browser engines still require device acceptance testing.
- Security advisor: service-only tables intentionally have no client policies. Existing leaked-password protection warning remains; enable in Supabase Auth if supported by plan.

## Fleet map — 2026-10-18
`/fleet-map.html` uses the shared account session and resolves an active office role before querying `fleet_trip_status` through the authenticated client. The security-invoker view and existing trip/update RLS enforce company and staff assignment. All accessible trips are shown by default; filters cover company, search, open/closed trips and GPS freshness. Null/out-of-range coordinates stay in the list and are never guessed from place text. Coincident points share one marker with all trip details. Locations older than 15 minutes are explicitly marked; closed trips are grey. Polling is every 30 seconds while visible; failed refreshes retain the last successful fetch timestamp and show an error. Sign-out clears markers and rows.

Leaflet 1.9.4 is vendored with BSD license and verified official SHA-256. OpenStreetMap tiles load on demand with visible attribution and origin referrer, native browser caching and no prefetch/offline tile download. No driver identity is sent to the tile provider. Map imagery is a best-effort third-party service; a tile error keeps the accessible vehicle list available. The map opens trip workspaces through the existing scoped endpoint. Existing enterprise, multi-stop, proof-of-delivery, notification and report functionality is retained.

## Document scanner — 2026-10-23
A shared document-scanner dialog is available from the office, driver, map, enterprise and command-center headers. Native image capture/file input opens the phone camera or gallery. Processing remains client-side: image orientation, a four-corner perspective correction with draggable handles and accessible corner sliders, 90-degree rotation, original/color-enhancement/grayscale/adaptive black-and-white modes and brightness adjustment. Users review the result before adding each page. Up to 15 pages form an A4 PDF (portrait or landscape per image), with a 10 MiB output limit. Input images are limited to 20 MiB and scaled to a maximum 1800-pixel edge for browser memory use. Unsupported HEIC files show a JPEG/PNG fallback message.

Root administrators can open the scanner from trip PDF attachments and explicitly attach its generated PDF using the existing private storage/metadata upload and cleanup flow. Other roles can scan/download locally; their existing upload permissions are unchanged. No OCR or automatic paper-edge detection is claimed. Processing cannot restore unreadable text; preview includes a reminder to check numbers and stamps. Core tests cover perspective geometry, invalid polygons, enhancement modes and multipage PDF structure; Poppler verifies and renders the generated test PDF. Phone-camera and gallery behavior still require actual device acceptance testing.

## Trip deletion — 2026-10-23
Root administrators can permanently delete an open or closed trip from its card after typing the exact plate. Company staff/managers and drivers have no deletion permission. The service-only `fleet_delete_trip` RPC rechecks an active root membership, locks the trip, verifies the plate, records cleanup jobs and removes its archive entry and trip atomically. Existing cascading FKs remove updates, files, messages, issues, waypoints, POD, expense/financial records, notifications and share links. Driver accounts and other trips are retained. Security audit rows are retained.

Private storage objects in the trip's PDF, conversation and POD prefixes are queued before metadata deletion. Edge cleanup uses Storage API removal in batches; unsuccessful jobs remain in a service-only RLS table. The UI provides retry after the trip is deleted. At most 500 jobs per bucket are processed per request; remaining work is reported accurately. Signed file URLs already issued can last until their expiry if cleanup is delayed. Existing maintenance history retains its records with the trip reference set to null by its FK.

Validation: transactional synthetic SQL fixtures rolled back after verifying denied staff/wrong confirmation, both open/closed trip deletion, cascading metadata deletion, durable cleanup jobs, audit retention and preserved driver/other trip. API mocks verify active root gating and successful retry following a simulated storage failure. No production trip was deleted as part of implementation.

## Modern interface — 2026-10-23
Shared `modern-ui.css` and `modern-ui.js` replace emoji/symbol shortcuts with inline SVG stroke icons, normalize anchor/button styles, compact the account/language/scanner header, refresh statistic cards, and provide a floating mobile navigation bar. White/slate surfaces and emerald actions have explicit dark variants; print styles are untouched. Scanner launcher receives a stable DOM ID for decoration. Decorative SVGs are hidden from assistive technology and text labels remain. Dynamic notification and appearance controls are decorated without replacing their handlers or badge elements. Existing session, role, storage and trip logic is unchanged.

Regression checks cover appearance persistence/system mode/large text, office translations, file actions and scoped map behavior. The local browser download was unavailable, so actual iPhone visual acceptance remains to be checked on the deployed interface.
