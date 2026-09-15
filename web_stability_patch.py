# -*- coding: utf-8 -*-
"""Stability/UI patch for Nahda Web V3.
- Keeps uid/user_id session keys compatible with extension layers.
- Puts Debts in the real sidebar/mobile navigation.
- Keeps Logout always visible, including mobile.
- Makes journal page operational with balanced manual entries.
- Replaces layout signature so reports can safely pass a context variable named title.
"""
from datetime import date

import web_debt_patch as base
from flask import request, session, redirect, url_for, flash, render_template_string
from markupsafe import escape

app = base.app
core = base.core
db = base.db

Account = core.Account
JournalEntry = core.JournalEntry
JournalLine = core.JournalLine


@app.before_request
def _compat_session_keys():
    # Core V3 authenticates with `uid`; earlier extension layers used `user_id`.
    # Keep both in sync so CRUD/debt features work under the same login session.
    if session.get('uid') and not session.get('user_id'):
        session['user_id'] = session.get('uid')
    elif session.get('user_id') and not session.get('uid'):
        session['uid'] = session.get('user_id')


def _nav_items():
    items = list(core.NAV_ITEMS)
    if not any(ep == 'debts' for _, _, ep in items):
        pos = next((i + 1 for i, (_, _, ep) in enumerate(items) if ep == 'accounting'), len(items))
        items.insert(pos, ('💳', 'الديون', 'debts'))
    return items


def _href(endpoint):
    try:
        return url_for(endpoint)
    except Exception:
        return '#'


def _active(href):
    if href in ('', '#'):
        return ''
    p = request.path or '/'
    if href == '/':
        return ' active' if p == '/' else ''
    return ' active' if p == href or p.startswith(href.rstrip('/') + '/') else ''


def fixed_layout(page_title, body, **ctx):
    items = _nav_items()
    nav = ''.join(
        f'<a class="{_active(_href(ep)).strip()}" href="{_href(ep)}"><span>{ic}</span>{tx}</a>'
        for ic, tx, ep in items
    )
    admin = ''
    if session.get('role') == 'admin':
        admin += f'<a href="{_href("users")}">👤 المستخدمون</a>'
        admin += f'<a href="{_href("settings")}">⚙ الإعدادات</a>'
        admin += f'<a href="{_href("audit_page")}">🛡 سجل التدقيق</a>'
    admin += f'<a href="{_href("logout")}">↩ تسجيل خروج</a>'
    mobile = ''.join(f'<a href="{_href(ep)}">{tx}</a>' for _, tx, ep in items)
    mobile += f'<a href="{_href("logout")}" style="background:#991b1b">تسجيل خروج</a>'
    logout_top = f'<a class="btn red small no-print" href="{_href("logout")}" style="margin-right:12px">تسجيل خروج</a>'
    html = f'''<!doctype html><html lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(page_title)}</title><style>{core.CSS}</style></head><body><div class="layout"><aside class="side"><div class="brand"><h2>{{{{company_name}}}}</h2><small>التخليص الجمركي • الترانزيت • المحاسبة</small></div>{nav}{admin}</aside><main class="main"><div class="top"><div class="title">{escape(page_title)}</div><div class="user">{{{{session.get('username')}}}} • {{{{session.get('role')}}}}</div>{logout_top}</div><div class="mobilebar">{mobile}</div><div class="content">{{% with ms=get_flashed_messages(with_categories=true) %}}{{% for c,m in ms %}}<div class="flash {{{{c}}}}">{{{{m}}}}</div>{{% endfor %}}{{% endwith %}}{body}</div></main></div></body></html>'''
    return render_template_string(
        html,
        company_name=core.get_setting('company_name', 'نهضة سوريا للتخليص الجمركي والنقل'),
        **ctx,
    )

# Replacing the module-level global fixes all existing pages, including /reports,
# whose old call passed a template context key named `title`.
core.layout = fixed_layout


def _money(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def fixed_journal_page():
    if not session.get('uid'):
        return redirect(url_for('login'))
    q = (request.args.get('q') or '').strip()
    dt = (request.args.get('date') or '').strip()
    query = JournalEntry.query
    if q:
        like = f'%{q}%'
        query = query.filter(db.or_(JournalEntry.description.ilike(like), JournalEntry.ref_type.ilike(like)))
    if dt:
        query = query.filter_by(entry_date=dt)
    rows = query.order_by(JournalEntry.id.desc()).limit(500).all()
    accounts = Account.query.filter_by(active=True).order_by(Account.code.asc()).all() if core.can_finance() else []
    body = '''
    <div class="hero"><h1>القيود اليومية والترحيل</h1><p>عرض القيود الآلية وإضافة قيد يدوي متوازن مدين / دائن.</p></div>
    {% if finance %}
    <div class="card no-print">
      <div class="section-title">إضافة قيد يومي يدوي</div>
      <form method="post" action="{{url_for('journal_add')}}">
        <div class="formgrid">
          <div class="field"><label>التاريخ</label><input type="date" name="entry_date" value="{{today}}" required></div>
          <div class="field full"><label>البيان / شرح القيد</label><input name="description" required placeholder="مثال: تسوية حساب شركة ..."></div>
        </div>
        <div class="tablewrap" style="margin-top:12px"><table style="min-width:720px"><thead><tr><th>الحساب</th><th>مدين</th><th>دائن</th><th>ملاحظة</th></tr></thead><tbody>
        {% for i in range(1,5) %}<tr>
          <td><select name="account_{{i}}" style="width:100%;padding:8px"><option value="">— اختر الحساب —</option>{% for a in accounts %}<option value="{{a.id}}">{{a.code}} — {{a.name}}</option>{% endfor %}</select></td>
          <td><input name="debit_{{i}}" type="number" min="0" step="0.01" value="0" style="width:120px"></td>
          <td><input name="credit_{{i}}" type="number" min="0" step="0.01" value="0" style="width:120px"></td>
          <td><input name="note_{{i}}" placeholder="اختياري"></td>
        </tr>{% endfor %}
        </tbody></table></div>
        <div class="muted" style="margin:10px 0">يجب أن يكون مجموع المدين مساوياً لمجموع الدائن، ولا يُحفظ القيد غير المتوازن.</div>
        <button class="btn green" type="submit">حفظ وترحيل القيد</button>
      </form>
    </div>
    {% endif %}
    <div class="card no-print"><form method="get" class="search"><input name="q" value="{{q}}" placeholder="بحث بالبيان أو نوع المرجع"><input type="date" name="date" value="{{dt}}"><span></span><button class="btn">بحث</button></form></div>
    <div class="card"><div class="tablewrap"><table><thead><tr><th>#</th><th>التاريخ</th><th>البيان</th><th>المرجع</th><th>مدين</th><th>دائن</th><th>تفاصيل الحسابات</th></tr></thead><tbody>
    {% for x in rows %}<tr>
      <td>{{x.id}}</td><td>{{x.entry_date}}</td><td>{{x.description}}</td><td>{{x.ref_type}} {{x.ref_id or ''}}</td>
      <td>{{'%.2f'|format(x.lines|sum(attribute='debit'))}}</td><td>{{'%.2f'|format(x.lines|sum(attribute='credit'))}}</td>
      <td>{% for l in x.lines %}<div style="margin:2px 0"><b>{{l.account.code if l.account else ''}} {{l.account.name if l.account else ''}}</b> — {% if l.debit %}مدين {{'%.2f'|format(l.debit)}}{% endif %}{% if l.credit %}دائن {{'%.2f'|format(l.credit)}}{% endif %} {{l.note}}</div>{% endfor %}</td>
    </tr>{% else %}<tr><td colspan="7" style="text-align:center;padding:25px" class="muted">لا توجد قيود مطابقة</td></tr>{% endfor %}
    </tbody></table></div></div>
    '''
    return core.layout('القيود اليومية', body, rows=rows, accounts=accounts, finance=core.can_finance(), today=date.today().isoformat(), q=q, dt=dt)

# Existing /journal URL keeps the same endpoint, but now renders the operational page.
app.view_functions['journal_page'] = fixed_journal_page


@app.route('/journal/add', methods=['POST'])
def journal_add():
    if not session.get('uid'):
        return redirect(url_for('login'))
    if not core.can_finance():
        flash('إضافة القيود اليدوية متاحة للمدير أو المحاسب فقط', 'error')
        return redirect(url_for('journal_page'))
    entry_date = (request.form.get('entry_date') or date.today().isoformat()).strip()
    description = (request.form.get('description') or '').strip()
    if not description:
        flash('اكتب شرح القيد', 'error')
        return redirect(url_for('journal_page'))
    lines = []
    total_debit = 0.0
    total_credit = 0.0
    try:
        for i in range(1, 5):
            aid = (request.form.get(f'account_{i}') or '').strip()
            debit = _money(request.form.get(f'debit_{i}'))
            credit = _money(request.form.get(f'credit_{i}'))
            note = (request.form.get(f'note_{i}') or '').strip()
            if debit < 0 or credit < 0:
                raise ValueError('لا يسمح بمبلغ سالب')
            if debit > 0 and credit > 0:
                raise ValueError(f'السطر {i}: لا يجوز أن يكون الحساب مديناً ودائناً بنفس السطر')
            if debit <= 0 and credit <= 0:
                continue
            if not aid:
                raise ValueError(f'السطر {i}: اختر الحساب')
            acc = Account.query.get(int(aid))
            if not acc or not acc.active:
                raise ValueError(f'السطر {i}: الحساب غير صالح')
            lines.append((acc.id, debit, credit, note))
            total_debit += debit
            total_credit += credit
        if len(lines) < 2:
            raise ValueError('القيد يحتاج سطرين ماليين على الأقل')
        if total_debit <= 0 or total_credit <= 0:
            raise ValueError('يجب وجود طرف مدين وطرف دائن')
        if abs(total_debit - total_credit) > 0.005:
            raise ValueError(f'القيد غير متوازن: المدين {total_debit:.2f} والدائن {total_credit:.2f}')
        entry = JournalEntry(entry_date=entry_date, description=description, ref_type='manual', posted=True)
        db.session.add(entry)
        db.session.flush()
        for aid, debit, credit, note in lines:
            db.session.add(JournalLine(entry_id=entry.id, account_id=aid, debit=debit, credit=credit, note=note))
        db.session.commit()
        try:
            core.audit('إضافة قيد يدوي', 'journal', entry.id, description)
        except Exception:
            pass
        flash(f'تم حفظ وترحيل القيد رقم {entry.id} بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        flash('تعذر حفظ القيد: ' + str(e), 'error')
    return redirect(url_for('journal_page'))


@app.route('/stability-health')
def stability_health():
    return {'ok': True, 'version': 'V3.3', 'debts': True, 'mobile_logout': True, 'manual_journal': True, 'reports_layout_fix': True}
