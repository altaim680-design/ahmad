# -*- coding: utf-8 -*-
"""Hotfix tenant validation during trip creation.

Flask session values and database tenant ids can occasionally reach the flush
hook with equivalent values represented by different Python types. Normalize
before comparing so same-tenant writes are allowed while cross-tenant writes
remain blocked.
"""
import web_login_premium_patch as base
import web_multitenant_patch as mt
from flask import has_request_context, session
from sqlalchemy import event
from sqlalchemy.orm import Session as SASession

app = base.app


def _tenant_ids_equal(a, b):
    if a is None or b is None:
        return a is b
    try:
        return int(a) == int(b)
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()


# Replace the original flush guard with a type-safe equivalent.
try:
    event.remove(SASession, 'before_flush', mt._tenant_before_flush)
except Exception:
    pass


@event.listens_for(SASession, 'before_flush')
def _tenant_before_flush_safe(db_session, flush_context, instances):
    if not has_request_context():
        return
    tid = session.get('tenant_id')
    if tid in (None, ''):
        return

    scoped = tuple(mt.SCOPED_MODELS)

    # Every newly created business row belongs to the active company.
    for obj in list(db_session.new):
        if isinstance(obj, scoped) and hasattr(obj, 'tenant_id'):
            otid = getattr(obj, 'tenant_id', None)
            if otid in (None, ''):
                try:
                    obj.tenant_id = int(tid)
                except (TypeError, ValueError):
                    obj.tenant_id = tid
            elif not _tenant_ids_equal(otid, tid):
                raise PermissionError('محاولة إنشاء بيانات لصالح شركة أخرى مرفوضة')

    # Existing rows may only be changed/deleted by their own tenant.
    for obj in list(db_session.dirty) + list(db_session.deleted):
        if isinstance(obj, scoped) and hasattr(obj, 'tenant_id'):
            otid = getattr(obj, 'tenant_id', None)
            if otid not in (None, '') and not _tenant_ids_equal(otid, tid):
                raise PermissionError('محاولة الوصول إلى بيانات شركة أخرى مرفوضة')


@app.route('/trip-tenant-hotfix-health')
def trip_tenant_hotfix_health():
    return {'ok': True, 'trip_creation_tenant_fix': True, 'tenant_guard': 'normalized'}
