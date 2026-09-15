# -*- coding: utf-8 -*-
"""Expose admin tools in the mobile navigation."""
import web_invoice_edit_hotfix as base
from flask import session, url_for

app = base.app
core = base.core

_previous_layout = core.layout


def admin_mobile_layout(page_title, body, **ctx):
    html = _previous_layout(page_title, body, **ctx)
    if session.get('role') != 'admin':
        return html

    marker = '<div class="mobilebar">'
    if marker not in html:
        return html

    links = (
        f'<a href="{url_for("users")}" style="background:#0f766e">👤 المستخدمون والصلاحيات</a>'
        f'<a href="{url_for("settings")}" style="background:#334155">⚙ الإعدادات</a>'
        f'<a href="{url_for("audit_page")}" style="background:#475569">🛡 سجل التدقيق</a>'
    )
    # Avoid duplicate injection if another wrapper re-renders the same HTML.
    if '👤 المستخدمون والصلاحيات' not in html:
        html = html.replace(marker, marker + links, 1)
    return html


core.layout = admin_mobile_layout


@app.route('/admin-mobile-health')
def admin_mobile_health():
    return {'ok': True, 'admin_mobile_nav': True, 'users_link': True, 'settings_link': True, 'audit_link': True}
