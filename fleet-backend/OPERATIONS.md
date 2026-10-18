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
