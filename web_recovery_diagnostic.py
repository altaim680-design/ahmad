# -*- coding: utf-8 -*-
"""Temporary read-only diagnostics for tenant recovery.
Prints only backend type, tenant/user ids and row counts; does not modify business data.
"""
import json
from sqlalchemy import text
import web_trip_tenant_hotfix as base
import web_multitenant_patch as mt

app = base.app
db = mt.db


def _rows(sql):
    with db.engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text(sql)).fetchall()]

with app.app_context():
    try:
        url = db.engine.url
        diag = {
            'db_backend': url.drivername,
            'db_database': url.database,
            'db_host': url.host,
            'tenants': _rows("SELECT id, code, name, active FROM system_tenant ORDER BY id"),
            'users': _rows('SELECT id, username, login_name, email, role, tenant_id, system_owner, active FROM "user" ORDER BY id'),
            'company': _rows('SELECT tenant_id, COUNT(*) AS count FROM company GROUP BY tenant_id ORDER BY tenant_id'),
            'declarations': _rows('SELECT tenant_id, COUNT(*) AS count FROM v3_customs_declarations GROUP BY tenant_id ORDER BY tenant_id'),
            'jobs': _rows('SELECT tenant_id, COUNT(*) AS count FROM v3_transport_jobs GROUP BY tenant_id ORDER BY tenant_id'),
            'invoices': _rows('SELECT tenant_id, COUNT(*) AS count FROM v3_sales_invoices GROUP BY tenant_id ORDER BY tenant_id'),
            'cash': _rows('SELECT tenant_id, COUNT(*) AS count FROM v3_cash_transactions GROUP BY tenant_id ORDER BY tenant_id'),
            'declaration_rows': _rows('SELECT id, declaration_no, tenant_id, transport_job_id, status FROM v3_customs_declarations ORDER BY id LIMIT 50'),
            'company_rows': _rows('SELECT id, name, tenant_id FROM company ORDER BY id LIMIT 50'),
        }
        print('RECOVERY_DIAG ' + json.dumps(diag, ensure_ascii=False, default=str), flush=True)
    except Exception as e:
        print('RECOVERY_DIAG_ERROR ' + repr(e), flush=True)
