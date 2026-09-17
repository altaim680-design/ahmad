# -*- coding: utf-8 -*-
"""SPORT HUB V9 stale-session recovery and club-admin verification."""
from flask import request, session, redirect
import web_sporthub_hotfix_v8 as v8
import web_sporthub_marketplace_v5 as v5

app = v8.app


def _valid_club_session():
    if session.get('sporthub_role') != 'club':
        return True
    try:
        cid = int(session.get('sporthub_club_id') or 0)
    except Exception:
        return False
    if not cid:
        return False
    club = v5.SportClub.query.filter_by(id=cid, active=True).first()
    if not club:
        return False
    username = (session.get('sporthub_admin_user') or '').strip()
    q = v5.SportClubAccount.query.filter_by(club_id=cid, active=True)
    if username:
        q = q.filter(v5.func.lower(v5.SportClubAccount.username) == username.lower())
    return q.first() is not None


def _stale_club_session_guard():
    path = request.path.rstrip('/') or '/'
    if path.startswith('/sporthub/admin') and not _valid_club_session():
        session.clear()
        if path != '/sporthub/admin/login':
            return redirect('/sporthub/admin/login')
    return None

# Run before V8's admin router.
app.before_request_funcs.setdefault(None, []).insert(0, _stale_club_session_guard)

# Startup checks: anonymous and deliberately stale sessions must redirect, and
# a real active Club Admin must be able to open dashboard/products/orders.
try:
    with app.test_client() as _client:
        _anon = _client.get('/sporthub/admin', follow_redirects=False)
        with _client.session_transaction() as _s:
            _s['sporthub_admin'] = True
            _s['sporthub_role'] = 'club'
            _s['sporthub_club_id'] = 999999999
            _s['sporthub_admin_user'] = '__stale__'
        _stale = _client.get('/sporthub/admin', follow_redirects=False)
        print(f'SPORTHUB_V9_SELFTEST anonymous={_anon.status_code} stale={_stale.status_code} location={_stale.headers.get("Location", "")}', flush=True)

        _acct = v5.SportClubAccount.query.filter_by(active=True).order_by(v5.SportClubAccount.id.desc()).first()
        if _acct:
            _club = v5.SportClub.query.filter_by(id=_acct.club_id, active=True).first()
            if _club:
                with _client.session_transaction() as _s:
                    _s.clear()
                    _s['sporthub_admin'] = True
                    _s['sporthub_role'] = 'club'
                    _s['sporthub_club_id'] = _club.id
                    _s['sporthub_admin_user'] = _acct.username
                    _s['sporthub_club_name'] = _club.name
                _dash = _client.get('/sporthub/admin', follow_redirects=False)
                _prod = _client.get('/sporthub/admin/products', follow_redirects=False)
                _ord = _client.get('/sporthub/admin/orders', follow_redirects=False)
                print(f'SPORTHUB_V9_CLUB_SELFTEST club={_club.id} dashboard={_dash.status_code} products={_prod.status_code} orders={_ord.status_code}', flush=True)
except Exception as _exc:
    print(f'SPORTHUB_V9_SELFTEST_ERROR {type(_exc).__name__}: {_exc}', flush=True)
