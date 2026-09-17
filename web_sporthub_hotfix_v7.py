# -*- coding: utf-8 -*-
"""SPORT HUB V7 hotfix.

Keeps the V6 duplicate-context fix and guarantees the main admin route exists.
"""
import web_sporthub_marketplace_v5 as v5

app = v5.app

_original_layout = v5._layout


def _layout_fixed(title, body, active='dashboard', **ctx):
    # v5._layout already computes these values internally.
    ctx.pop('is_super', None)
    ctx.pop('club_name', None)
    ctx.pop('nav', None)
    return _original_layout(title, body, active, **ctx)


v5._layout = _layout_fixed

# The dashboard view is swapped in v5 by endpoint name, but on some deploys the
# legacy URL rule was missing from the active Flask url_map. Register a safe
# fallback only when the concrete route is absent.
if not any(rule.rule == '/sporthub/admin' and 'GET' in rule.methods for rule in app.url_map.iter_rules()):
    app.add_url_rule(
        '/sporthub/admin',
        endpoint='sporthub_admin_v7',
        view_func=v5.dashboard_v5,
        methods=['GET'],
    )
