# -*- coding: utf-8 -*-
"""Customer/company account statement for Nahda Web."""
from datetime import date
from flask import request, session, redirect, url_for

import web_nahda_password_reset_patch as base
import web_multitenant_patch as mt

app = base.app
core = mt.core
db = mt.db
Company = core.Company
SalesInvoice = core.SalesInvoice
CashTransaction = core.CashTransaction

def _num(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0

def _in_range(dt, start, end):
    s = str(dt or '')
    if start and s < start:
        return False
    if end and s > end:
        return False
    return True

def _company_statement(company, start='', end=''):
    opening = _num(company.opening_balance)
    before_debit = 0.0
    before_credit = 0.0
    movements = []

    invoices = SalesInvoice.query.filter_by(company_id=company.id).order_by(SalesInvoice.invoice_date.asc(), SalesInvoice.id.asc()).all()
    for x in invoices:
        dt = str(x.invoice_date or '')
        amount = _num(x.total)
        if start and dt < start:
            before_debit += amount
            continue
        if end and dt > end:
            continue
        movements.append({
            'date': dt, 'kind': 'فاتورة', 'ref': x.invoice_no or '',
            'description': x.description or ('فاتورة ' + str(x.invoice_no or '')),
            'debit': amount, 'credit': 0.0,
            'url': url_for('invoice_detail', iid=x.id)
        })

    cash = CashTransaction.query.filter_by(company_id=company.id).order_by(CashTransaction.txn_date.asc(), CashTransaction.id.asc()).all()
    for x in cash:
        dt = str(x.txn_date or '')
        amt = _num(x.amount)
        # Money received from the customer reduces receivables (credit).
        # Outgoing/adjustment entries increase the customer's debit balance.
        is_credit = str(x.direction or '').lower() in ('in','income','receive','received','قبض','تحصيل','وارد')
        debit = 0.0 if is_credit else amt
        credit = amt if is_credit else 0.0
        if start and dt < start:
            before_debit += debit
            before_credit += credit
            continue
        if end and dt > end:
            continue
        movements.append({
            'date': dt, 'kind': x.category or ('دفعة' if is_credit else 'حركة نقدية'),
            'ref': x.reference or '',
            'description': x.description or '',
            'debit': debit, 'credit': credit, 'url': ''
        })

    movements.sort(key=lambda r: (r['date'], 0 if r['kind']=='فاتورة' else 1, r['ref']))
    balance = opening + before_debit - before_credit
    opening_for_period = balance
    period_debit = 0.0
    period_credit = 0.0
    for r in movements:
        period_debit += r['debit']
        period_credit += r['credit']
        balance += r['debit'] - r['credit']
        r['balance'] = balance

    return {
        'opening': opening,
        'opening_for_period': opening_for_period,
        'debit': period_debit,
        'credit': period_credit,
        'balance': balance,
        'movements': movements
    }

@app.route('/customer-statement')
def customer_statement():
    if not session.get('uid'):
        return redirect(url_for('login'))
    if session.get('role') not in ('admin','accountant','collector'):
        return redirect(url_for('dashboard'))

    cid = request.args.get('company_id', type=int)
    start = (request.args.get('from') or '').strip()
    end = (request.args.get('to') or '').strip()
    companies = Company.query.order_by(Company.name.asc()).all()
    selected = Company.query.get(cid) if cid else None

    detail = _company_statement(selected, start, end) if selected else None
    summaries = []
    if not selected:
        for c in companies:
            s = _company_statement(c, start, end)
            summaries.append({'company': c, **s})

    body = r'''
    <div class="hero"><h1>كشف حساب شامل</h1>
      <p>{% if selected %}كشف حساب {{selected.name}}{% else %}ملخص أرصدة جميع الشركات والعملاء{% endif %}</p>
    </div>

    <div class="card no-print">
      <form method="get" class="formgrid">
        <div class="field"><label>الشركة / العميل</label>
          <select name="company_id">
            <option value="">كل الشركات</option>
            {% for c in companies %}<option value="{{c.id}}" {% if selected and selected.id==c.id %}selected{% endif %}>{{c.name}}</option>{% endfor %}
          </select>
        </div>
        <div class="field"><label>من تاريخ</label><input type="date" name="from" value="{{start}}"></div>
        <div class="field"><label>إلى تاريخ</label><input type="date" name="to" value="{{end}}"></div>
        <div class="field" style="align-self:end"><button class="btn green">عرض الكشف</button></div>
      </form>
      <div class="toolbar" style="margin-top:12px">
        <button type="button" class="btn dark" onclick="window.print()">🖨️ طباعة / PDF</button>
        <a class="btn gray" href="{{url_for('customer_statement')}}">إلغاء الفلاتر</a>
      </div>
    </div>

    {% if selected %}
      <div class="grid stats">
        <div class="card stat"><div class="label">الرصيد أول المدة</div><div class="value">{{'%.2f'|format(detail.opening_for_period)}}</div></div>
        <div class="card stat"><div class="label">إجمالي المدين</div><div class="value">{{'%.2f'|format(detail.debit)}}</div></div>
        <div class="card stat"><div class="label">إجمالي الدائن / المدفوع</div><div class="value">{{'%.2f'|format(detail.credit)}}</div></div>
        <div class="card stat"><div class="label">الرصيد الحالي</div><div class="value">{{'%.2f'|format(detail.balance)}}</div></div>
      </div>

      <div class="card">
        <div class="section-title">حركة حساب {{selected.name}}</div>
        <div style="margin-bottom:10px;color:#64748b">الهاتف: {{selected.phone or '—'}}{% if start or end %} • الفترة: {{start or 'البداية'}} إلى {{end or 'اليوم'}}{% endif %}</div>
        <div class="tablewrap"><table>
          <thead><tr><th>التاريخ</th><th>نوع الحركة</th><th>المرجع</th><th>الشرح</th><th>مدين</th><th>دائن</th><th>الرصيد</th><th class="no-print">فتح</th></tr></thead>
          <tbody>
            <tr><td>{{start or '—'}}</td><td><b>رصيد أول المدة</b></td><td>—</td><td>الرصيد المرحّل قبل الفترة</td><td>—</td><td>—</td><td><b>{{'%.2f'|format(detail.opening_for_period)}}</b></td><td class="no-print">—</td></tr>
            {% for r in detail.movements %}
            <tr>
              <td>{{r.date}}</td><td>{{r.kind}}</td><td>{{r.ref or '—'}}</td><td>{{r.description}}</td>
              <td>{% if r.debit %}{{'%.2f'|format(r.debit)}}{% else %}—{% endif %}</td>
              <td>{% if r.credit %}{{'%.2f'|format(r.credit)}}{% else %}—{% endif %}</td>
              <td><b>{{'%.2f'|format(r.balance)}}</b></td>
              <td class="no-print">{% if r.url %}<a class="btn small dark" href="{{r.url}}">فتح</a>{% else %}—{% endif %}</td>
            </tr>
            {% else %}<tr><td colspan="8" style="text-align:center;padding:25px">لا توجد حركات ضمن الفترة المحددة</td></tr>{% endfor %}
          </tbody>
          <tfoot><tr><th colspan="4">الإجمالي</th><th>{{'%.2f'|format(detail.debit)}}</th><th>{{'%.2f'|format(detail.credit)}}</th><th>{{'%.2f'|format(detail.balance)}}</th><th class="no-print"></th></tr></tfoot>
        </table></div>
      </div>
    {% else %}
      <div class="card">
        <div class="section-title">ملخص حسابات الشركات</div>
        <div class="tablewrap"><table>
          <thead><tr><th>الشركة / العميل</th><th>رصيد أول المدة</th><th>مدين</th><th>دائن / مدفوع</th><th>الرصيد الحالي</th><th class="no-print">التفاصيل</th></tr></thead>
          <tbody>{% for s in summaries %}
            <tr><td><b>{{s.company.name}}</b></td><td>{{'%.2f'|format(s.opening_for_period)}}</td><td>{{'%.2f'|format(s.debit)}}</td><td>{{'%.2f'|format(s.credit)}}</td><td><b>{{'%.2f'|format(s.balance)}}</b></td>
            <td class="no-print"><a class="btn small dark" href="{{url_for('customer_statement',company_id=s.company.id,from=start,to=end)}}">كشف الحساب</a></td></tr>
          {% else %}<tr><td colspan="6" style="text-align:center;padding:25px">لا توجد شركات</td></tr>{% endfor %}</tbody>
        </table></div>
      </div>
    {% endif %}
    '''
    return core.layout('كشف حساب شامل', body, companies=companies, selected=selected, detail=detail,
                       summaries=summaries, start=start, end=end, today=date.today().isoformat())

_previous_layout = core.layout
def _statement_layout(page_title, body, **ctx):
    html = _previous_layout(page_title, body, **ctx)
    if session.get('uid') and '/customer-statement' not in html:
        link = '<a href="/customer-statement">📒 كشف حساب شامل</a>'
        # Prefer placing it close to accounting links; fallback to end of sidebar.
        marker = '</aside>'
        if marker in html:
            html = html.replace(marker, link + marker, 1)
    return html
core.layout = _statement_layout

@app.route('/customer-statement-health')
def customer_statement_health():
    return {'ok': True, 'customer_statement': True, 'all_companies_summary': True, 'date_filter': True, 'print_pdf': True}
