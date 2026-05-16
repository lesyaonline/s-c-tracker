"""
S&C Tracker — Основное Flask-приложение
Акции MOEX + Криптовалюты с реальными данными
"""
import re
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime, timedelta
from functools import wraps

import database as db
import prices as px

app = Flask(__name__)
app.secret_key = 'sc_tracker_secret_key_2024_change_this'
# Сессия не сохраняется между перезапусками сервера
app.config['SESSION_PERMANENT'] = False

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

@app.route('/', methods=['GET', 'POST'])
def login_page():
    """
    Всегда показываем страницу входа при GET.
    Не редиректим автоматически в кабинет — при перезапуске сервера
    сессия сбрасывается и пользователь видит форму входа.
    """
    if request.method == 'POST':
        login_val = request.form.get('login', '').strip()

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
    Возвращает активы пользователя, сгруппированные по (type, code).
    Одинаковые активы объединяются в одну строку:
      - quantity = суммарное количество
      - avg_buy_price = средневзвешенная цена покупки (total_cost / total_qty)
    ?currency=usd|rub|cny
    """
    currency = request.args.get('currency', 'usd')
    rates    = px.get_rates()
    sym      = px.currency_symbol(currency)
    usd_rub  = rates['usd_rub']

    raw = db.get_user_assets(session['user_id'])

    # Группируем по (asset_type, asset_code)
    groups = {}
    for a in raw:
        key = (a['asset_type'], a['asset_code'])
        if key not in groups:
            groups[key] = {
                'ids':        [a['id']],
                'type':       a['asset_type'],
                'code':       a['asset_code'],
                'name':       a['asset_name'],
                'total_qty':  0.0,
                'total_cost': 0.0,        # сумма (qty * price_usd) — для средней
                'earliest':   a['purchase_date'],
            }
        g = groups[key]
        g['ids'].append(a['id']) if a['id'] not in g['ids'] else None
        g['total_qty']  += a['quantity']
        g['total_cost'] += a['quantity'] * a['purchase_price']  # всё в USD

    # ── Батч-загрузка текущих цен ───────────────────────────────────────────────
    # Один запрос на все крипто-активы (избегаем rate-limit CoinGecko)
    # Один запрос на все акции MOEX
    stock_codes  = [code for (atype, code) in groups if atype == 'stock']
    crypto_codes = [code for (atype, code) in groups if atype == 'crypto']

    moex_batch   = px.get_moex_prices_batch(stock_codes)   if stock_codes  else {}
    crypto_batch = px.get_crypto_prices_batch(crypto_codes) if crypto_codes else {}
    # ────────────────────────────────────────────────────────────────────────────

    result = []
    for (atype, code), g in groups.items():
        qty         = g['total_qty']
        total_cost  = g['total_cost']
        avg_buy_usd = total_cost / qty if qty > 0 else 0  # средняя цена покупки

        # Явная проверка на None — не допускаем тихий fallback через «or»
        if atype == 'stock':
            p_rub    = moex_batch.get(code)
            curr_usd = (p_rub / usd_rub) if p_rub is not None else avg_buy_usd
        else:
            p_usd    = crypto_batch.get(code)
            curr_usd = p_usd if p_usd is not None else avg_buy_usd

        invest_usd  = total_cost            # инвестиции = сумма покупок
        current_usd = qty * curr_usd        # текущий баланс
        profit_usd  = current_usd - invest_usd
        profit_pct  = (profit_usd / invest_usd * 100) if invest_usd > 0 else 0

        def cv(v):
            return round(px.convert_usd(v, currency, rates), 2)

        result.append({
            'ids':            g['ids'],
            'type':           atype,
            'code':           code,
            'name':           g['name'],
            'quantity':       qty,
            'avg_buy_price':  cv(avg_buy_usd),  # средняя цена покупки
            'current_price':  cv(curr_usd),
            'invest_value':   cv(invest_usd),
            'current_value':  cv(current_usd),
            'profit':         cv(profit_usd),
            'profit_percent': round(profit_pct, 2),
            'currency_symbol': sym,
        })

    return jsonify(result)


@app.route('/api/assets', methods=['POST'])
@login_required
def api_add_asset():
    """
    Добавить актив.
    Тело: {type, code, name, quantity, purchase_price, purchase_currency, purchase_date}
    purchase_currency: usd|rub|cny — валюта, в которой указана цена покупки.
    Цена конвертируется в USD и сохраняется в БД.
    """
    data  = request.get_json(force=True)
    atype = data.get('type', '')

    # ─── Валидация чисел ─────────────────────────────────────
    try:
        quantity = float(data.get('quantity', 0))
        price    = float(data.get('purchase_price', 0))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Некорректные числовые значения'}), 400

    if quantity <= 0:
        return jsonify({'success': False,
                        'error': 'Количество должно быть больше нуля'}), 400
    if price <= 0:
        return jsonify({'success': False,
                        'error': 'Цена покупки должна быть больше нуля'}), 400

    if atype == 'stock':
        if quantity != int(quantity):
            return jsonify({'success': False,
                            'error': 'Количество акций должно быть целым числом'}), 400
        quantity = int(quantity)

    # ─── Валидация даты — не из будущего ─────────────────────
    date_str = data.get('purchase_date', '')
    if not date_str:
        return jsonify({'success': False, 'error': 'Укажите дату покупки'}), 400
    try:
        purchase_dt = datetime.strptime(date_str, '%d.%m.%Y')
    except ValueError:
        return jsonify({'success': False, 'error': 'Неверный формат даты'}), 400

    if purchase_dt.date() > datetime.now().date():
        return jsonify({'success': False,
                        'error': 'Дата покупки не может быть в будущем'}), 400

    # ─── Конвертация цены в USD для единого хранения ─────────
    purchase_currency = data.get('purchase_currency', 'usd')
    rates     = px.get_rates()
    price_usd = px.to_usd(price, purchase_currency, rates)

    new_id = db.add_asset(
        user_id        = session['user_id'],
        asset_type     = atype,
        code           = data['code'],
        name           = data['name'],
        quantity       = quantity,
        purchase_price = price_usd,
        purchase_date  = date_str,
    )
    return jsonify({'success': True, 'id': new_id})


@app.route('/api/assets/group', methods=['DELETE'])
@login_required
def api_delete_asset_group():
    """Удалить все записи группы (список id)"""
    data = request.get_json(force=True)
    for aid in data.get('ids', []):
        db.delete_asset(int(aid), session['user_id'])
    return jsonify({'success': True})


@app.route('/api/assets/group/partial', methods=['DELETE'])
@login_required
def api_delete_partial():
    """Удалить часть позиции из группы."""
    data = request.get_json(force=True)
    ids  = [int(i) for i in data.get('ids', [])]
    try:
        qty = float(data.get('quantity', 0))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Некорректное количество'}), 400
    if qty <= 0:
        return jsonify({'success': False, 'error': 'Количество должно быть больше нуля'}), 400
    db.partial_delete_group(ids, qty, session['user_id'])
    return jsonify({'success': True})


@app.route('/api/assets/<int:asset_id>', methods=['DELETE'])
@login_required
def api_delete_asset(asset_id):
    db.delete_asset(asset_id, session['user_id'])
    return jsonify({'success': True})


# ═══════════════════════════════════════════════════════════════════════════════
#  API СТАТИСТИКА ПОРТФЕЛЯ
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/portfolio/stats')
@login_required
def api_portfolio_stats():
    """Суммарная статистика портфеля. ?currency=usd|rub|cny"""
    currency = request.args.get('currency', 'usd')
    rates    = px.get_rates()
    usd_rub  = rates['usd_rub']

    raw = db.get_user_assets(session['user_id'])

    # Группируем по (type, code) — правильный подсчёт средних
    groups = {}
    for a in raw:
        key = (a['asset_type'], a['asset_code'])
        if key not in groups:
            groups[key] = {'type': a['asset_type'], 'code': a['asset_code'],
                           'total_qty': 0.0, 'total_cost': 0.0}
        groups[key]['total_qty']  += a['quantity']
        groups[key]['total_cost'] += a['quantity'] * a['purchase_price']

    # ── Батч-загрузка текущих цен ───────────────────────────────────────────────
    stock_codes  = [code for (atype, code) in groups if atype == 'stock']
    crypto_codes = [code for (atype, code) in groups if atype == 'crypto']

    moex_batch   = px.get_moex_prices_batch(stock_codes)   if stock_codes  else {}
    crypto_batch = px.get_crypto_prices_batch(crypto_codes) if crypto_codes else {}
    # ────────────────────────────────────────────────────────────────────────────

    total_invest_usd  = 0.0
    total_current_usd = 0.0

    for (atype, code), g in groups.items():
        avg_buy = g['total_cost'] / g['total_qty'] if g['total_qty'] > 0 else 0
        if atype == 'stock':
            p_rub = moex_batch.get(code)
            c     = (p_rub / usd_rub) if p_rub is not None else avg_buy
        else:
            p_usd = crypto_batch.get(code)
            c     = p_usd if p_usd is not None else avg_buy
        total_invest_usd  += g['total_cost']
        total_current_usd += g['total_qty'] * c

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


# ═══════════════════════════════════════════════════════════════════════════════
#  API ГРАФИК ПОРТФЕЛЯ
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/portfolio/chart')
@login_required
def api_portfolio_chart():
    """
    Исторический график суммарной стоимости портфеля.
    ?days=7|30|90  &currency=usd|rub|cny
    Строится с момента самой ранней покупки до сегодня.
    Каждая точка = сумма (qty_i × price_i(day)) по всем активам,
    которые уже были куплены на этот день.
    """
    period   = int(request.args.get('days', 7))
    currency = request.args.get('currency', 'usd')
    rates    = px.get_rates()
    usd_rub  = rates['usd_rub']

    raw = db.get_user_assets(session['user_id'])
    if not raw:
        return jsonify({'labels': [], 'data': []})

    # Определяем самую раннюю дату покупки
    buy_dates = []
    for a in raw:
        try:
            buy_dates.append(datetime.strptime(a['purchase_date'], '%d.%m.%Y'))
        except Exception:
            pass
    if not buy_dates:
        return jsonify({'labels': [], 'data': []})

    today     = datetime.now()
    earliest  = min(buy_dates)
    start     = max(earliest, today - timedelta(days=period))
    days_load = (today - start).days + 5

    # Группируем активы по (type, code): суммируем qty и cost
    groups = {}
    for a in raw:
        key = (a['asset_type'], a['asset_code'])
        if key not in groups:
            groups[key] = {
                'type':       a['asset_type'],
                'code':       a['asset_code'],
                'total_qty':  0.0,
                'total_cost': 0.0,
                'earliest':   datetime.strptime(a['purchase_date'], '%d.%m.%Y'),
            }
        g = groups[key]
        g['total_qty']  += a['quantity']
        g['total_cost'] += a['quantity'] * a['purchase_price']
        d = datetime.strptime(a['purchase_date'], '%d.%m.%Y')
        if d < g['earliest']:
            g['earliest'] = d

    # ── Параллельная загрузка истории цен ──────────────────────────────────────
    moex_hist   = {}
    crypto_hist = {}

    def _fetch_history(key):
        atype, code = key
        try:
            if atype == 'stock':
                return key, px.get_moex_history(code, days=days_load)
            else:
                return key, px.get_crypto_history(code, days=days_load)
        except Exception:
            return key, {}

    unique_keys = list(groups.keys())
    if unique_keys:
        with ThreadPoolExecutor(max_workers=len(unique_keys)) as ex:
            for (atype, code), hist in ex.map(_fetch_history, unique_keys):
                if atype == 'stock':
                    moex_hist[code] = hist
                else:
                    crypto_hist[code] = hist
    # ────────────────────────────────────────────────────────────────────────────

    labels, data = [], []
    cur_date = start

    while cur_date.date() <= today.date():
        iso           = cur_date.strftime('%Y-%m-%d')
        day_total_usd = 0.0
        has_any       = False

        for (atype, code), g in groups.items():
            # Актив учитывается только начиная с даты своей первой покупки
            if cur_date.date() < g['earliest'].date():
                continue

            qty     = g['total_qty']
            avg_buy = g['total_cost'] / qty if qty > 0 else 0

            if atype == 'stock':
                hist      = moex_hist.get(code, {})
                p_rub     = hist.get(iso) or px.nearest_price(hist, iso)
                price_usd = (p_rub / usd_rub) if p_rub else avg_buy
            else:
                hist      = crypto_hist.get(code, {})
                price_usd = hist.get(iso) or px.nearest_price(hist, iso) or avg_buy

            day_total_usd += qty * price_usd
            has_any = True

        if has_any:
            labels.append(cur_date.strftime('%d.%m'))
            data.append(round(px.convert_usd(day_total_usd, currency, rates), 2))

        cur_date += timedelta(days=1)

    return jsonify({'labels': labels, 'data': data})


# ─── API курсы ────────────────────────────────────────────────────────────────

@app.route('/api/rates')
@login_required
def api_rates():
    return jsonify(px.get_rates())


# ─── Запуск ───────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    db.init_db()
    print('🚀 S&C Tracker запускается...')
    print('📊 Откройте http://localhost:5000')
    app.run(debug=True, host='0.0.0.0', port=5000)
