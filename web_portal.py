# -*- coding: utf-8 -*-
from web_customer_statement_patch import app
import web_vehicle_accounts_patch  # register Flask routes before other import-time requests
import web_company_payments_patch  # company-wide receipts without invoice-by-invoice settlement
from web_sporthub_customer_email_v11 import premium_storefront_v11
# Startup route diagnostics (no customer data or credentials).
print("NAHDA_PAYMENTS_ROUTES registered_before_store="+str(sorted((r.rule,sorted(r.methods)) for r in app.url_map.iter_rules() if r.rule.startswith('/company-payments'))), flush=True)


try:
    from sqlalchemy.engine import make_url as _make_url
    _dbu = _make_url(app.config.get('SQLALCHEMY_DATABASE_URI',''))
    print(f"DB_TARGET host={_dbu.host} port={_dbu.port} database={_dbu.database} user={_dbu.username}", flush=True)
except Exception as _e:
    print(f"DB_TARGET unavailable={type(_e).__name__}", flush=True)

# Keep the public root as the customer storefront; administration remains under
# /sporthub/admin/login and customer identity is handled by email OTP.
app.view_functions['sporthub_home'] = premium_storefront_v11
if 'sporthub_customer_shop' in app.view_functions:
    app.view_functions['sporthub_customer_shop'] = premium_storefront_v11

if __name__ == '__main__':
    import os
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT','5000')))
