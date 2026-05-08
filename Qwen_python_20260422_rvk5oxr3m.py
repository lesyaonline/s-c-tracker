"""
S&C Tracker - Система отслеживания инвестиционного портфеля
Акции + Криптовалюты с реальной аутентификацией
"""
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime, timedelta
import sqlite3
import requests
from functools import wraps
import json
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_change_this_12345'

# База данных
DB_NAME = 'portfolio.db'

# Список доступных акций MOEX
MOEX_STOCKS = {
    'SBER': 'Сбербанк',
    'GAZP': 'Газпром',
    'LKOH': 'Лукойл',
    'ROSN': 'Роснефть',
    'GMKN': 'Норникель',
    'NVTK': 'Новатэк',
    'MGNT': 'Магнит',
    'TATN': 'Татнефть',
    'YNDX': 'Яндекс',
    'CHMF': 'Северсталь'
}

# Список криптовалют
CRYPTO_ASSETS = {
    'bitcoin': 'Bitcoin (BTC)',
    'ethereum': 'Ethereum (ETH)',
    'solana': 'Solana (SOL)',
    'ripple': 'Ripple (XRP)',
    'dogecoin': 'Dogecoin (DOGE)',
    'binancecoin': 'BNB',
    'tether': 'Tether (USDT)',
    'usd-coin': 'USDC'
}

# Инициализация БД
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица активов
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
    
    # Таблица истории цен (для графика)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_code TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            price_date TEXT NOT NULL,
            price REAL NOT NULL,
            UNIQUE(asset_code, asset_type, price_date)
        )
    ''')
    
    conn.commit()
    conn.close()

# Декоратор для проверки авторизации
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Получение текущей цены акции MOEX
def get_moex_price(ticker):
    try:
        url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            market_data = data.get('marketdata', {}).get('data', [])
            if market_data and len(market_data) > 0:
                columns = data['marketdata']['columns']
                row = market_data[0]
                
                last_idx = columns.index('LAST') if 'LAST' in columns else -1
                if last_idx >= 0 and row[last_idx] is not None:
                    return float(row[last_idx])
        return None
    except:
        return None

# Получение текущей цены криптовалюты
def get_crypto_price(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get(coin_id, {}).get('usd')
        return None
    except:
        return None

# Получение исторической цены криптовалюты
def get_crypto_history(coin_id, date):
    try:
        date_obj = datetime.strptime(date, '%d.%m.%Y')
        date_str = date_obj.strftime('%d-%m-%Y')
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/history?date={date_str}&localization=false"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('market_data', {}).get('current_price', {}).get('usd')
        return None
    except:
        return None

# Страница входа
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form.get('login', '').strip()
        
        if not login:
            return render_template('login.html', error='Введите логин')
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Проверяем существование пользователя
        cursor.execute('SELECT id FROM users WHERE login = ?', (login,))
        user = cursor.fetchone()
        
        if not user:
            # Создаем нового пользователя
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

# Выход
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Главная страница (дашборд)
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', 
                         login=session.get('login'),
                         moex_stocks=MOEX_STOCKS,
                         crypto_assets=CRYPTO_ASSETS)

# API: Получение всех активов пользователя
@app.route('/api/assets')
@login_required
def get_assets():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, asset_type, asset_code, asset_name, quantity, 
               purchase_price, purchase_date, created_at
        FROM assets
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (session['user_id'],))
    
    assets = cursor.fetchall()
    conn.close()
    
    result = []
    for asset in assets:
        current_price = None
        
        if asset[1] == 'stock':
            current_price = get_moex_price(asset[2])
        else:
            current_price = get_crypto_price(asset[2])
        
        if current_price is None:
            current_price = asset[5]  # Используем цену покупки
        
        current_value = asset[4] * current_price
        purchase_value = asset[4] * asset[5]
        profit = current_value - purchase_value
        profit_percent = (profit / purchase_value) * 100 if purchase_value > 0 else 0
        
        result.append({
            'id': asset[0],
            'type': asset[1],
            'code': asset[2],
            'name': asset[3],
            'quantity': asset[4],
            'purchase_price': asset[5],
            'purchase_date': asset[6],
            'current_price': round(current_price, 2),
            'current_value': round(current_value, 2),
            'profit': round(profit, 2),
            'profit_percent': round(profit_percent, 2)
        })
    
    return jsonify(result)

# API: Добавление актива
@app.route('/api/assets', methods=['POST'])
@login_required
def add_asset():
    data = request.json
    
    asset_type = data.get('type')
    asset_code = data.get('code')
    asset_name = data.get('name')
    quantity = float(data.get('quantity'))
    purchase_price = float(data.get('purchase_price'))
    purchase_date = data.get('purchase_date')
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO assets (user_id, asset_type, asset_code, asset_name, 
                           quantity, purchase_price, purchase_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (session['user_id'], asset_type, asset_code, asset_name,
          quantity, purchase_price, purchase_date))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# API: Удаление актива
@app.route('/api/assets/<int:asset_id>', methods=['DELETE'])
@login_required
def delete_asset(asset_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        DELETE FROM assets WHERE id = ? AND user_id = ?
    ''', (asset_id, session['user_id']))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# API: Общая статистика портфеля
@app.route('/api/portfolio/stats')
@login_required
def portfolio_stats():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT asset_type, asset_code, asset_name, quantity, purchase_price
        FROM assets
        WHERE user_id = ?
    ''', (session['user_id'],))
    
    assets = cursor.fetchall()
    conn.close()
    
    total_investment = 0
    total_current = 0
    portfolio_data = []
    
    for asset in assets:
        asset_type, code, name, qty, purchase_price = asset
        
        if asset_type == 'stock':
            current_price = get_moex_price(code)
        else:
            current_price = get_crypto_price(code)
        
        if current_price is None:
            current_price = purchase_price
        
        investment = qty * purchase_price
        current_value = qty * current_price
        
        total_investment += investment
        total_current += current_value
        
        portfolio_data.append({
            'name': name,
            'value': current_value,
            'percent': 0
        })
    
    # Рассчитываем проценты
    if total_current > 0:
        for item in portfolio_data:
            item['percent'] = round((item['value'] / total_current) * 100, 2)
    
    total_profit = total_current - total_investment
    profit_percent = (total_profit / total_investment * 100) if total_investment > 0 else 0
    
    return jsonify({
        'total_investment': round(total_investment, 2),
        'total_current': round(total_current, 2),
        'total_profit': round(total_profit, 2),
        'profit_percent': round(profit_percent, 2),
        'assets': portfolio_data
    })

# API: Данные для графика (история портфеля за 7 дней)
@app.route('/api/portfolio/chart')
@login_required
def portfolio_chart():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT asset_type, asset_code, quantity, purchase_price, purchase_date
        FROM assets
        WHERE user_id = ?
    ''', (session['user_id'],))
    
    assets = cursor.fetchall()
    conn.close()
    
    if not assets:
        return jsonify({'labels': [], 'data': []})
    
    # Генерируем данные за последние 7 дней
    labels = []
    data = []
    
    for i in range(6, -1, -1):
        date = datetime.now() - timedelta(days=i)
        date_str = date.strftime('%d.%m.%Y')
        labels.append(date.strftime('%d.%m'))
        
        day_total = 0
        
        for asset in assets:
            asset_type, code, qty, purchase_price, purchase_date = asset
            
            # Если дата покупки позже текущей даты в цикле, пропускаем
            if datetime.strptime(purchase_date, '%d.%m.%Y') > date:
                continue
            
            # Получаем цену на эту дату
            if asset_type == 'stock':
                # Для акций используем текущую цену (упрощенно)
                price = get_moex_price(code) or purchase_price
            else:
                # Для крипты пробуем получить историческую цену
                price = get_crypto_history(code, date_str)
                if price is None:
                    price = get_crypto_price(code) or purchase_price
            
            day_total += qty * price
        
        data.append(round(day_total, 2))
    
    return jsonify({'labels': labels, 'data': data})

if __name__ == '__main__':
    init_db()
    print("🚀 Запуск S&C Tracker...")
    print("📊 http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)