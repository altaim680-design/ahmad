# -*- coding: utf-8 -*-
"""Hotfix for email multi-tenant login redirect.
The V3 app names the dashboard endpoint `home`; the email layer referenced
`index`. Keep backward compatibility by registering an `index` endpoint that
redirects to the real dashboard.
"""
import web_email_tenant_patch as base
from flask import redirect, url_for

app = base.app


def _index_alias():
    return redirect(url_for('home'))

# Register a stable compatibility endpoint without replacing the existing `/` route.
if 'index' not in app.view_functions:
    app.add_url_rule('/home', endpoint='index', view_func=_index_alias, methods=['GET'])


@app.route('/email-login-hotfix-health')
def email_login_hotfix_health():
    return {'ok': True, 'email_login_home_redirect': True, 'index_alias': True}
