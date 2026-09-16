# -*- coding: utf-8 -*-
"""Per-invoice Code128 barcode + QR code for screen, print and PDF output."""
import io
import re
from html import escape

import barcode
import segno
from barcode.writer import SVGWriter

import web_passkey_patch as base
import web_invoice_collector_patch as invoicebase
from flask import Response, abort, make_response, request, session, url_for

app = base.app
SalesInvoice = invoicebase.SalesInvoice


def _current_invoice(iid):
    if not (session.get('uid') or session.get('user_id')):
        abort(401)
    tid = session.get('tenant_id')
    if tid is None:
        abort(403)
    q = SalesInvoice.query
    if hasattr(SalesInvoice, 'tenant_id'):
        q = q.filter(SalesInvoice.tenant_id == int(tid))
    return q.filter(SalesInvoice.id == int(iid)).first_or_404()


def _machine_code(inv):
    tid = int(getattr(inv, 'tenant_id', None) or session.get('tenant_id') or 0)
    tenant_code = str(session.get('tenant_code') or '').upper().strip()
    tenant_code = re.sub(r'[^A-Z0-9_-]+', '', tenant_code)[:18] or 'TENANT'
    return f'{tenant_code}-T{tid:04d}-INV-{int(inv.id):08d}'


def _invoice_public_url(iid):
    proto = (request.headers.get('X-Forwarded-Proto') or request.scheme or 'https').split(',')[0].strip()
    host = (request.headers.get('X-Forwarded-Host') or request.host).split(',')[0].strip()
    return f'{proto}://{host}{url_for("invoice_detail", iid=iid)}'


@app.get('/invoices/<int:iid>/barcode.svg')
def invoice_barcode_svg(iid):
    inv = _current_invoice(iid)
    code = _machine_code(inv)
    output = io.BytesIO()
    barcode.get('code128', code, writer=SVGWriter()).write(
        output,
        options={
            'module_width': 0.34,
            'module_height': 13.5,
            'quiet_zone': 2.5,
            'font_size': 9,
            'text_distance': 3.0,
            'write_text': True,
        },
    )
    resp = Response(output.getvalue(), mimetype='image/svg+xml')
    resp.headers['Cache-Control'] = 'private, max-age=86400'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp


@app.get('/invoices/<int:iid>/qr.svg')
def invoice_qr_svg(iid):
    inv = _current_invoice(iid)
    target = _invoice_public_url(inv.id)
    output = io.BytesIO()
    qr = segno.make(target, error='m')
    qr.save(output, kind='svg', scale=5, border=2, xmldecl=False, svgns=True)
    resp = Response(output.getvalue(), mimetype='image/svg+xml')
    resp.headers['Cache-Control'] = 'private, max-age=86400'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp


_original_invoice_detail = app.view_functions.get('invoice_detail')


def _invoice_detail_with_codes(iid, *args, **kwargs):
    result = _original_invoice_detail(iid, *args, **kwargs)
    response = make_response(result)
    if response.status_code != 200:
        return response
    content_type = (response.content_type or '').lower()
    if 'text/html' not in content_type:
        return response

    html = response.get_data(as_text=True)
    if 'id="invoice-machine-codes"' in html:
        return response

    try:
        inv = _current_invoice(iid)
    except Exception:
        return response

    machine = escape(_machine_code(inv))
    invoice_no = escape(str(getattr(inv, 'invoice_no', '') or inv.id))
    barcode_url = escape(url_for('invoice_barcode_svg', iid=inv.id), quote=True)
    qr_url = escape(url_for('invoice_qr_svg', iid=inv.id), quote=True)

    codes = f'''
<style>
#invoice-machine-codes{{max-width:900px;margin:14px auto;padding:16px 18px;border:1px solid #d9e3e8;border-radius:14px;background:#fff;display:grid;grid-template-columns:minmax(0,1fr) 150px;gap:18px;align-items:center;break-inside:avoid;page-break-inside:avoid}}
#invoice-machine-codes .imc-title{{font-size:13px;font-weight:900;color:#334155;margin-bottom:8px}}
#invoice-machine-codes .imc-bar{{width:min(100%,430px);height:auto;display:block}}
#invoice-machine-codes .imc-qr{{width:132px;height:132px;display:block;margin:auto}}
#invoice-machine-codes .imc-code{{direction:ltr;text-align:left;font-family:Consolas,monospace;font-size:11px;color:#475569;margin-top:5px;letter-spacing:.3px}}
#invoice-machine-codes .imc-invoice{{font-size:12px;color:#64748b;margin-top:4px}}
#invoice-machine-codes .imc-qr-label{{text-align:center;font-size:11px;color:#64748b;margin-top:5px}}
@media(max-width:640px){{#invoice-machine-codes{{grid-template-columns:1fr;text-align:center}}#invoice-machine-codes .imc-bar{{margin:auto}}#invoice-machine-codes .imc-code{{text-align:center}}}}
@media print{{#invoice-machine-codes{{box-shadow:none;border-color:#aaa;margin-top:8mm;padding:10px 12px;grid-template-columns:minmax(0,1fr) 125px}}#invoice-machine-codes .imc-qr{{width:112px;height:112px}}}}
</style>
<div id="invoice-machine-codes">
  <div>
    <div class="imc-title">باركود الفاتورة</div>
    <img class="imc-bar" src="{barcode_url}" alt="Barcode {machine}">
    <div class="imc-code">{machine}</div>
    <div class="imc-invoice">رقم الفاتورة: <strong>{invoice_no}</strong></div>
  </div>
  <div>
    <img class="imc-qr" src="{qr_url}" alt="QR Invoice {invoice_no}">
    <div class="imc-qr-label">امسح لفتح الفاتورة</div>
  </div>
</div>
'''

    marker = '<div class="toolbar no-print"'
    if marker in html:
        html = html.replace(marker, codes + marker, 1)
    elif '</body>' in html:
        html = html.replace('</body>', codes + '</body>', 1)
    else:
        html += codes
    response.set_data(html)
    return response


if _original_invoice_detail:
    app.view_functions['invoice_detail'] = _invoice_detail_with_codes


@app.get('/invoice-code-health')
def invoice_code_health():
    return {
        'ok': True,
        'barcode': 'Code128',
        'qr': True,
        'invoice_print': True,
        'tenant_unique': True,
    }
