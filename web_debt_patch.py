# -*- coding: utf-8 -*-
"""Debt center for Nahda Web V3.
Search outstanding balances by vehicle plate/number or customs declaration number.
"""
from decimal import Decimal

import web_crud_patch as base
from flask import request, session, redirect, url_for
from markupsafe import escape

app = base.app
core = base.core

db = base.db
Company = base.Company
CustomsDeclaration = base.CustomsDeclaration
TransportJob = base.TransportJob
SalesInvoice = base.SalesInvoice

ARABIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')


def _num(v):
    if v in (None, ''):
        return 0.0
    try:
        return float(v)
    except Exception:
        try:
            return float(Decimal(str(v)))
        except Exception:
            return 0.0


def _first_value(obj, names, default=''):
    for name in names:
        try:
            v = getattr(obj, name, None)
        except Exception:
            v = None
        if v not in (None, ''):
            return v
    return default


def _first_num(obj, names):
    for name in names:
        try:
            v = getattr(obj, name, None)
        except Exception:
            v = None
        if v not in (None, ''):
            return _num(v)
    return 0.0


def _norm(v):
    s = str(v or '').translate(ARABIC_DIGITS).strip().lower()
    # Keep Arabic/Latin letters and numbers but ignore common plate separators.
    for ch in (' ', '-', '_', '/', '\\', '.', ':'):
        s = s.replace(ch, '')
    return s


def _company_name(company_id):
    if not company_id:
        return '—'
    try:
        row = Company.query.get(company_id)
        return str(_first_value(row, ('name', 'company_name', 'title'), f'#{company_id}')) if row else f'#{company_id}'
    except Exception:
        return f'#{company_id}'


def _jobs_for_declaration(dec):
    rows = []
    did = getattr(dec, 'id', None)
    if did is not None and hasattr(TransportJob, 'declaration_id'):
        try:
            rows.extend(TransportJob.query.filter_by(declaration_id=did).all())
        except Exception:
            pass
    jid = getattr(dec, 'transport_job_id', None)
    if jid:
        try:
            j = TransportJob.query.get(jid)
            if j and all(getattr(x, 'id', None) != getattr(j, 'id', None) for x in rows):
                rows.append(j)
        except Exception:
            pass
    return rows


def _vehicle_values(dec, jobs):
    attrs = (
        'plate_no', 'vehicle_no', 'vehicle_number', 'car_no', 'car_number',
        'turkish_vehicle', 'syrian_vehicle', 'foreign_vehicle',
        'truck_no', 'tractor_no', 'trailer_no', 'vehicle_plate',
    )
    out = []
    for obj in [dec] + list(jobs):
        for name in attrs:
            try:
                v = getattr(obj, name, None)
            except Exception:
                v = None
            if v not in (None, ''):
                txt = str(v).strip()
                if txt and txt not in out:
                    out.append(txt)
    return out


def _invoice_rows(dec_id):
    if not hasattr(SalesInvoice, 'declaration_id'):
        return []
    try:
        return SalesInvoice.query.filter_by(declaration_id=dec_id).all()
    except Exception:
        return []


def _invoice_amounts(inv):
    total = _first_num(inv, ('grand_total', 'total', 'net_total', 'amount', 'subtotal'))
    paid = _first_num(inv, ('paid', 'paid_amount', 'amount_paid', 'payment_amount'))
    remaining = _first_num(inv, ('remaining', 'balance', 'due', 'amount_due'))
    # If the model has an explicit remaining/balance column, trust it even when zero.
    explicit_remaining = any(hasattr(inv, x) for x in ('remaining', 'balance', 'due', 'amount_due'))
    if not explicit_remaining:
        remaining = max(total - paid, 0.0)
    return total, paid, max(remaining, 0.0)


def _declaration_amount(dec):
    return _first_num(dec, (
        'customer_total', 'grand_total', 'total', 'amount_due', 'company_price',
        'office_fee',
    ))


def _debt_rows(q=''):
    nq = _norm(q)
    try:
        declarations = CustomsDeclaration.query.order_by(CustomsDeclaration.id.desc()).all()
    except Exception:
        declarations = CustomsDeclaration.query.all()
    result = []
    for dec in declarations:
        did = getattr(dec, 'id', None)
        dno = str(_first_value(dec, ('declaration_no', 'number', 'declaration_number', 'manifest_no'), did or '—'))
        jobs = _jobs_for_declaration(dec)
        vehicles = _vehicle_values(dec, jobs)
        if nq:
            search_values = [_norm(dno)] + [_norm(x) for x in vehicles]
            if not any(nq in x for x in search_values if x):
                continue
        invoices = _invoice_rows(did)
        total = paid = remaining = 0.0
        invoice_ids = []
        if invoices:
            for inv in invoices:
                t, p, r = _invoice_amounts(inv)
                total += t
                paid += p
                remaining += r
                if getattr(inv, 'id', None):
                    invoice_ids.append(inv.id)
        else:
            total = _declaration_amount(dec)
            paid = 0.0
            remaining = max(total, 0.0)
        # Debt page shows outstanding rows only; a search still returns settled rows so the user can verify them.
        if not nq and remaining <= 0.0001:
            continue
        company_id = getattr(dec, 'company_id', None)
        result.append({
            'id': did,
            'declaration_no': dno,
            'company': _company_name(company_id),
            'vehicles': ' / '.join(vehicles) if vehicles else '—',
            'total': total,
            'paid': paid,
            'remaining': remaining,
            'status': str(_first_value(dec, ('status',), '—')),
            'invoice_ids': invoice_ids,
        })
    return result


@app.route('/debts')
def debts():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    q = (request.args.get('q') or '').strip()
    rows = _debt_rows(q)
    debt_total = sum(r['remaining'] for r in rows)
    gross_total = sum(r['total'] for r in rows)
    paid_total = sum(r['paid'] for r in rows)
    body = '''
    <div class="page-head">
      <div><h1>صفحة الديون</h1><p class="muted">ابحث برقم السيارة أو رقم البيان، واعرض المستحق والمدفوع والمتبقي مباشرة.</p></div>
    </div>
    <form method="get" class="card" style="margin-bottom:16px">
      <div class="toolbar" style="display:flex;gap:10px;align-items:end;flex-wrap:wrap">
        <label style="flex:1;min-width:250px">رقم السيارة أو رقم البيان
          <input name="q" value="{{q}}" placeholder="مثال: 31 ABC 123 أو رقم البيان" autofocus>
        </label>
        <button class="btn green" type="submit">بحث</button>
        {% if q %}<a class="btn gray" href="/debts">إظهار كل الديون</a>{% endif %}
      </div>
    </form>
    <div class="stats" style="margin-bottom:16px">
      <div class="stat"><div class="muted">عدد السجلات</div><div class="num">{{rows|length}}</div></div>
      <div class="stat"><div class="muted">إجمالي المستحق</div><div class="num">{{'%.2f'|format(gross_total)}}</div></div>
      <div class="stat"><div class="muted">إجمالي المدفوع</div><div class="num">{{'%.2f'|format(paid_total)}}</div></div>
      <div class="stat"><div class="muted">إجمالي الدين</div><div class="num" style="color:#b42318">{{'%.2f'|format(debt_total)}}</div></div>
    </div>
    <div class="card" style="overflow:auto">
      <table>
        <thead><tr><th>رقم البيان</th><th>رقم السيارة</th><th>الشركة</th><th>المستحق</th><th>المدفوع</th><th>المتبقي</th><th>الحالة</th><th>إجراءات</th></tr></thead>
        <tbody>
        {% for r in rows %}
          <tr>
            <td><strong>{{r.declaration_no}}</strong></td>
            <td>{{r.vehicles}}</td>
            <td>{{r.company}}</td>
            <td>{{'%.2f'|format(r.total)}}</td>
            <td>{{'%.2f'|format(r.paid)}}</td>
            <td><strong style="color:{% if r.remaining>0 %}#b42318{% else %}#087443{% endif %}">{{'%.2f'|format(r.remaining)}}</strong></td>
            <td>{{r.status}}</td>
            <td style="white-space:nowrap">
              <a class="btn small blue" href="/declarations/{{r.id}}">فتح البيان</a>
              {% if r.invoice_ids %}<a class="btn small gray" href="/invoices/{{r.invoice_ids[0]}}">الفاتورة</a>{% endif %}
            </td>
          </tr>
        {% else %}
          <tr><td colspan="8" style="text-align:center;padding:30px" class="muted">{% if q %}لا توجد نتيجة مطابقة لرقم السيارة أو البيان{% else %}لا توجد ديون مسجلة حالياً{% endif %}</td></tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
    '''
    return core.layout('الديون', body, q=q, rows=rows, debt_total=debt_total, gross_total=gross_total, paid_total=paid_total)


@app.after_request
def debt_menu_inject(response):
    try:
        if not session.get('user_id') or 'text/html' not in response.headers.get('Content-Type', ''):
            return response
        html = response.get_data(as_text=True)
        if 'href="/debts"' not in html:
            script = '''<script>(function(){if(document.querySelector('a[href="/debts"]'))return;var ref=document.querySelector('a[href="/accounting"]')||document.querySelector('a[href="/invoices"]')||document.querySelector('nav a');if(!ref)return;var a=ref.cloneNode(false);a.href='/debts';a.textContent='💳 الديون';a.className=ref.className||'';ref.parentNode.insertBefore(a,ref.nextSibling);})();</script>'''
            html = html.replace('</body>', script + '</body>')
            response.set_data(html)
            response.headers['Content-Length'] = str(len(response.get_data()))
    except Exception as e:
        print('[debt-menu]', type(e).__name__, str(e))
    return response


@app.route('/debts/health')
def debts_health():
    return {'ok': True, 'feature': 'debts', 'search': ['vehicle', 'declaration']}
