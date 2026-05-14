"""
S&C Tracker — Основное Flask-приложение
Акции MOEX + Криптовалюты с реальными данными
"""
import re
import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from datetime import datetime, timedelta
from functools import wraps

import database as db
import prices as px

app = Flask(__name__)
app.secret_key = 'sc_tracker_secret_key_2024_change_this'

# ─── Справочники активов ──────────────────────────────────────────────────────

MOEX_STOCKS = {
    'SBER': 'Сбербанк',
    'GAZP': 'Газпром',
    'LKOH': 'Лукойл',
    'ROSN': 'Роснефть',
    'GMKN': 'Норильский никель',
    'NVTK': 'Новатэк',
    'MGNT': 'Магнит',
    'TATN': 'Татнефть',
    'TCSG': 'TCS Group',
    'CHMF': 'Северсталь',
    'YDEX': 'Яндекс',
    'VTBR': 'ВТБ',
}

CRYPTO_ASSETS = {
    'bitcoin':     'Bitcoin (BTC)',
    'ethereum':    'Ethereum (ETH)',
    'solana':      'Solana (SOL)',
    'dogecoin':    'Dogecoin (DOGE)',
    'ripple':      'Ripple (XRP)',
    'binancecoin': 'BNB',
    'tether-gold': 'Gold (XAUT)',
}

# ─── Декоратор авторизации ────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return wrapper

# ═══════════════════════════════════════════════════════════════════════════════
#  СТРАНИЦЫ
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/logo.png')
def serve_logo():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'logo.png')

@app.route('/', methods=['GET', 'POST'])
def login_page():
    session.clear()

    if request.method == 'POST':
        login_val = request.form.get('login', '').strip()

        # Валидация: только буквы RU/EN, не более 30 символов
        if not login_val:
            return render_template('login.html', error='Введите логин')
        if len(login_val) > 30:
            return render_template('login.html',
                                   error='Логин не должен превышать 30 символов')
        if not re.match(r'^[A-Za-zА-Яа-яЁё]+$', login_val):
            return render_template('login.html',
                                   error='Логин может содержать только буквы '
                                         '(русские или латинские), без пробелов и цифр')

        user_id = db.get_or_create_user(login_val)
        session['user_id'] = user_id
        session['login']   = login_val
        return redirect(url_for('dashboard'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html',
                           login=session.get('login'),
                           moex_stocks=MOEX_STOCKS,
                           crypto_assets=CRYPTO_ASSETS)


# ═══════════════════════════════════════════════════════════════════════════════
#  API АКТИВОВ
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/assets', methods=['GET'])
@login_required
def api_get_assets():
    """
    Получить список активов с расчитанными значениями.
    ?currency=usd|rub|cny
    """
    currency = request.args.get('currency', 'usd')
    rates    = px.get_rates()
    sym      = px.currency_symbol(currency)
    usd_rub  = rates['usd_rub']

    assets = db.get_user_assets(session['user_id'])
    result = []
    
    # Слияние активов по коду
    grouped = {}
    for a in assets:
        code = a['asset_code']
        if code not in grouped:
            grouped[code] = {
                'id': a['id'],
                'asset_type': a['asset_type'],
                'asset_code': code,
                'asset_name': a['asset_name'],
                'quantity': 0,
                'total_invest': 0
            }
        grouped[code]['quantity'] += a['quantity']
        grouped[code]['total_invest'] += (a['quantity'] * a['purchase_price'])

    for code, g in grouped.items():
        if g['quantity'] > 0:
            g['purchase_price'] = g['total_invest'] / g['quantity']
        else:
            g['purchase_price'] = 0

    for code, g in grouped.items():
        atype       = g['asset_type']
        qty         = g['quantity']
        p_price_usd = g['purchase_price']

        # Получаем текущую цену в USD
        if atype == 'stock':
            price_rub = px.get_moex_price(code)
            curr_usd  = (price_rub / usd_rub) if price_rub else p_price_usd
        else:
            curr_usd = px.get_crypto_price(code) or p_price_usd

        # ─── Ключевые расчёты ─────────────────────────────────
        invest_usd  = g['total_invest']
        current_usd = qty * curr_usd
        profit_usd  = current_usd - invest_usd
        profit_pct  = (profit_usd / invest_usd * 100) if invest_usd > 0 else 0

        def fmt(v):
            return round(px.convert_usd(v, currency, rates), 2)

        result.append({
            'id':             g['id'],
            'type':           atype,
            'code':           code,
            'name':           g['asset_name'],
            'quantity':       qty,
            'purchase_price': fmt(p_price_usd),
            'current_price':  fmt(curr_usd),
            'invest_value':   fmt(invest_usd),
            'current_value':  fmt(current_usd),
            'profit':         fmt(profit_usd),
            'profit_percent': round(profit_pct, 2),
            'purchase_date':  '—', # Указывается как средняя
            'currency_symbol': sym,
        })

    return jsonify(result)

@app.route('/api/assets', methods=['POST'])
@login_required
def api_add_asset():
    """
    Добавить актив.
    Тело: {type, code, name, quantity, purchase_price, purchase_date}
    """
    data  = request.get_json(force=True)
    atype = data.get('type', '')

    try:
        quantity = float(data.get('quantity', 0))
        price    = float(data.get('purchase_price', 0))
        cur      = data.get('currency', 'usd').lower()
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Некорректные числовые значения'}), 400

    rates = px.get_rates()
    # Конвертируем цену в USD
    if cur == 'rub':
        price = price / rates['usd_rub']
    elif cur == 'cny':
        price = (price * rates['cny_rub']) / rates['usd_rub']

    if quantity <= 0:
        return jsonify({'success': False, 'error': 'Количество должно быть больше нуля'}), 400
    if price <= 0:
        return jsonify({'success': False, 'error': 'Цена покупки должна быть больше нуля'}), 400

    if atype == 'stock':
        if quantity != int(quantity):
            return jsonify({'success': False, 'error': 'Количество акций должно быть целым числом'}), 400
        quantity = int(quantity)

    if not data.get('purchase_date'):
        return jsonify({'success': False, 'error': 'Укажите дату покупки'}), 400

    new_id = db.add_asset(
        user_id       = session['user_id'],
        asset_type    = atype,
        code          = data['code'],
        name          = data['name'],
        quantity      = quantity,
        purchase_price= price,
        purchase_date = data['purchase_date'],
    )
    return jsonify({'success': True, 'id': new_id})


@app.route('/api/assets/<int:asset_id>', methods=['DELETE'])
@login_required
def api_delete_asset(asset_id):
    db.delete_asset(asset_id, session['user_id'])
    return jsonify({'success': True})


@app.route('/api/portfolio/stats')
@login_required
def api_portfolio_stats():
    # ... Без изменений в stats ...
    currency = request.args.get('currency', 'usd')
    rates    = px.get_rates()
    usd_rub  = rates['usd_rub']

    assets = db.get_user_assets(session['user_id'])
    total_invest_usd  = 0.0
    total_current_usd = 0.0

    for a in assets:
        qty    = a['quantity']
        p_usd  = a['purchase_price']

        if a['asset_type'] == 'stock':
            rub = px.get_moex_price(a['asset_code'])
            c   = (rub / usd_rub) if rub else p_usd
        else:
            c = px.get_crypto_price(a['asset_code']) or p_usd

        total_invest_usd  += qty * p_usd
        total_current_usd += qty * c

    profit_usd = total_current_usd - total_invest_usd
    pct        = (profit_usd / total_invest_usd * 100) if total_invest_usd > 0 else 0

    def cv(v):
        return round(px.convert_usd(v, currency, rates), 2)

    return jsonify({
        'total_investment': cv(total_invest_usd), 
        'total_current':    cv(total_current_usd),
        'total_profit':     cv(profit_usd),       
        'profit_percent':   round(pct, 2),
        'currency_symbol':  px.currency_symbol(currency),
        'rates':            rates,
    })


@app.route('/api/portfolio/chart')
@login_required
def api_portfolio_chart():
    currency = request.args.get('currency', 'usd')
    rates    = px.get_rates()
    usd_rub  = rates['usd_rub']

    assets = db.get_user_assets(session['user_id'])
    if not assets:
        return jsonify({'labels': [], 'data': []})

    buy_dates = []
    for a in assets:
        try:
            buy_dates.append(datetime.strptime(a['purchase_date'], '%d.%m.%Y'))
        except Exception:
            pass
    if not buy_dates:
        return jsonify({'labels': [], 'data': []})

    today     = datetime.now()
    earliest  = min(buy_dates)
    start     = earliest
    days_load = (today - start).days + 5

    moex_hist   = {}
    crypto_hist = {}
    for a in assets:
        code = a['asset_code']
        if a['asset_type'] == 'stock' and code not in moex_hist:
            moex_hist[code] = px.get_moex_history(code, days=days_load)
        elif a['asset_type'] == 'crypto' and code not in crypto_hist:
            crypto_hist[code] = px.get_crypto_history(code, days=days_load)

    labels, data = [], []
    cur_date = start

    while cur_date.date() <= today.date():
        iso  = cur_date.strftime('%Y-%m-%d')
        day_total_usd = 0.0
        has_any = False

        for a in assets:
            try:
                buy_dt = datetime.strptime(a['purchase_date'], '%d.%m.%Y')
            except Exception:
                continue
            if cur_date.date() < buy_dt.date():
                continue

            qty   = a['quantity']
            p_usd = a['purchase_price']

            if a['asset_type'] == 'stock':
                hist       = moex_hist.get(a['asset_code'], {})
                price_rub  = hist.get(iso) or px.nearest_price(hist, iso)
                price_usd  = (price_rub / usd_rub) if price_rub else p_usd
            else:
                hist      = crypto_hist.get(a['asset_code'], {})
                price_usd = hist.get(iso) or px.nearest_price(hist, iso) or p_usd

            day_total_usd += qty * price_usd
            has_any = True

        if has_any:
            labels.append(cur_date.strftime('%d.%m'))
            data.append(round(px.convert_usd(day_total_usd, currency, rates), 2))

        cur_date += timedelta(days=1)

    return jsonify({'labels': labels, 'data': data})

@app.route('/api/rates')
@login_required
def api_rates():
    return jsonify(px.get_rates())

if __name__ == '__main__':
    db.init_db()
    print('🚀 S&C Tracker запускается...')
    print('📊 Откройте http://localhost:5000')
    app.run(debug=True, host='0.0.0.0', port=5000)
