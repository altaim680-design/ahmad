# -*- coding: utf-8 -*-
"""SPORT HUB V8 robust admin router.

Works around inconsistent legacy Flask URL-map state by intercepting the core
SPORT HUB admin paths before normal dispatch, while preserving all V5 business
logic and permission checks.
"""
import re
from flask import request
import web_sporthub_marketplace_v5 as v5

app = v5.app

_original_layout = v5._layout


def _layout_fixed(title, body, active='dashboard', **ctx):
    ctx.pop('is_super', None)
    ctx.pop('club_name', None)
    ctx.pop('nav', None)
    return _original_layout(title, body, active, **ctx)


v5._layout = _layout_fixed


@app.before_request
def _sporthub_v8_admin_router():
    path = request.path.rstrip('/') or '/'
    method = request.method.upper()

    if method == 'GET' and path == '/sporthub/admin':
        return v5.dashboard_v5()

    if method == 'GET' and path == '/sporthub/admin/products':
        return v5.products_v5()

    if method == 'POST' and path == '/sporthub/admin/products/new':
        return v5.product_new_v5()

    if method == 'POST':
        m = re.fullmatch(r'/sporthub/admin/products/(\d+)/save', path)
        if m:
            return v5.product_save_v5(int(m.group(1)))

    if method == 'GET' and path == '/sporthub/admin/orders':
        return v5.orders_v5()

    return None


# Startup self-test: unauthenticated admin pages should redirect to login (302),
# never 404/500. This writes only status codes to service logs.
try:
    with app.test_client() as _client:
        _a = _client.get('/sporthub/admin', follow_redirects=False)
        _p = _client.get('/sporthub/admin/products', follow_redirects=False)
        print(f'SPORTHUB_V8_SELFTEST admin={_a.status_code} products={_p.status_code}', flush=True)
except Exception as _exc:
    print(f'SPORTHUB_V8_SELFTEST_ERROR {type(_exc).__name__}', flush=True)
