# -*- coding: utf-8 -*-
"""Hotfix: reliable invoice editing and stale generic edit redirects."""
import re
import web_invoice_collector_patch as base
import web_crud_patch as crud
from flask import request, session, redirect, url_for, flash

app = base.app
core = base.core
db = base.db
SalesInvoice = core.SalesInvoice
Company = core.Company
CustomsDeclaration = core.CustomsDeclaration
TransportJob = core.TransportJob

# Do not let the generic table injector guess invoice IDs. Invoices render their own actions.
crud.PATH_ENTITY.pop('/invoices', None)

@app.before_request
def invoice_edit_legacy_redirect():
    m = re.fullmatch(r'/crud/edit/invoice/(\d+)', request.path or '')
    if m and session.get('uid'):
        iid = int(m.group(1))
        inv = SalesInvoice.query.get(iid)
        if not inv:
            flash('الفاتورة المطلوبة غير موجودة أو تم حذفها. تم إعادتك إلى قائمة الفواتير.', 'warn')
            return redirect(url_for('invoices'))
        return redirect(url_for('invoice_edit_v5', iid=iid))
    return None

@app.route('/invoices/<int:iid>/edit', methods=['GET','POST'])
def invoice_edit_v5(iid):
    if not session.get('uid'):
        return redirect(url_for('login'))
    if session.get('role') not in ('admin','accountant'):
        flash('تعديل الفواتير متاح للمدير أو المحاسب فقط', 'error')
        return redirect(url_for('invoices'))
    inv = SalesInvoice.query.get(iid)
    if not inv:
        flash('الفاتورة غير موجودة', 'error')
        return redirect(url_for('invoices'))

    if request.method == 'POST':
        try:
            new_decl = request.form.get('declaration_id', type=int)
            if new_decl:
                other = SalesInvoice.query.filter(SalesInvoice.declaration_id == new_decl, SalesInvoice.id != inv.id).first()
                if other:
                    flash(f'البيان لديه فاتورة مسبقاً رقم {other.invoice_no}. لا يسمح بربط فاتورتين بنفس البيان.', 'error')
                    return redirect(url_for('invoice_edit_v5', iid=iid))
            inv.invoice_date = (request.form.get('invoice_date') or inv.invoice_date or '').strip()
            inv.company_id = request.form.get('company_id', type=int) or None
            inv.declaration_id = new_decl or None
            inv.job_id = request.form.get('job_id', type=int) or None
            inv.payment_method = (request.form.get('payment_method') or inv.payment_method or '').strip()
            inv.description = (request.form.get('description') or '').strip()
            db.session.commit()
            try:
                core.audit('تعديل فاتورة', 'invoice', inv.id, inv.invoice_no)
            except Exception:
                pass
            flash('تم تعديل بيانات الفاتورة بنجاح', 'success')
            return redirect(url_for('invoice_detail', iid=inv.id))
        except Exception as e:
            db.session.rollback()
            flash('تعذر تعديل الفاتورة: ' + str(e), 'error')

    comps = Company.query.order_by(Company.name.asc()).all()
    decls = CustomsDeclaration.query.order_by(CustomsDeclaration.id.desc()).all()
    trips = TransportJob.query.order_by(TransportJob.id.desc()).all()
    body = '''
    <div class="hero"><h1>تعديل الفاتورة {{inv.invoice_no}}</h1><p>تعديل بيانات الربط والوصف بدون العبث بسجل الدفعات.</p></div>
    <div class="card"><form method="post"><div class="formgrid">
      <div class="field"><label>التاريخ</label><input type="date" name="invoice_date" value="{{inv.invoice_date}}"></div>
      <div class="field"><label>الشركة</label><select name="company_id"><option value="">—</option>{% for c in comps %}<option value="{{c.id}}" {% if inv.company_id==c.id %}selected{% endif %}>{{c.name}}</option>{% endfor %}</select></div>
      <div class="field"><label>البيان</label><select name="declaration_id"><option value="">—</option>{% for d in decls %}<option value="{{d.id}}" {% if inv.declaration_id==d.id %}selected{% endif %}>{{d.declaration_no}}</option>{% endfor %}</select></div>
      <div class="field"><label>الرحلة</label><select name="job_id"><option value="">—</option>{% for j in trips %}<option value="{{j.id}}" {% if inv.job_id==j.id %}selected{% endif %}>#{{j.id}} - {{j.manifest_no}}</option>{% endfor %}</select></div>
      <div class="field"><label>طريقة الدفع</label><select name="payment_method">{% for p in ['نقدي','تحويل','آجل'] %}<option {% if inv.payment_method==p %}selected{% endif %}>{{p}}</option>{% endfor %}</select></div>
      <div class="field full"><label>بيان الفاتورة</label><input name="description" value="{{inv.description or ''}}"></div>
    </div><div class="toolbar" style="margin-top:14px"><button class="btn green">حفظ التعديل</button><a class="btn gray" href="{{url_for('invoice_detail',iid=inv.id)}}">إلغاء</a></div></form></div>
    <div class="card"><div class="section-title">بنود الفاتورة</div><div class="tablewrap"><table><thead><tr><th>الشرح</th><th>الكمية</th><th>سعر الوحدة</th><th>المبلغ</th></tr></thead><tbody>{% for l in inv.lines %}<tr><td>{{l.description}}</td><td>{{'%.2f'|format(l.qty or 0)}}</td><td>{{'%.2f'|format(l.unit_price or 0)}}</td><td>{{'%.2f'|format(l.amount or 0)}}</td></tr>{% else %}<tr><td colspan="4">لا توجد بنود</td></tr>{% endfor %}</tbody></table></div></div>
    '''
    return core.layout('تعديل الفاتورة', body, inv=inv, comps=comps, decls=decls, trips=trips)


def invoices_v5():
    if not session.get('uid'):
        return redirect(url_for('login'))
    rows = SalesInvoice.query.order_by(SalesInvoice.id.desc()).all()
    body = '''
    <div class="hero"><h1>الفواتير</h1><p>فاتورة واحدة لكل بيان، مع بنود مفصلة والمدفوع والمتبقي.</p></div>
    <div class="toolbar no-print"><a class="btn" href="{{url_for('invoice_new')}}">＋ فاتورة جديدة</a><button class="btn dark" onclick="window.print()">PDF / طباعة</button></div>
    <div class="card"><div class="tablewrap"><table><thead><tr><th>رقم الفاتورة</th><th>التاريخ</th><th>الشركة</th><th>البيان</th><th>الإجمالي</th><th>المدفوع</th><th>المتبقي</th><th>الحالة</th><th>إجراءات</th></tr></thead><tbody>
    {% for x in rows %}<tr><td>{{x.invoice_no}}</td><td>{{x.invoice_date}}</td><td>{{x.company.name if x.company else '—'}}</td><td>{{x.declaration.declaration_no if x.declaration else '—'}}</td><td>{{'%.2f'|format(x.total or 0)}}</td><td>{{'%.2f'|format(x.paid or 0)}}</td><td class="amount">{{'%.2f'|format(x.remaining)}}</td><td>{{x.status}}</td><td style="white-space:nowrap"><a class="btn small dark" href="{{url_for('invoice_detail',iid=x.id)}}">فتح</a> {% if session.get('role') in ['admin','accountant'] %}<a class="btn small blue" href="{{url_for('invoice_edit_v5',iid=x.id)}}">تعديل</a>{% endif %}</td></tr>{% else %}<tr><td colspan="9" class="muted" style="text-align:center;padding:25px">لا توجد فواتير</td></tr>{% endfor %}
    </tbody></table></div></div>'''
    return core.layout('الفواتير', body, rows=rows)

app.view_functions['invoices'] = invoices_v5

@app.route('/invoice-hotfix-health')
def invoice_hotfix_health():
    return {'ok': True, 'invoice_edit': True, 'legacy_redirect': True, 'explicit_invoice_actions': True}
