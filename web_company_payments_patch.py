# -*- coding: utf-8 -*-
"""Company-level lump-sum receipts: no per-declaration repayment required.

Adds one cash receipt, one balanced general-ledger entry and an audit record in
a single transaction. Existing customs declarations and invoice rows are NEVER
updated. The company statement already counts cash receipts as credits.
"""
from datetime import date
from decimal import Decimal
import uuid

from flask import abort, flash, redirect, request, session, url_for
from sqlalchemy import text

import web_vehicle_accounts_patch as vehicles
import web_customer_statement_patch as statements

app = vehicles.app
db = vehicles.db
core = vehicles.core
Company = vehicles.Company

PAYMENT_CATEGORY = 'دفعة على حساب الشركة'
RECEIPT_PREFIX = 'CCP-'
CAN_VIEW = ('admin', 'accountant', 'collector')
CAN_RECEIVE = ('admin', 'accountant', 'collector')


def _money(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))


def _company_balance(conn, tenant_id, company_id):
    return _money(vehicles._receivable(conn, tenant_id, company_id, 'USD'))


def _company_list():
    return Company.query.order_by(Company.name.asc(), Company.id.asc()).all()


def _payment_rows(conn, tenant_id, company_id):
    return conn.execute(text("""
      SELECT id, txn_date, amount, reference, description, created_by, created_at
      FROM public.v3_cash_transactions
      WHERE tenant_id=:tid AND company_id=:cid
        AND category=:category AND direction='in'
      ORDER BY created_at DESC, id DESC LIMIT 100
    """), {'tid': tenant_id, 'cid': company_id, 'category': PAYMENT_CATEGORY}).mappings().all()


def _payments_total(conn, tenant_id, company_id):
    return _money(conn.execute(text("""
      SELECT COALESCE(sum(amount),0)
      FROM public.v3_cash_transactions
      WHERE tenant_id=:tid AND company_id=:cid
        AND category=:category AND direction='in'
    """), {'tid': tenant_id, 'cid': company_id, 'category': PAYMENT_CATEGORY}).scalar())


@app.route('/company-payments', methods=['GET'])
def nahda_company_payments():
    tid, actor = vehicles._access(CAN_VIEW)
    companies = _company_list()
    cid = request.args.get('company_id', type=int)
    if cid is None and companies:
        cid = companies[0].id
    selected = next((c for c in companies if c.id == cid), None)
    if cid is not None and selected is None:
        abort(404, description='الشركة غير موجودة')
    current = Decimal('0.00')
    total_received = Decimal('0.00')
    rows = []
    if selected:
        with db.engine.connect() as conn:
            vehicles._company(conn, tid, selected.id)
            current = _company_balance(conn, tid, selected.id)
            total_received = _payments_total(conn, tid, selected.id)
            rows = _payment_rows(conn, tid, selected.id)
    body = r"""
    <div class="hero">
      <h1>💵 تسجيل دفعة للشركة</h1>
      <p>دفعة واحدة على الحساب العام للشركة، بدون الدخول إلى البيانات الجمركية أو تسديد الفواتير واحدة واحدة.</p>
    </div>
    <div class="card no-print">
      <form method="get" action="{{url_for('nahda_company_payments')}}" class="formgrid">
        <div class="field"><label>اختار الشركة</label>
          <select name="company_id" required>
          {% for c in companies %}<option value="{{c.id}}" {% if selected and c.id==selected.id %}selected{% endif %}>{{c.name}}</option>{% endfor %}
          </select>
        </div>
        <div class="field" style="align-self:end"><button class="btn green" type="submit">عرض حساب الشركة</button></div>
      </form>
    </div>
    {% if selected %}
    <div class="grid stats">
      <div class="card stat">
        <div class="label">الرصيد الحالي للشركة (USD)</div>
        <div class="value">{{'%.2f'|format(current)}}</div>
        <small class="muted">موجب: الشركة مدينة للمكتب، سالب: رصيد دائن للشركة</small>
      </div>
      <div class="card stat"><div class="label">الدفعات المستلمة على حساب الشركة</div><div class="value">{{'%.2f'|format(total_received)}}</div></div>
      <div class="card stat"><div class="label">عدد دفعات الحساب المسجلة</div><div class="value">{{rows|length}}</div><small class="muted">آخر 100 حركة كحد أقصى</small></div>
    </div>
    <div class="card no-print">
      <div class="section-title">+ تسجيل دفعة جديدة من {{selected.name}}</div>
      <p class="muted">القبض يسجَّل بالصندوق وكشف حساب الشركة، ولا يغيّر أي بيان أو فاتورة قديمة.</p>
      {% if can_receive %}
      <form id="nahda-company-receipt-form" method="post" action="{{url_for('nahda_company_receive')}}" class="formgrid">
        <input type="hidden" name="csrf" value="{{csrf}}">
        <input type="hidden" name="company_id" value="{{selected.id}}">
        <input type="hidden" name="request_id" value="{{request_id}}">
        <div class="field"><label>تاريخ القبض</label><input type="date" name="date" value="{{today}}" required></div>
        <div class="field"><label>المبلغ المستلم ($)</label>
          <input type="number" name="amount" step="0.01" min="0.01" max="{{'%.2f'|format(current if current>0 else 0)}}" required placeholder="مثلاً 1000"></div>
        <div class="field"><label>ملاحظات / اسم المسلم (اختياري)</label><input name="note" maxlength="500" placeholder="دفعة على حساب الشركة"></div>
        <div class="field" style="align-self:end"><button type="submit" form="nahda-company-receipt-form"
          formmethod="post" formaction="{{url_for('nahda_company_receive')}}"
          class="btn green" {% if current<=0 %}disabled{% endif %}>💾 حفظ دفعة الشركة</button></div>
      </form>
      {% if current<=0 %}<p class="muted">لا يوجد رصيد مدين حالياً، ولذلك لا يمكن تسجيل دفعة قبض جديدة على هذا الحساب.</p>{% endif %}
      {% else %}<p>صلاحية تسجيل الدفعات محصورة بالمدير أو المحاسب أو المحصل.</p>{% endif %}
    </div>
    <div class="card">
      <div class="section-title">سجل دفعات الشركة — {{selected.name}}</div>
      <div class="toolbar no-print">
        <a class="btn dark" href="{{url_for('customer_statement',company_id=selected.id)}}">📒 كشف حساب الشركة الكامل</a>
        <button type="button" class="btn gray" onclick="window.print()">🖨 طباعة القائمة</button>
      </div>
      <div class="tablewrap"><table>
        <thead><tr><th>التاريخ</th><th>رقم السند</th><th>المبلغ بالدولار</th><th>الملاحظات</th><th>سجّلها</th><th class="no-print">طباعة</th></tr></thead>
        <tbody>
        {% for p in rows %}
        <tr>
          <td>{{p.txn_date}}</td><td>{{p.reference}}</td><td><b>{{'%.2f'|format(p.amount)}}</b></td>
          <td>{{p.description or '—'}}</td><td>{{p.created_by or '—'}}</td>
          <td class="no-print"><a class="btn small dark" href="{{url_for('nahda_company_payment_receipt',payment_id=p.id)}}">سند قبض</a></td>
        </tr>
        {% else %}
        <tr><td colspan="6" style="text-align:center;padding:25px">لا توجد دفعات على حساب هذه الشركة بعد</td></tr>
        {% endfor %}
        </tbody>
      </table></div>
    </div>
    {% else %}<div class="card">لم تتم إضافة شركات بعد.</div>{% endif %}
    """
    return core.layout(
        'دفعات الشركات',body,companies=companies,selected=selected,rows=rows,
        current=current,total_received=total_received,can_receive=session.get('role') in CAN_RECEIVE,
        csrf=vehicles._csrf(),request_id=str(uuid.uuid4()),today=date.today().isoformat()
    )


@app.route('/company-payments/receive', methods=['GET','POST'])
def nahda_company_receive():
    if request.method != 'POST':
        flash('لحفظ الدفعة افتح نموذج دفعات الشركات واضغط حفظ؛ هذا الرابط لا يسجل دفعة بمفرده.', 'error')
        return redirect(url_for('nahda_company_payments'))
    tid, actor = vehicles._access(CAN_RECEIVE)
    vehicles._require_csrf()
    try:
        cid = int(request.form.get('company_id') or '')
    except (ValueError, TypeError):
        abort(400, description='الشركة غير محددة')
    day = vehicles._day(request.form.get('date'))
    amount = vehicles._amount(request.form.get('amount'))
    note = (request.form.get('note') or '').strip()[:500]
    token = (request.form.get('request_id') or '').strip()
    try:
        uuid.UUID(token)
    except (ValueError, TypeError):
        abort(400, description='معرف الدفعة غير صحيح')
    reference = RECEIPT_PREFIX + uuid.UUID(token).hex.upper()
    with db.engine.begin() as conn:
        company = vehicles._company(conn, tid, cid, lock=True)
        # Matches other financial flows. A company-wide lock also serializes duplicate clicks.
        conn.execute(text('SELECT pg_advisory_xact_lock(:namespace,:company)'),
                     {'namespace':11081,'company':cid})
        existing = conn.execute(text("""
          SELECT id FROM public.v3_cash_transactions
          WHERE tenant_id=:tid AND company_id=:cid AND reference=:ref AND category=:category
          LIMIT 1
        """), {'tid':tid,'cid':cid,'ref':reference,'category':PAYMENT_CATEGORY}).scalar()
        if existing:
            flash('هذه الدفعة مسجلة سابقاً، ولم نكررها.', 'success')
            return redirect(url_for('nahda_company_payments',company_id=cid))
        outstanding = _company_balance(conn, tid, cid)
        if outstanding <= 0:
            abort(409, description='الشركة ليس عليها دين في كشف الحساب الحالي')
        if amount > outstanding:
            abort(409, description='الدفعة أكبر من الدين الحالي للشركة؛ راجع الرصيد قبل التسجيل')
        payment_id = conn.execute(text("""
          INSERT INTO public.v3_cash_transactions
          (txn_date,direction,category,amount,company_id,description,reference,created_by,created_at,tenant_id)
          VALUES (:dt,'in',:category,:amount,:cid,:note,:ref,:actor,now(),:tid)
          RETURNING id
        """), {'dt':day.isoformat(),'category':PAYMENT_CATEGORY,'amount':amount,
              'cid':cid,'note':note,'ref':reference,'actor':actor,'tid':tid}).scalar_one()
        vehicles._journal(
            conn,tid,day,'قبض دفعة على حساب '+str(company['name'])+' — '+reference,
            'company_account_receipt',payment_id,'1000','1100',amount
        )
        conn.execute(text("""
          INSERT INTO public.v3_audit_log
          (username,action,entity,entity_id,details,created_at,tenant_id)
          VALUES (:actor,'company_receipt','company',:cid,:details,now(),:tid)
        """), {'actor':actor,'cid':cid,'tid':tid,
              'details':'سند '+reference+'؛ قبض '+str(amount)+' USD'})
    flash('تم حفظ دفعة الشركة في الصندوق وكشف الحساب العام بدون تعديل الفواتير.', 'success')
    return redirect(url_for('nahda_company_payment_receipt',payment_id=payment_id))


@app.route('/company-payments/receipt/<int:payment_id>', methods=['GET'])
def nahda_company_payment_receipt(payment_id):
    tid, actor = vehicles._access(CAN_VIEW)
    with db.engine.connect() as conn:
        row = conn.execute(text("""
          SELECT t.id,t.txn_date,t.amount,t.reference,t.description,t.created_by,
                 c.id AS company_id,c.name AS company_name,c.phone
          FROM public.v3_cash_transactions t
          JOIN public.company c ON c.id=t.company_id AND c.tenant_id=t.tenant_id
          WHERE t.id=:id AND t.tenant_id=:tid AND
                t.direction='in' AND t.category=:category
        """), {'id':payment_id,'tid':tid,'category':PAYMENT_CATEGORY}).mappings().first()
    if row is None:
        abort(404)
    body = r"""
    <div class="hero"><h1>سند قبض دفعة شركة</h1><p>نسخة قابلة للطباعة أو الحفظ PDF.</p></div>
    <div class="card" style="max-width:740px;margin:auto">
      <div class="section-title">نهضة سوريا — سند قبض رقم {{p.reference}}</div>
      <div class="tablewrap"><table>
      <tbody>
        <tr><th>الشركة</th><td>{{p.company_name}}</td></tr>
        <tr><th>التاريخ</th><td>{{p.txn_date}}</td></tr>
        <tr><th>المبلغ المقبوض</th><td><b>{{'%.2f'|format(p.amount)}} USD</b></td></tr>
        <tr><th>نوع الحركة</th><td>دفعة على الحساب العام للشركة</td></tr>
        <tr><th>الشرح</th><td>{{p.description or '—'}}</td></tr>
        <tr><th>تم التسجيل بواسطة</th><td>{{p.created_by or '—'}}</td></tr>
      </tbody></table></div>
      <p class="muted">يخفّض هذا السند رصيد الشركة الإجمالي دون توزيع المبلغ على فواتير أو بيانات بعينها.</p>
      <div class="toolbar no-print">
        <button type="button" class="btn green" onclick="window.print()">🖨 طباعة / PDF</button>
        <a class="btn gray" href="{{url_for('nahda_company_payments',company_id=p.company_id)}}">رجوع إلى دفعات الشركة</a>
      </div>
    </div>
    """
    return core.layout('سند قبض شركة',body,p=row)


_original_layout = core.layout


def _payment_layout(page_title, body, **ctx):
    html = _original_layout(page_title, body, **ctx)
    if session.get('uid') and session.get('role') in CAN_VIEW:
        link = '<a href="/company-payments">💵 دفعات الشركات</a>'
        if 'href="/company-payments"' not in html:
            if '</aside>' in html:
                html = html.replace('</aside>', link+'</aside>', 1)
            if '<div class="mobilebar">' in html:
                mobile_link='<a href="/company-payments">💵 دفعات الشركات</a>'
                html = html.replace('<div class="mobilebar">','<div class="mobilebar">'+mobile_link,1)
        # Clarify that invoice-by-invoice debt totals differ from unallocated company-wide receipts.
        if request.path == '/debts' and 'دفعات الشركات غير الموزعة' not in html:
            note = ('<div class="card no-print" style="margin:12px 0">'
                    '<b>دفعات الشركات غير الموزعة:</b> دفعة على الحساب تخفّض إجمالي رصيد الشركة، '
                    'لكنها لا تغيّر حالة أي فاتورة أو رصيد بيان فردي. '
                    '<a class="btn small dark" href="/company-payments">دفعات الشركات والرصيد الإجمالي</a></div>')
            html = html.replace('<div class="page-head">',note+'<div class="page-head">',1)
    return html


core.layout = _payment_layout


@app.route('/company-payments-health',methods=['GET'])
def nahda_company_payments_health():
    return {'ok':True,'feature':'company_lump_sum_receipts',
            'per_invoice_allocation':False,'uses_existing_cash_ledger':True}
