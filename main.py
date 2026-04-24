"""
S&C Tracker - Система отслеживания инвестиционного портфеля
Акции MOEX + Криптовалюты с реальными данными
"""
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime, timedelta
import sqlite3
import requests
import json
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = 'sc_tracker_secret_key_2024_change_this'

# База данных
DB_NAME = 'portfolio.db'

# Акции MOEX
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
    'CHMF': 'Северсталь'
}

# Криптовалюты
CRYPTO_ASSETS = {
    'bitcoin': 'Bitcoin (BTC)',
    'ethereum': 'Ethereum (ETH)',
    'solana': 'Solana (SOL)',
    'dogecoin': 'Dogecoin (DOGE)',
    'ripple': 'Ripple (XRP)',
    'binancecoin': 'BNB',
    'tether': 'Tether (USDT)'
}

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            asset_type TEXT NOT NULL,
            asset_code TEXT NOT NULL,
            asset_name TEXT NOT NULL,
            quantity REAL NOT NULL,
            purchase_price REAL NOT NULL,
            purchase_date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ============ ФУНКЦИИ ДЛЯ MOEX ============

def get_moex_price(ticker):
    """Получение текущей цены акции с MOEX"""
    try:
        url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            market_data = data.get('marketdata', {}).get('data', [])
            market_cols = data.get('marketdata', {}).get('columns', [])
            
            if market_data and len(market_data) > 0:
                row = market_data[0]
                price_idx = market_cols.index('LAST') if 'LAST' in market_cols else -1
                
                if price_idx >= 0 and row[price_idx] is not None:
                    return float(row[price_idx])
        return None
    except Exception as e:
        print(f"MOEX Error: {e}")
        return None

def get_moex_history(ticker, days=7):
    """Получение исторических данных с MOEX за период"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days+10)
        
        url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{ticker}/history.json?from={start_date.strftime('%Y-%m-%d')}&till={end_date.strftime('%Y-%m-%d')}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            history = data.get('history', {}).get('data', [])
            columns = data.get('history', {}).get('columns', [])
            
            if history and columns:
                close_idx = columns.index('CLOSE') if 'CLOSE' in columns else -1
                last_idx = columns.index('LAST') if 'LAST' in columns else -1
                date_idx = columns.index('TRADEDATE') if 'TRADEDATE' in columns else -1
                
                history_dict = {}
                for row in history:
                    if date_idx >= 0 and row[date_idx]:
                        date_str = row[date_idx]
                        price = None
                        if close_idx >= 0 and row[close_idx] is not None:
                            price = float(row[close_idx])
                        elif last_idx >= 0 and row[last_idx] is not None:
                            price = float(row[last_idx])
                        
                        if price:
                            history_dict[date_str] = price
                
                return history_dict
        return {}
    except Exception as e:
        print(f"MOEX History Error: {e}")
        return {}

# ============ ФУНКЦИИ ДЛЯ КРИПТОВАЛЮТ ============

def get_crypto_price(coin_id):
    """Получение текущей цены криптовалюты"""
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get(coin_id, {}).get('usd')
        return None
    except Exception as e:
        print(f"Crypto Error: {e}")
        return None

def get_crypto_history(coin_id, date_str):
    """Получение исторической цены криптовалюты"""
    try:
        date_obj = datetime.strptime(date_str, '%d.%m.%Y')
        api_date = date_obj.strftime('%d-%m-%Y')
        
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/history?date={api_date}&localization=false"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            market_data = data.get('market_data', {})
            if market_data:
                current_price = market_data.get('current_price', {})
                if current_price:
                    return current_price.get('usd')
        return None
    except Exception as e:
        print(f"Crypto History Error: {e}")
        return None

def get_crypto_chart_data(coin_id, days=7):
    """Получение данных для графика с CoinGecko"""
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            prices = data.get('prices', [])
            
            chart_data = {}
            for price_point in prices:
                timestamp = price_point[0]
                price = price_point[1]
                date_str = datetime.fromtimestamp(timestamp / 1000).strftime('%d.%m.%Y')
                chart_data[date_str] = price
            
            return chart_data
        return {}
    except Exception as e:
        print(f"Crypto Chart Error: {e}")
        return {}

# ============ МАРШРУТЫ ============

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form.get('login', '').strip()
        if not login:
            return render_template('login.html', error='Введите логин')
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM users WHERE login = ?', (login,))
        user = cursor.fetchone()
        
        if not user:
            cursor.execute('INSERT INTO users (login) VALUES (?)', (login,))
            conn.commit()
            user_id = cursor.lastrowid
        else:
            user_id = user[0]
        
        conn.close()
        session['user_id'] = user_id
        session['login'] = login
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', 
                         login=session.get('login'),
                         moex_stocks=MOEX_STOCKS,
                         crypto_assets=CRYPTO_ASSETS)

@app.route('/api/assets')
@login_required
def get_assets():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, asset_type, asset_code, asset_name, quantity, 
               purchase_price, purchase_date
        FROM assets WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (session['user_id'],))
    
    assets = cursor.fetchall()
    conn.close()
    
    result = []
    for asset in assets:
        aid, atype, code, name, qty, p_price, p_date = asset
        
        current_price = None
        if atype == 'stock':
            current_price = get_moex_price(code)
        else:
            current_price = get_crypto_price(code)
        
        if current_price is None:
            current_price = p_price
        
        current_value = qty * current_price
        invest_value = qty * p_price
        profit = current_value - invest_value
        profit_pct = (profit / invest_value * 100) if invest_value > 0 else 0
        
        result.append({
            'id': aid,
            'type': atype,
            'code': code,
            'name': name,
            'quantity': qty,
            'purchase_price': p_price,
            'purchase_date': p_date,
            'current_price': round(current_price, 2),
            'current_value': round(current_value, 2),
            'profit': round(profit, 2),
            'profit_percent': round(profit_pct, 2)
        })
    
    return jsonify(result)

@app.route('/api/assets', methods=['POST'])
@login_required
def add_asset():
    data = request.json
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO assets (user_id, asset_type, asset_code, asset_name, 
                           quantity, purchase_price, purchase_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (session['user_id'], data['type'], data['code'], data['name'],
          float(data['quantity']), float(data['purchase_price']), data['purchase_date']))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/assets/<int:asset_id>', methods=['DELETE'])
@login_required
def delete_asset(asset_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM assets WHERE id = ? AND user_id = ?', (asset_id, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/portfolio/stats')
@login_required
def portfolio_stats():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT asset_type, asset_code, asset_name, quantity, purchase_price
        FROM assets WHERE user_id = ?
    ''', (session['user_id'],))
    assets = cursor.fetchall()
    conn.close()
    
    total_invest = 0
    total_current = 0
    
    for atype, code, name, qty, p_price in assets:
        curr_price = get_moex_price(code) if atype == 'stock' else get_crypto_price(code)
        if curr_price is None:
            curr_price = p_price
        
        total_invest += qty * p_price
        total_current += qty * curr_price
    
    profit = total_current - total_invest
    profit_pct = (profit / total_invest * 100) if total_invest > 0 else 0
    
    return jsonify({
        'total_investment': round(total_invest, 2),
        'total_current': round(total_current, 2),
        'total_profit': round(profit, 2),
        'profit_percent': round(profit_pct, 2)
    })

@app.route('/api/portfolio/chart')
@login_required
def portfolio_chart():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT asset_type, asset_code, quantity, purchase_price, purchase_date
        FROM assets WHERE user_id = ?
    ''', (session['user_id'],))
    assets = cursor.fetchall()
    conn.close()
    
    if not assets:
        return jsonify({'labels': [], 'data': []})
    
    # Получаем исторические данные для всех активов
    moex_history = {}
    crypto_history = {}
    
    for asset in assets:
        atype, code, qty, p_price, p_date = asset
        if atype == 'stock':
            if code not in moex_history:
                moex_history[code] = get_moex_history(code, days=7)
        else:
            if code not in crypto_history:
                crypto_history[code] = get_crypto_chart_data(code, days=7)
    
    labels = []
    data = []
    
    # Генерируем данные за последние 7 дней
    for i in range(6, -1, -1):
        date = datetime.now() - timedelta(days=i)
        date_str = date.strftime('%d.%m.%Y')
        labels.append(date.strftime('%d.%m'))
        
        day_total = 0
        
        for asset in assets:
            atype, code, qty, p_price, p_date = asset
            
            # Если актив куплен позже этой даты, пропускаем
            if datetime.strptime(p_date, '%d.%m.%Y') > date:
                continue
            
            # Получаем цену на конкретную дату
            if atype == 'stock':
                # Для акций используем исторические данные MOEX
                history = moex_history.get(code, {})
                # Пробуем найти точную дату или ближайшую
                price = history.get(date_str)
                if price is None:
                    # Если нет данных, используем текущую цену
                    price = get_moex_price(code) or p_price
            else:
                # Для крипты используем исторические данные CoinGecko
                history = crypto_history.get(code, {})
                price = history.get(date_str)
                if price is None:
                    # Если нет данных, пробуем API истории
                    price = get_crypto_history(code, date_str)
                    if price is None:
                        price = get_crypto_price(code) or p_price
            
            day_total += qty * price
        
        data.append(round(day_total, 2))
    
    return jsonify({'labels': labels, 'data': data})

if __name__ == '__main__':
    init_db()
    print("🚀 S&C Tracker запускается...")
    print("📊 http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)