# -*- coding: utf-8 -*-
"""Invoice branding + detailed lines + one invoice per declaration + debt collector role."""
import base64
from datetime import date

import web_stability_patch as base
import web_debt_patch as debtmod
from flask import request, session, redirect, url_for, flash, render_template_string, Response
from werkzeug.security import generate_password_hash

app = base.app
core = base.core
db = base.db

User = core.User
Company = core.Company
CustomsDeclaration = core.CustomsDeclaration
TransportJob = core.TransportJob
SalesInvoice = core.SalesInvoice
InvoiceLine = core.InvoiceLine
CashTransaction = core.CashTransaction

LOGO_B64 = """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"""

ROLE_LABELS = {
    'admin': 'مدير',
    'accountant': 'محاسب',
    'transport': 'نقل وترانزيت',
    'user': 'موظف',
    'viewer': 'مشاهدة فقط',
    'collector': 'محصل ديون',
}


@app.route('/company-logo')
def company_logo():
    return Response(
        base64.b64decode(LOGO_B64),
        mimetype='image/jpeg',
        headers={'Cache-Control': 'public, max-age=86400'}
    )


@app.before_request
def collector_only_access():
    if session.get('role') != 'collector':
        return None
    allowed = {
        'debts', 'debt_payment', 'logout', 'login', 'company_logo',
        'stability_health', 'health', 'static'
    }
    if request.endpoint and request.endpoint not in allowed:
        return redirect(url_for('debts'))
    return None


_original_layout = core.layout

def collector_aware_layout(page_title, body, **ctx):
    if session.get('role') != 'collector':
        return _original_layout(page_title, body, **ctx)
    html = f"""<!doctype html><html lang="ar"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{page_title}</title><style>{core.CSS}</style></head>
    <body><div class="layout"><aside class="side">
      <div class="brand"><h2>{{{{company_name}}}}</h2><small>تحصيل الديون</small></div>
      <a class="active" href="{{{{url_for('debts')}}}}">💳 الديون والتحصيل</a>
      <a href="{{{{url_for('logout')}}}}" style="background:#7f1d1d">↩ تسجيل خروج</a>
    </aside><main class="main">
      <div class="top"><div class="title">{page_title}</div>
      <div class="user">{{{{session.get('username')}}}} • محصل ديون</div>
      <a class="btn red small" href="{{{{url_for('logout')}}}}" style="margin-right:12px">تسجيل خروج</a></div>
      <div class="mobilebar"><a href="{{{{url_for('debts')}}}}">الديون</a>
      <a href="{{{{url_for('logout')}}}}" style="background:#991b1b">تسجيل خروج</a></div>
      <div class="content">
      {{% with ms=get_flashed_messages(with_categories=true) %}}
      {{% for c,m in ms %}}<div class="flash {{{{c}}}}">{{{{m}}}}</div>{{% endfor %}}
      {{% endwith %}}
      {body}</div></main></div></body></html>"""
    return render_template_string(
        html,
        company_name=core.get_setting('company_name','نهضة سوريا للتخليص الجمركي والنقل'),
        **ctx
    )

core.layout = collector_aware_layout


def _money(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _declaration_invoice(did):
    if not did:
        return None
    return SalesInvoice.query.filter_by(
        declaration_id=int(did)
    ).order_by(SalesInvoice.id.asc()).first()


def _charge_lines_for_declaration(d):
    out = []
    if not d:
        return out
    for ch in d.charges:
        amount = _money(ch.amount)
        if amount <= 0:
            continue
        label = (ch.charge_type or 'بند').strip()
        detail = (ch.description or '').strip()
        desc = label if not detail else f'{label} — {detail}'
        out.append((desc, amount))
    return out


def _invoice_display_lines(inv):
    if inv.declaration:
        rows = _charge_lines_for_declaration(inv.declaration)
        if rows:
            return [{'description': d, 'qty': 1.0, 'unit_price': a, 'amount': a} for d, a in rows]
    return [{
        'description': l.description or 'بند',
        'qty': _money(l.qty) or 1,
        'unit_price': _money(l.unit_price),
        'amount': _money(l.amount),
    } for l in inv.lines]


def invoice_new_v4():
    if not session.get('uid'):
        return redirect(url_for('login'))
    if not core.can_finance():
        flash('هذه العملية للمحاسبة', 'error')
        return redirect(url_for('invoices'))

    selected_id = request.args.get('declaration_id', type=int)
    d = CustomsDeclaration.query.get(selected_id) if selected_id else None

    if d:
        old = _declaration_invoice(d.id)
        if old:
            flash(
                f'البيان {d.declaration_no} لديه فاتورة مسبقاً رقم {old.invoice_no}، لا يسمح بإنشاء فاتورة ثانية.',
                'warn'
            )
            return redirect(url_for('invoice_detail', iid=old.id))

    if request.method == 'POST':
        did_raw = (request.form.get('declaration_id') or '').strip()
        did = int(did_raw) if did_raw.isdigit() else None
        d = CustomsDeclaration.query.get(did) if did else None

        if did:
            old = _declaration_invoice(did)
            if old:
                flash(f'هذا البيان لديه فاتورة مسبقاً رقم {old.invoice_no}.', 'error')
                return redirect(url_for('invoice_detail', iid=old.id))

        items = _charge_lines_for_declaration(d)
        for i in range(1, 5):
            desc = (request.form.get(f'extra_desc_{i}') or '').strip()
            amount = _money(request.form.get(f'extra_amount_{i}'))
            if amount > 0:
                items.append((desc or f'بند إضافي {i}', amount))

        if not items:
            flash('لا توجد مبالغ للفوترة. أضف مبالغ للبيان أو بنداً إضافياً.', 'error')
            return redirect(url_for('invoice_new', declaration_id=did or ''))

        subtotal = sum(a for _, a in items)
        discount = max(0.0, _money(request.form.get('discount')))
        total = max(0.0, subtotal - discount)
        paid = min(total, max(0.0, _money(request.form.get('paid'))))
        status = 'مسددة' if total > 0 and paid >= total else ('جزئية' if paid > 0 else 'غير مسددة')

        company_id = d.company_id if d and d.company_id else (request.form.get('company_id') or None)
        job_id = None
        if d and getattr(d, 'transport_job_id', None):
            job_id = d.transport_job_id
        else:
            raw_job = (request.form.get('job_id') or '').strip()
            job_id = int(raw_job) if raw_job.isdigit() else None

        inv = SalesInvoice(
            invoice_no=(request.form.get('invoice_no') or '').strip() or core.next_invoice_no(),
            invoice_date=(request.form.get('invoice_date') or '').strip() or date.today().isoformat(),
            company_id=company_id,
            declaration_id=did,
            job_id=job_id,
            description=(request.form.get('description') or '').strip(),
            subtotal=subtotal,
            discount=discount,
            total=total,
            paid=paid,
            payment_method=(request.form.get('payment_method') or 'آجل').strip(),
            status=status,
        )
        try:
            db.session.add(inv)
            db.session.flush()
            for desc, amount in items:
                db.session.add(InvoiceLine(
                    invoice_id=inv.id, description=desc, qty=1,
                    unit_price=amount, amount=amount
                ))
            core.journal(
                'فاتورة مبيعات',
                [('1100', total, 0, inv.description or inv.invoice_no),
                 ('4000', 0, total, inv.description or inv.invoice_no)],
                'invoice', inv.id, inv.invoice_date
            )
            if paid > 0:
                db.session.add(CashTransaction(
                    txn_date=inv.invoice_date, direction='in', category='تحصيل فاتورة',
                    amount=paid, company_id=inv.company_id,
                    description=f'دفعة فاتورة {inv.invoice_no}',
                    reference=inv.invoice_no, created_by=session.get('username','')
                ))
                core.journal(
                    'تحصيل فاتورة',
                    [('1000', paid, 0, inv.invoice_no),
                     ('1100', 0, paid, inv.invoice_no)],
                    'invoice_payment', inv.id, inv.invoice_date
                )
            db.session.commit()
            try:
                core.audit('إنشاء فاتورة', 'invoice', inv.id, inv.invoice_no)
            except Exception:
                pass
            return redirect(url_for('invoice_detail', iid=inv.id))
        except Exception as e:
            db.session.rollback()
            if did:
                old = _declaration_invoice(did)
                if old:
                    flash('تم منع فاتورة مكررة لهذا البيان وفتح الفاتورة الموجودة.', 'warn')
                    return redirect(url_for('invoice_detail', iid=old.id))
            flash('تعذر حفظ الفاتورة: ' + str(e), 'error')

    used_ids = [
        r[0] for r in db.session.query(SalesInvoice.declaration_id)
        .filter(SalesInvoice.declaration_id.isnot(None)).all()
    ]
    q = CustomsDeclaration.query
    if used_ids:
        q = q.filter(~CustomsDeclaration.id.in_(used_ids))
    decls = q.order_by(CustomsDeclaration.id.desc()).all()

    preview = _charge_lines_for_declaration(d)
    preview_total = sum(a for _, a in preview)

    body = """
    <div class="hero"><h1>فاتورة جديدة</h1>
    <p>فاتورة واحدة فقط لكل بيان، وكل مبلغ يظهر كبند مستقل.</p></div>

    <div class="card no-print">
      <div class="section-title">1) اختر البيان</div>
      <div class="field">
        <label>البيان الجمركي</label>
        <select id="declPick">
          <option value="">— اختر البيان —</option>
          {% for x in decls %}
          <option value="{{x.id}}" {% if d and d.id==x.id %}selected{% endif %}>
            {{x.declaration_no}} — {{x.company.name if x.company else x.customer_name}}
          </option>
          {% endfor %}
        </select>
      </div>
      <script>
      document.getElementById('declPick').addEventListener('change', function(){
        var u='{{url_for("invoice_new")}}';
        location.href=this.value ? (u+'?declaration_id='+this.value) : u;
      });
      </script>
    </div>

    {% if d %}
    <div class="card">
      <div class="section-title">تفصيل مبالغ البيان التي ستظهر في الفاتورة</div>
      <div class="tablewrap"><table><thead><tr><th>البند</th><th>المبلغ</th></tr></thead><tbody>
        {% for desc,amt in preview %}
        <tr><td>{{desc}}</td><td>{{'%.2f'|format(amt)}}</td></tr>
        {% else %}
        <tr><td colspan="2" class="muted">لا توجد رسوم مضافة للبيان بعد.</td></tr>
        {% endfor %}
        <tr><th>المجموع</th><th>{{'%.2f'|format(preview_total)}}</th></tr>
      </tbody></table></div>
    </div>

    <div class="card">
      <form method="post">
        <input type="hidden" name="declaration_id" value="{{d.id}}">
        <input type="hidden" name="company_id" value="{{d.company_id or ''}}">
        <div class="formgrid">
          <div class="field"><label>رقم الفاتورة</label><input name="invoice_no" value="{{inv_no}}"></div>
          <div class="field"><label>التاريخ</label><input type="date" name="invoice_date" value="{{today}}"></div>
          <div class="field"><label>شركة العميل</label><input value="{{d.company.name if d.company else d.customer_name}}" disabled></div>
          <div class="field"><label>طريقة الدفع</label><select name="payment_method"><option>آجل</option><option>نقدي</option><option>تحويل</option></select></div>
          <div class="field full"><label>شرح الفاتورة</label><input name="description" value="خدمات البيان {{d.declaration_no}}"></div>
        </div>

        <div class="section-title" style="margin-top:16px">بنود إضافية — كل مبلغ في سطر مستقل</div>
        <div class="tablewrap"><table><thead><tr><th>شرح البند</th><th>المبلغ</th></tr></thead><tbody>
          {% for i in range(1,5) %}
          <tr><td><input name="extra_desc_{{i}}" placeholder="مثال: أجور إضافية"></td>
          <td><input name="extra_amount_{{i}}" type="number" min="0" step="0.01" value="0"></td></tr>
          {% endfor %}
        </tbody></table></div>

        <div class="formgrid" style="margin-top:12px">
          <div class="field"><label>الخصم</label><input name="discount" type="number" min="0" step="0.01" value="0"></div>
          <div class="field"><label>المدفوع الآن</label><input name="paid" type="number" min="0" step="0.01" value="0"></div>
        </div>
        <button class="btn green" style="margin-top:12px">حفظ الفاتورة</button>
      </form>
    </div>
    {% endif %}
    """
    return core.layout(
        'فاتورة جديدة', body, d=d, decls=decls, preview=preview,
        preview_total=preview_total, inv_no=core.next_invoice_no(),
        today=date.today().isoformat()
    )

app.view_functions['invoice_new'] = invoice_new_v4


def invoice_detail_v4(iid):
    if not session.get('uid'):
        return redirect(url_for('login'))
    x = SalesInvoice.query.get_or_404(iid)

    if request.method == 'POST':
        if not core.can_finance():
            flash('تسجيل الدفعات متاح للمحاسبة', 'error')
            return redirect(url_for('invoice_detail', iid=iid))
        amt = min(max(0.0, _money(request.form.get('amount'))), x.remaining)
        if amt > 0:
            dt = (request.form.get('date') or date.today().isoformat()).strip()
            x.paid = min(_money(x.total), _money(x.paid) + amt)
            x.status = 'مسددة' if x.paid >= x.total else 'جزئية'
            db.session.add(CashTransaction(
                txn_date=dt, direction='in', category='تحصيل فاتورة',
                amount=amt, company_id=x.company_id,
                description=(request.form.get('description') or f'دفعة {x.invoice_no}').strip(),
                reference=x.invoice_no, created_by=session.get('username','')
            ))
            core.journal(
                'تحصيل فاتورة',
                [('1000', amt, 0, x.invoice_no),
                 ('1100', 0, amt, x.invoice_no)],
                'invoice_payment', x.id, dt
            )
            db.session.commit()
            try:
                core.audit('دفعة فاتورة', 'invoice', x.id, str(amt))
            except Exception:
                pass
        return redirect(url_for('invoice_detail', iid=iid))

    lines = _invoice_display_lines(x)
    brand = core.get_setting(
        'company_name',
        'شركة نهضة سوريا للتخليص الجمركي والنقل بالترانزيت العربي والدولي'
    )
    address = core.get_setting('address','')
    phone = core.get_setting('phone','')
    currency = core.get_setting('currency','USD') or 'USD'

    body = """
    <div class="card" style="max-width:900px;margin:auto">
      <div style="display:flex;align-items:center;gap:18px;border-bottom:2px solid #0f766e;padding-bottom:14px;margin-bottom:14px">
        <img src="{{url_for('company_logo')}}" alt="Nahda"
             style="width:115px;height:115px;object-fit:contain;border-radius:12px">
        <div style="flex:1">
          <h1 style="margin:0;color:#102a43;font-size:24px">{{brand}}</h1>
          {% if address %}<div class="muted" style="margin-top:6px">{{address}}</div>{% endif %}
          {% if phone %}<div class="muted">هاتف: {{phone}}</div>{% endif %}
          <div style="margin-top:8px;font-weight:800">فاتورة رقم {{x.invoice_no}}</div>
        </div>
      </div>

      <div class="grid" style="margin-bottom:14px">
        <div><b>التاريخ:</b> {{x.invoice_date}}</div>
        <div><b>شركة العميل:</b> {{x.company.name if x.company else '—'}}</div>
        <div><b>رقم البيان:</b> {{x.declaration.declaration_no if x.declaration else '—'}}</div>
        <div><b>رقم السيارة:</b> {{x.declaration.vehicle_no if x.declaration else '—'}}</div>
      </div>

      <div class="section-title">تفاصيل المبالغ</div>
      <div class="tablewrap"><table style="min-width:0"><thead>
        <tr><th>#</th><th>شرح البند</th><th>الكمية</th><th>سعر الوحدة</th><th>المبلغ</th></tr>
      </thead><tbody>
        {% for l in lines %}
        <tr><td>{{loop.index}}</td><td>{{l.description}}</td>
        <td>{{'%.2f'|format(l.qty)}}</td>
        <td>{{'%.2f'|format(l.unit_price)}} {{currency}}</td>
        <td><b>{{'%.2f'|format(l.amount)}} {{currency}}</b></td></tr>
        {% endfor %}
      </tbody></table></div>

      <div style="margin-top:16px;margin-right:auto;max-width:380px">
        <table style="min-width:0">
          <tr><th>المجموع قبل الخصم</th><td>{{'%.2f'|format(x.subtotal or 0)}} {{currency}}</td></tr>
          <tr><th>الخصم</th><td>{{'%.2f'|format(x.discount or 0)}} {{currency}}</td></tr>
          <tr><th>الإجمالي</th><td><b>{{'%.2f'|format(x.total or 0)}} {{currency}}</b></td></tr>
          <tr><th>المدفوع</th><td>{{'%.2f'|format(x.paid or 0)}} {{currency}}</td></tr>
          <tr><th>المتبقي</th><td style="font-size:18px;color:#b42318">
            <b>{{'%.2f'|format(x.remaining)}} {{currency}}</b></td></tr>
        </table>
      </div>
    </div>

    <div class="toolbar no-print" style="justify-content:center;margin-top:14px">
      <button class="btn dark" onclick="window.print()">📄 حفظ PDF / طباعة</button>
      <a class="btn amber" href="{{url_for('entity_attachments',source_type='invoice',source_id=x.id)}}">📎 المرفقات</a>
    </div>

    {% if finance and x.remaining>0 %}
    <div class="card no-print" style="max-width:900px;margin:14px auto">
      <div class="section-title">تسجيل دفعة</div>
      <form method="post"><div class="formgrid">
        <div class="field"><label>التاريخ</label><input type="date" name="date" value="{{today}}"></div>
        <div class="field"><label>المبلغ</label><input type="number" min="0.01" max="{{x.remaining}}" step="0.01" name="amount" required></div>
        <div class="field full"><label>الشرح</label><input name="description" value="دفعة الفاتورة {{x.invoice_no}}"></div>
      </div><button class="btn green" style="margin-top:10px">تسجيل الدفعة</button></form>
    </div>
    {% endif %}
    """
    return core.layout(
        'الفاتورة ' + x.invoice_no, body, x=x, lines=lines, brand=brand,
        address=address, phone=phone, currency=currency,
        finance=core.can_finance(), today=date.today().isoformat()
    )

app.view_functions['invoice_detail'] = invoice_detail_v4


def debts_v4():
    if not session.get('uid'):
        return redirect(url_for('login'))
    q = (request.args.get('q') or '').strip()
    rows = debtmod._debt_rows(q)
    debt_total = sum(r['remaining'] for r in rows)
    gross_total = sum(r['total'] for r in rows)
    paid_total = sum(r['paid'] for r in rows)
    collector = session.get('role') == 'collector'

    body = """
    <div class="hero"><h1>الديون والتحصيل</h1>
    <p>البحث برقم السيارة أو رقم البيان وتسجيل دفعة مباشرة.</p></div>

    <form method="get" class="card no-print"><div class="toolbar">
      <label style="flex:1;min-width:240px">رقم السيارة أو رقم البيان
      <input name="q" value="{{q}}" placeholder="اكتب رقم السيارة أو البيان" autofocus></label>
      <button class="btn green">بحث</button>
      {% if q %}<a class="btn gray" href="{{url_for('debts')}}">الكل</a>{% endif %}
    </div></form>

    <div class="grid">
      <div class="card stat"><div class="label">إجمالي المستحق</div><div class="n">{{'%.2f'|format(gross_total)}}</div></div>
      <div class="card stat"><div class="label">المدفوع</div><div class="n">{{'%.2f'|format(paid_total)}}</div></div>
      <div class="card stat"><div class="label">الدين المتبقي</div><div class="n">{{'%.2f'|format(debt_total)}}</div></div>
    </div>

    <div class="card"><div class="tablewrap"><table>
      <thead><tr><th>رقم البيان</th><th>السيارة</th><th>الشركة</th><th>المستحق</th><th>المدفوع</th><th>المتبقي</th><th>إجراء</th></tr></thead>
      <tbody>
      {% for r in rows %}
      <tr><td>{{r.declaration_no}}</td><td>{{r.vehicles}}</td><td>{{r.company}}</td>
      <td>{{'%.2f'|format(r.total)}}</td><td>{{'%.2f'|format(r.paid)}}</td>
      <td style="color:#b42318;font-weight:800">{{'%.2f'|format(r.remaining)}}</td>
      <td>
        {% if r.invoice_ids and r.remaining>0 %}
          <a class="btn small green" href="{{url_for('debt_payment',iid=r.invoice_ids[0])}}">💵 تسجيل دفعة</a>
          {% if not collector %}
            <a class="btn small dark" href="{{url_for('invoice_detail',iid=r.invoice_ids[0])}}">الفاتورة</a>
          {% endif %}
        {% else %}<span class="muted">—</span>{% endif %}
      </td></tr>
      {% else %}
      <tr><td colspan="7" style="text-align:center;padding:25px">لا توجد نتائج</td></tr>
      {% endfor %}
      </tbody>
    </table></div></div>
    """
    return core.layout(
        'الديون', body, q=q, rows=rows, debt_total=debt_total,
        gross_total=gross_total, paid_total=paid_total, collector=collector
    )

app.view_functions['debts'] = debts_v4


@app.route('/debts/pay/<int:iid>', methods=['GET','POST'])
def debt_payment(iid):
    if not session.get('uid'):
        return redirect(url_for('login'))
    if session.get('role') not in ('admin','accountant','collector'):
        flash('ليس لديك صلاحية تحصيل الديون', 'error')
        return redirect(url_for('debts'))

    inv = SalesInvoice.query.get_or_404(iid)

    if request.method == 'POST':
        amount = min(max(0.0, _money(request.form.get('amount'))), inv.remaining)
        if amount <= 0:
            flash('أدخل مبلغاً صحيحاً', 'error')
            return redirect(url_for('debt_payment', iid=iid))
        dt = (request.form.get('date') or date.today().isoformat()).strip()

        inv.paid = min(_money(inv.total), _money(inv.paid) + amount)
        inv.status = 'مسددة' if inv.paid >= inv.total else 'جزئية'
        db.session.add(CashTransaction(
            txn_date=dt, direction='in', category='تحصيل دين',
            amount=amount, company_id=inv.company_id,
            description=(request.form.get('description') or f'تحصيل {inv.invoice_no}').strip(),
            reference=inv.invoice_no, created_by=session.get('username','')
        ))
        core.journal(
            'تحصيل دين',
            [('1000', amount, 0, inv.invoice_no),
             ('1100', 0, amount, inv.invoice_no)],
            'debt_collection', inv.id, dt
        )
        db.session.commit()
        try:
            core.audit('تحصيل دين', 'invoice', inv.id, f'{amount:.2f}')
        except Exception:
            pass

        flash(f'تم تسجيل دفعة {amount:.2f} بنجاح', 'success')
        return redirect(
            url_for('debts', q=inv.declaration.declaration_no if inv.declaration else '')
        )

    body = """
    <div class="hero"><h1>تسجيل دفعة دين</h1><p>الفاتورة {{inv.invoice_no}}</p></div>
    <div class="grid">
      <div class="card stat"><div class="label">الشركة</div>
        <div style="font-size:18px;font-weight:800">{{inv.company.name if inv.company else '—'}}</div></div>
      <div class="card stat"><div class="label">رقم البيان</div>
        <div style="font-size:18px;font-weight:800">{{inv.declaration.declaration_no if inv.declaration else '—'}}</div></div>
      <div class="card stat"><div class="label">المتبقي</div>
        <div class="n">{{'%.2f'|format(inv.remaining)}}</div></div>
    </div>

    <div class="card"><form method="post"><div class="formgrid">
      <div class="field"><label>التاريخ</label><input type="date" name="date" value="{{today}}" required></div>
      <div class="field"><label>المبلغ المقبوض</label>
        <input type="number" min="0.01" max="{{inv.remaining}}" step="0.01" name="amount" required autofocus></div>
      <div class="field full"><label>الشرح</label>
        <input name="description" value="تحصيل من الفاتورة {{inv.invoice_no}}"></div>
    </div>
    <button class="btn green" style="margin-top:12px">حفظ التحصيل</button>
    <a class="btn gray" href="{{url_for('debts')}}" style="margin-top:12px">رجوع</a>
    </form></div>
    """
    return core.layout('تحصيل دين', body, inv=inv, today=date.today().isoformat())


def users_v4():
    if not session.get('uid'):
        return redirect(url_for('login'))
    if session.get('role') != 'admin':
        flash('هذه الصفحة للمدير فقط', 'error')
        return redirect(url_for('home'))

    if request.method == 'POST':
        name = (request.form.get('username') or '').strip()
        role = (request.form.get('role') or 'viewer').strip()
        if role not in ROLE_LABELS:
            role = 'viewer'

        if User.query.filter_by(username=name).first():
            flash('اسم المستخدم موجود', 'error')
        elif not name or not request.form.get('password'):
            flash('أدخل اسم المستخدم وكلمة المرور', 'error')
        else:
            db.session.add(User(
                username=name,
                password_hash=generate_password_hash(request.form.get('password','')),
                role=role,
                active=True
            ))
            db.session.commit()
            flash('تمت إضافة المستخدم', 'success')
        return redirect(url_for('users'))

    rows = User.query.order_by(User.id.asc()).all()
    body = """
    <div class="hero"><h1>المستخدمون والصلاحيات</h1>
    <p>أضف محصل ديون لتكون واجهته مقتصرة على صفحة الديون والتحصيل فقط.</p></div>

    <div class="card no-print"><form method="post"><div class="formgrid">
      <div class="field"><label>اسم المستخدم</label><input name="username" required></div>
      <div class="field"><label>كلمة المرور</label><input type="password" name="password" required></div>
      <div class="field"><label>الصلاحية</label><select name="role">
        <option value="admin">مدير</option>
        <option value="accountant">محاسب</option>
        <option value="transport">نقل وترانزيت</option>
        <option value="user">موظف</option>
        <option value="viewer">مشاهدة فقط</option>
        <option value="collector">محصل ديون فقط</option>
      </select></div>
    </div><button class="btn">إضافة المستخدم</button></form></div>

    <div class="card"><div class="tablewrap"><table>
      <tr><th>ID</th><th>المستخدم</th><th>الصلاحية</th><th>الحالة</th></tr>
      {% for x in rows %}
      <tr><td>{{x.id}}</td><td>{{x.username}}</td>
      <td>{{labels.get(x.role,x.role)}}</td>
      <td>{{'فعال' if x.active else 'موقوف'}}</td></tr>
      {% endfor %}
    </table></div></div>
    """
    return core.layout('المستخدمون', body, rows=rows, labels=ROLE_LABELS)

app.view_functions['users'] = users_v4


@app.route('/invoice-v4-health')
def invoice_v4_health():
    return {
        'ok': True,
        'invoice_logo': True,
        'detailed_lines': True,
        'one_invoice_per_declaration': True,
        'collector_role': True,
        'collector_payment': True,
    }
