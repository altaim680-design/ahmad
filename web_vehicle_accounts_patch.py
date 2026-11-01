# -*- coding: utf-8 -*-
"""Separate company vehicle-payable ledger for Nahda Web (additive patch).
Existing customs, invoices and customer cash records remain untouched.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
import hmac
import secrets
import uuid

from flask import abort, flash, redirect, request, session, url_for
from sqlalchemy import text

import web_customer_statement_patch as statement_module
import web_multitenant_patch as mt

app = statement_module.app
db = statement_module.db
core = statement_module.core
Company = core.Company

# USD only until the existing customer/cash ledger supports explicit FX accounting.
VALID_CURRENCIES = ('USD',)
ROLE_VIEW = ('admin', 'accountant', 'transport', 'collector')
ROLE_WRITE = ('admin', 'accountant', 'transport')
ROLE_PAYMENT = ('admin', 'accountant')
ROLE_OFFSET = ('admin', 'accountant')


def _access(allowed):
    if not session.get('uid') or not session.get('tenant_id'):
        abort(401)
    if session.get('role') not in allowed:
        abort(403)
    return int(session['tenant_id']), str(session.get('username') or 'user')


def _csrf():
    if '_vehicle_csrf' not in session:
        session['_vehicle_csrf'] = secrets.token_urlsafe(32)
    return session['_vehicle_csrf']


def _require_csrf():
    expected = session.get('_vehicle_csrf', '')
    supplied = request.form.get('csrf', '')
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        abort(403, description='رمز التحقق غير صحيح')


def _amount(raw):
    try:
        v = Decimal(str(raw)).quantize(Decimal('0.01'))
        if not v.is_finite() or v <= 0 or v > Decimal('999999999999999.99'):
            raise ValueError()
        return v
    except (ValueError, TypeError, InvalidOperation):
        abort(400, description='المبلغ غير صحيح')


def _day(raw):
    try:
        return date.fromisoformat(str(raw))
    except (ValueError, TypeError):
        abort(400, description='التاريخ غير صحيح')


def _currency(raw):
    value = str(raw or 'USD').upper()
    if value not in VALID_CURRENCIES:
        abort(400, description='العملة غير مدعومة')
    return value


def _company(conn, tenant_id, company_id, lock=False):
    query = ('SELECT id, name, COALESCE(opening_balance,0) AS opening '
             'FROM public.company WHERE id=:cid AND tenant_id=:tid')
    if lock:
        query += ' FOR UPDATE'
    row = conn.execute(text(query), {'cid': company_id, 'tid': tenant_id}).mappings().first()
    if row is None:
        abort(404, description='الشركة غير موجودة')
    return row


def _receivable(conn, tenant_id, company_id, currency):
    """Customer account is USD-only in existing system. Never FX-net automatically."""
    if currency != 'USD':
        return Decimal('0')
    c = _company(conn, tenant_id, company_id)
    invoices = conn.execute(text(
        'SELECT COALESCE(SUM(COALESCE(total,0)),0) '
        'FROM public.v3_sales_invoices WHERE tenant_id=:tid AND company_id=:cid'),
        {'tid': tenant_id, 'cid': company_id}).scalar() or 0
    cash = conn.execute(text("""
        SELECT COALESCE(SUM(CASE
          WHEN lower(COALESCE(direction,'')) IN
             ('in','income','receive','received','قبض','تحصيل','وارد')
          THEN -COALESCE(amount,0) ELSE COALESCE(amount,0) END),0)
        FROM public.v3_cash_transactions
        WHERE tenant_id=:tid AND company_id=:cid
    """), {'tid': tenant_id, 'cid': company_id}).scalar() or 0
    offsets = conn.execute(text("""
        SELECT COALESCE(SUM(o.amount),0) FROM public.v3_company_vehicle_offsets o
        WHERE o.tenant_id=:tid AND o.company_id=:cid AND o.currency='USD'
        AND NOT EXISTS (SELECT 1 FROM public.v3_company_vehicle_offset_reversals r
                        WHERE r.offset_id=o.id)
    """), {'tid': tenant_id, 'cid': company_id}).scalar() or 0
    return (Decimal(str(c['opening'])) + Decimal(str(invoices))
            + Decimal(str(cash)) - Decimal(str(offsets)))


def _vehicle_due(conn, tenant_id, company_id, currency):
    return Decimal(str(conn.execute(text("""
        SELECT COALESCE(outstanding_to_company,0)
        FROM public.v3_company_vehicle_balances
        WHERE tenant_id=:tid AND company_id=:cid AND currency=:cur
    """), {'tid': tenant_id, 'cid': company_id, 'cur': currency}).scalar() or 0))


def _journal(conn, tid, day, description, ref_type, ref_id, debit_code, credit_code, amount):
    accounts = conn.execute(text("""
        SELECT code,id FROM public.v3_accounts
        WHERE code IN (:debit,:credit) AND active IS DISTINCT FROM FALSE
    """), {'debit':debit_code,'credit':credit_code}).mappings().all()
    codes = {row['code']:row['id'] for row in accounts}
    if debit_code not in codes or credit_code not in codes:
        abort(409, description='حساب اليومية المطلوب غير موجود')
    jid = conn.execute(text("""
        INSERT INTO public.v3_journal_entries
        (entry_date,description,ref_type,ref_id,posted,created_at,tenant_id)
        VALUES(:day,:desc,:ref_type,:ref_id,true,now(),:tid) RETURNING id
    """), {'day':day.isoformat(),'desc':description,'ref_type':ref_type,
          'ref_id':ref_id,'tid':tid}).scalar_one()
    conn.execute(text("""
        INSERT INTO public.v3_journal_lines
        (entry_id,account_id,debit,credit,note,tenant_id)
        VALUES (:jid,:debit_account,:amount,0,:note,:tid),
               (:jid,:credit_account,0,:amount,:note,:tid)
    """), {'jid':jid,'debit_account':codes[debit_code],
          'credit_account':codes[credit_code],'amount':amount,
          'note':description,'tid':tid})
    return jid


def _redirect(company_id, currency='USD'):
    return redirect(url_for('nahda_vehicle_accounts',
                            company_id=company_id, currency=currency))


# Extend only the visible customer statement to reflect confirmed manual offsets.
# All preexisting cash/invoices and opening balances retain their original logic.
_original_company_statement = statement_module._company_statement


def _statement_including_offsets(company, start='', end=''):
    result = _original_company_statement(company, start, end)
    tid = int(session['tenant_id'])
    entries = db.session.execute(text("""
        SELECT transaction_date,kind,id,owed_to_company,reduction
        FROM public.v3_company_vehicle_statement
        WHERE tenant_id=:tid AND company_id=:cid AND currency='USD'
          AND kind IN ('manual_offset','offset_reversal')
        ORDER BY transaction_date,id
    """), {'tid': tid, 'cid': company.id}).mappings().all()
    if not entries:
        return result
    movements = result['movements']
    opening_for_period = result['opening_for_period']
    for entry in entries:
        dt = entry['transaction_date'].isoformat()
        credit = float(entry['reduction'] or 0)
        debit = float(entry['owed_to_company'] or 0)
        if start and dt < start:
            opening_for_period += debit - credit
            continue
        if end and dt > end:
            continue
        movements.append({
            'date': dt,
            'kind': 'مقاصة سيارات يدوية' if entry['kind']=='manual_offset' else 'عكس مقاصة سيارات',
            'ref': 'CV-' + str(entry['id']),
            'description': 'تسوية موثقة بين حساب السيارات وحساب الشركة',
            'debit': debit, 'credit': credit, 'url': '/vehicle-accounts?company_id='+str(company.id)
        })
    movements.sort(key=lambda x: (x['date'], x['kind'], x['ref']))
    balance = opening_for_period
    debit = credit = 0.0
    for row in movements:
        debit += float(row['debit'])
        credit += float(row['credit'])
        balance += float(row['debit']) - float(row['credit'])
        row['balance'] = balance
    result.update(opening_for_period=opening_for_period,
                  debit=debit, credit=credit, balance=balance, movements=movements)
    return result


statement_module._company_statement = _statement_including_offsets


@app.route('/vehicle-accounts', methods=['GET'])
def nahda_vehicle_accounts():
    tenant, actor = _access(ROLE_VIEW)
    currency = _currency(request.args.get('currency'))
    companies = Company.query.order_by(Company.name.asc(), Company.id.asc()).all()
    cid = request.args.get('company_id', type=int)
    if cid is None and companies:
        cid = companies[0].id
    selected = next((x for x in companies if x.id == cid), None)
    if cid is not None and selected is None:
        abort(404)
    movements = []
    due = Decimal('0')
    receivable = Decimal('0')
    if selected:
        with db.engine.connect() as conn:
            _company(conn, tenant, selected.id)
            due = _vehicle_due(conn, tenant, selected.id, currency)
            receivable = _receivable(conn, tenant, selected.id, currency)
            movements = conn.execute(text("""
               SELECT transaction_date,kind,id,details,owed_to_company,reduction
               FROM public.v3_company_vehicle_statement
               WHERE tenant_id=:tid AND company_id=:cid AND currency=:cur
               ORDER BY transaction_date DESC,id DESC LIMIT 300
            """), {'tid': tenant, 'cid': selected.id, 'cur': currency}).mappings().all()
    body = r'''
    <div class="hero"><h1>🚚 حسابات سيارات الشركات</h1>
      <p>حساب مستقل تماماً عن الديون الجمركية — لا توجد مقاصة تلقائية</p>
    </div>
    <div class="card no-print">
      <div class="section-title">اختيار الشركة والعملة</div>
      <form method="get" action="{{url_for('nahda_vehicle_accounts')}}" class="formgrid">
        <div class="field"><label>الشركة</label><select name="company_id">
        {% for c in companies %}<option value="{{c.id}}" {% if selected and c.id==selected.id %}selected{% endif %}>{{c.name}}</option>{% endfor %}
        </select></div>
        <div class="field"><label>العملة</label><select name="currency">
        {% for cur in currencies %}<option value="{{cur}}" {% if cur==currency %}selected{% endif %}>{{cur}}</option>{% endfor %}
        </select></div>
        <div class="field" style="align-self:end"><button class="btn green">عرض الحساب</button></div>
      </form>
    </div>
    {% with messages = get_flashed_messages(with_categories=true) %}
    {% for cat,msg in messages %}<div class="card" style="margin:12px 0;color:{{'#991b1b' if cat=='error' else '#065f46'}}">{{msg}}</div>{% endfor %}
    {% endwith %}
    {% if selected %}
    <div class="grid stats">
      <div class="card stat"><div class="label">مستحق للشركة عن سياراتها ({{currency}})</div><div class="value">{{'%.2f'|format(due)}}</div></div>
      <div class="card stat"><div class="label">ديون الشركة للمكتب ({{currency}})</div><div class="value">{{'%.2f'|format(receivable)}}</div></div>
      <div class="card stat"><div class="label">فرق الحسابين قبل أي مقاصة جديدة</div><div class="value">{{'%.2f'|format(receivable-due)}}</div></div>
    </div>
    <div class="card no-print">
      <div class="section-title">تسجيل سيارة عملت لنا</div>
      {% if can_write %}
      <form method="post" action="{{url_for('nahda_vehicle_trip')}}" class="formgrid">
        <input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="company_id" value="{{selected.id}}">
        <input type="hidden" name="currency" value="{{currency}}">
        <div class="field"><label>التاريخ</label><input type="date" name="date" value="{{today}}" required></div>
        <div class="field"><label>رقم السيارة</label><input name="vehicle_no" maxlength="100" required></div>
        <div class="field"><label>اسم السائق</label><input name="driver_name" maxlength="120"></div>
        <div class="field"><label>من</label><input name="from_location" maxlength="200"></div>
        <div class="field"><label>إلى</label><input name="to_location" maxlength="200"></div>
        <div class="field"><label>رقم البيان</label><input name="declaration_no" maxlength="120"></div>
        <div class="field"><label>الأجرة ({{currency}})</label><input type="number" step=".01" min=".01" name="amount" required></div>
        <div class="field" style="align-self:end"><button class="btn green">+ حفظ نقلة السيارة</button></div>
      </form>
      {% else %}<p>صلاحية عرض فقط.</p>{% endif %}
    </div>
    {% if can_payment %}
    <div class="card no-print">
      <div class="section-title">تسديد مستحقات سيارات الشركة</div>
      <p>الدفع من صندوق الدولار فقط حالياً، ويُسجل صرفاً مستقلاً عن حساب العملاء.</p>
      {% if currency=='USD' %}
      <form method="post" action="{{url_for('nahda_vehicle_payment')}}" class="formgrid">
        <input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="company_id" value="{{selected.id}}">
        <input type="hidden" name="currency" value="USD">
        <div class="field"><label>التاريخ</label><input type="date" name="date" value="{{today}}" required></div>
        <div class="field"><label>المبلغ بالدولار</label><input type="number" step=".01" min=".01" max="{{due}}" name="amount" required></div>
        <div class="field" style="align-self:end"><button class="btn dark" {% if due<=0 %}disabled{% endif %}>تسديد من الصندوق</button></div>
      </form>
      {% else %}<p>تسجيل السداد النقدي بغير الدولار مؤجل لحين تفعيل حساب صندوق خاص بهذه العملة.</p>{% endif %}
    </div>
    {% endif %}
    {% if can_offset %}
    <div class="card no-print">
      <div class="section-title">مقاصة يدوية — لا تحدث دون تأكيدك</div>
      <p>تخصم من ذمة الشركة ومن حساب السيارات معاً بقيد محاسبي متوازن.
         لا تقبل المقاصة إلا بالدولار لأن حساب العملاء الحالي بالدولار.</p>
      {% if currency=='USD' %}
      <form method="post" action="{{url_for('nahda_vehicle_offset')}}" class="formgrid">
        <input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="company_id" value="{{selected.id}}">
        <input type="hidden" name="currency" value="USD"><input type="hidden" name="request_id" value="{{request_id}}">
        <div class="field"><label>التاريخ</label><input type="date" name="date" value="{{today}}" required></div>
        <div class="field"><label>قيمة المقاصة</label><input type="number" name="amount" step=".01" min=".01" max="{{max_offset}}" required></div>
        <div class="field"><label>سبب المقاصة</label><input name="reason" maxlength="500"></div>
        <div class="field"><label>التأكيد اليدوي</label><label><input type="checkbox" name="confirm" value="yes" required> أوافق على إجراء المقاصة الآن</label></div>
        <div class="field" style="align-self:end"><button class="btn amber" {% if max_offset<=0 %}disabled{% endif %}>تأكيد المقاصة يدوياً</button></div>
      </form>
      {% endif %}
    </div>
    {% endif %}
    <div class="card">
      <div class="section-title">كشف حساب السيارات — {{selected.name}} ({{currency}})</div>
      <div class="toolbar no-print"><button type="button" class="btn dark" onclick="window.print()">🖨️ طباعة / PDF</button>
      <a class="btn gray" href="{{url_for('customer_statement',company_id=selected.id)}}">كشف حساب الشركة الجمركي</a></div>
      <div class="tablewrap"><table>
      <thead><tr><th>التاريخ</th><th>نوع الحركة</th><th>التفاصيل</th><th>لصالح الشركة</th><th>سداد / مقاصة</th></tr></thead>
      <tbody>
      {% for m in movements %}
      <tr><td>{{m.transaction_date}}</td><td>{{kinds.get(m.kind,m.kind)}}</td><td>{{m.details or '—'}}</td>
        <td>{{'%.2f'|format(m.owed_to_company)}}</td><td>{{'%.2f'|format(m.reduction)}}</td></tr>
      {% else %}<tr><td colspan="5">لا توجد حركات سيارات لهذه الشركة بهذه العملة.</td></tr>{% endfor %}
      </tbody></table></div>
    </div>
    {% else %}<div class="card">لا توجد شركات بعد.</div>{% endif %}
    '''
    return core.layout(
        'حسابات سيارات الشركات', body,
        companies=companies, selected=selected, movements=movements,
        due=due, receivable=receivable, max_offset=max(Decimal('0'),min(due,receivable)),
        currency=currency, currencies=VALID_CURRENCIES, csrf=_csrf(),
        request_id=str(uuid.uuid4()), today=date.today().isoformat(),
        can_write=session.get('role') in ROLE_WRITE,
        can_payment=session.get('role') in ROLE_PAYMENT,
        can_offset=session.get('role') in ROLE_OFFSET,
        kinds={'trip':'أجرة نقلة','payment':'سداد من الصندوق',
               'manual_offset':'مقاصة يدوية','offset_reversal':'عكس مقاصة'}
    )


def _form_base(roles):
    tenant, actor = _access(roles)
    _require_csrf()
    try:
        cid = int(request.form.get('company_id',''))
    except (ValueError, TypeError):
        abort(400)
    cur = _currency(request.form.get('currency'))
    return tenant, actor, cid, cur


@app.route('/vehicle-accounts/trips', methods=['POST'])
def nahda_vehicle_trip():
    tid, actor, cid, cur = _form_base(ROLE_WRITE)
    day = _day(request.form.get('date'))
    vehicle = (request.form.get('vehicle_no') or '').strip()[:100]
    if not vehicle:
        abort(400)
    amount = _amount(request.form.get('amount'))
    with db.engine.begin() as conn:
        company = _company(conn, tid, cid)
        job_id = conn.execute(text("""
          INSERT INTO public.v3_company_vehicle_jobs
          (tenant_id,company_id,trip_date,vehicle_no,driver_name,from_location,to_location,
           declaration_no,amount,currency,created_by)
          VALUES (:tid,:cid,:day,:vehicle,:driver,:src,:dst,:dec,:amount,:cur,:actor)
          RETURNING id
        """), {
            'tid':tid,'cid':cid,'day':day,'vehicle':vehicle,
            'driver':(request.form.get('driver_name') or '')[:120],
            'src':(request.form.get('from_location') or '')[:200],
            'dst':(request.form.get('to_location') or '')[:200],
            'dec':(request.form.get('declaration_no') or '')[:120],
            'amount':amount,'cur':cur,'actor':actor
        }).scalar_one()
        _journal(conn, tid, day, 'أجرة سيارة '+vehicle+' لشركة '+str(company['name']),
                 'company_vehicle_trip', job_id, '5020', '2000', amount)
    flash('تمت إضافة أجرة السيارة إلى حساب الشركة المستقل.', 'success')
    return _redirect(cid, cur)


@app.route('/vehicle-accounts/payments', methods=['POST'])
def nahda_vehicle_payment():
    tid, actor, cid, cur = _form_base(ROLE_PAYMENT)
    if cur != 'USD':
        abort(400, description='صندوق العملات الأخرى غير مدعوم حالياً')
    day = _day(request.form.get('date'))
    amount = _amount(request.form.get('amount'))
    with db.engine.begin() as conn:
        company = _company(conn, tid, cid, lock=True)
        conn.execute(text('SELECT pg_advisory_xact_lock(:key,:cid)'),
                     {'key':11081,'cid':cid})
        if amount > _vehicle_due(conn, tid, cid, cur):
            abort(409, description='المبلغ أكبر من الأجور المستحقة')
        reference = 'CVP-' + uuid.uuid4().hex[:20].upper()
        cash_id = conn.execute(text("""
          INSERT INTO public.v3_cash_transactions
          (txn_date,direction,category,amount,company_id,description,reference,created_by,created_at,tenant_id)
          VALUES (:day,'out','أجور سيارات شركات',:amount,NULL,:description,:ref,:actor,now(),:tid)
          RETURNING id
        """), {'day':day.isoformat(),'amount':amount,
              'description':'تسديد أجور سيارات - '+str(company['name']),
              'ref':reference,'actor':actor,'tid':tid}).scalar_one()
        payment_id = conn.execute(text("""
          INSERT INTO public.v3_company_vehicle_payments
          (tenant_id,company_id,payment_date,amount,currency,payment_method,
           cash_transaction_id,reference_no,created_by)
          VALUES(:tid,:cid,:day,:amount,'USD','cash',:cash,:ref,:actor)
          RETURNING id
        """), {'tid':tid,'cid':cid,'day':day,'amount':amount,
              'cash':cash_id,'ref':reference,'actor':actor}).scalar_one()
        _journal(conn, tid, day, 'سداد أجور سيارات '+str(company['name']),
                 'company_vehicle_payment', payment_id, '2000', '1000', amount)
    flash('تم تسجيل سداد أجور السيارات من الصندوق، دون تغيير حساب العميل.', 'success')
    return _redirect(cid, cur)


@app.route('/vehicle-accounts/offsets', methods=['POST'])
def nahda_vehicle_offset():
    tid, actor, cid, cur = _form_base(ROLE_OFFSET)
    if cur != 'USD':
        abort(400, description='المقاصة متاحة للدولار فقط في نظام الذمم الحالي')
    if request.form.get('confirm') != 'yes':
        abort(400, description='يجب تأكيد المقاصة يدوياً')
    token = (request.form.get('request_id') or '').strip()
    try:
        uuid.UUID(token)
    except (ValueError, TypeError):
        abort(400, description='معرف العملية غير صحيح')
    amount = _amount(request.form.get('amount'))
    day = _day(request.form.get('date'))
    with db.engine.begin() as conn:
        company = _company(conn, tid, cid, lock=True)
        conn.execute(text('SELECT pg_advisory_xact_lock(:key,:cid)'),
                     {'key':11081,'cid':cid})
        existing = conn.execute(text("""
          SELECT id FROM public.v3_company_vehicle_offsets
          WHERE tenant_id=:tid AND company_id=:cid AND idempotency_key=:token
        """), {'tid':tid,'cid':cid,'token':token}).scalar()
        if existing:
            flash('هذه المقاصة محفوظة سابقاً ولم يتم تكرارها.', 'success')
            return _redirect(cid, cur)
        if amount > _vehicle_due(conn, tid, cid, cur) or amount > _receivable(conn, tid, cid, cur):
            abort(409, description='المقاصة تتجاوز أحد الرصيدين المتاحين')
        # Balanced posting in the same SQL transaction, never automatically.
        jid = _journal(conn, tid, day,
                        'مقاصة سيارات يدوية مع '+str(company['name'])+'، بواسطة '+actor,
                        'company_vehicle_offset', None, '2000', '1100', amount)
        offset_id = conn.execute(text("""
          INSERT INTO public.v3_company_vehicle_offsets
          (tenant_id,company_id,offset_date,amount,currency,
           journal_entry_id,reason,confirmed_by,idempotency_key)
          VALUES(:tid,:cid,:day,:amount,'USD',:jid,:reason,:actor,:token)
          RETURNING id
        """), {'tid':tid,'cid':cid,'day':day,'amount':amount,'jid':jid,
              'reason':(request.form.get('reason') or '')[:500],
              'actor':actor,'token':token}).scalar_one()
        conn.execute(text("UPDATE public.v3_journal_entries SET ref_id=:oid WHERE id=:jid"),
                     {'oid':offset_id,'jid':jid})
    flash('تم اعتماد المقاصة اليدوية وتسجيل قيد اليومية دون حذف أي حركة.', 'success')
    return _redirect(cid, cur)


_previous_layout = core.layout
def _vehicle_layout(title, body, **ctx):
    html = _previous_layout(title, body, **ctx)
    if session.get('uid') and session.get('role') in ROLE_VIEW and '/vehicle-accounts' not in html:
        link = '<a href="/vehicle-accounts">🚚 حسابات السيارات</a>'
        if '</aside>' in html:
            html = html.replace('</aside>', link+'</aside>', 1)
    return html

core.layout = _vehicle_layout


@app.route('/vehicle-accounts-health')
def nahda_vehicle_health():
    return {'ok': True, 'feature': 'company_vehicle_accounts',
            'separate_ledger': True, 'manual_offsets_only': True}
