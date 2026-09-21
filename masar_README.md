# مسار للنقل الدولي — منصة تشغيل أولية

Full-stack marketplace preview, with real user accounts, cargo offers, single accepted booking per cargo, fixed fee snapshots for both parties, receipt claims, admin-only independent payment review, and role-limited shipment state changes. Uses PostgreSQL when DATABASE_URL is configured.

**Important:** This is a functional *preview*, not a production-ready payment system. The initial free hosted configuration uses ephemeral SQLite and disables all real payment submission. For any public launch, configure isolated persistent PostgreSQL with backups and tested restores, HTTPS with secure cookies, rate limits, password reset and email verification, dispute and refund rules, accounting and currency settlement controls, identity checks, data retention/legal terms, security audit and licensed payment services. Never mark a payment verified based on the user's transfer reference alone.

Environment:
SECRET_KEY unique high-entropy secret; SECURE_COOKIES=1; DATABASE_URL=postgresql://... for persistent data; ADMIN_SETUP_TOKEN high-entropy one-time bootstrap token; TRADER_FEE_BPS=200, CARRIER_FEE_BPS=300.
SHAMCASH_RECEIVER recipient ID and PAYMENTS_ENABLED=1 **only after authorized account verification and settlement arrangements**. This enables manual submission + independent admin review, not an official API or escrow. The platform does not automatically move funds to the carrier.

Run: pip install -r masar_requirements.txt ; uvicorn masar_app:app --host 0.0.0.0 --port 8000.
