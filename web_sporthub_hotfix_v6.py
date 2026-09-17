# -*- coding: utf-8 -*-
"""SPORT HUB V6 hotfix.

Fixes duplicate template context keys in the multi-club admin layout that caused
500 errors for Club Admin product/order pages.
"""
import web_sporthub_marketplace_v5 as v5

app = v5.app

_original_layout = v5._layout


def _layout_fixed(title, body, active='dashboard', **ctx):
    # v5._layout computes these internally. Some page handlers also passed them
    # explicitly, which made render_template_string receive duplicate keyword
    # arguments (notably is_super) and raised a TypeError/500.
    ctx.pop('is_super', None)
    ctx.pop('club_name', None)
    ctx.pop('nav', None)
    return _original_layout(title, body, active, **ctx)


# Functions defined in web_sporthub_marketplace_v5 resolve the module-global
# _layout at call time, so replacing it here fixes products/orders without
# duplicating their business logic or permissions.
v5._layout = _layout_fixed
