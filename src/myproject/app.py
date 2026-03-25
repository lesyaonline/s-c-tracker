"""
Веб-приложение для отслеживания акций и расчета прибыли
"""

from flask import Flask, render_template, request, jsonify
from datetime import datetime
import pandas as pd
from database_manager import StockDatabase

app = Flask(__name__)

# Инициализация базы данных
db = StockDatabase("stocks.db")


def calculate_profit(company_name, purchase_date, quantity):
    """
    Расчет прибыли от инвестиции

    Args:
        company_name (str): Название компании
        purchase_date (str): Дата покупки (дд.мм.гггг)
        quantity (int): Количество акций

    Returns:
        dict: Результат расчета
    """
    # Получаем цену покупки
    purchase_price = db.get_price_by_date(company_name, purchase_date)

    if purchase_price is None:
        return {
            'success': False,
            'error': f'Нет данных о цене {company_name} на дату {purchase_date}'
        }

    # Получаем текущую цену
    current_price = db.get_current_price(company_name)

    if current_price is None:
        return {
            'success': False,
            'error': 'Нет данных о текущей цене'
        }

    # Расчет прибыли
    total_cost = purchase_price * quantity
    total_current = current_price * quantity
    profit = total_current - total_cost
    profit_percent = (profit / total_cost) * 100

    return {
        'success': True,
        'company': company_name,
        'purchase_date': purchase_date,
        'purchase_price': purchase_price,
        'current_price': current_price,
        'quantity': quantity,
        'total_cost': total_cost,
        'total_current': total_current,
        'profit': profit,
        'profit_percent': profit_percent
    }


@app.route('/')
def index():
    """Главная страница"""
    companies = db.get_all_companies()
    return render_template('index.html', companies=companies)


@app.route('/api/calculate', methods=['GET'])
def calculate_profit_api():
    """
    API для расчета прибыли
    Параметры: company, date, quantity
    """
    company = request.args.get('company')
    date = request.args.get('date')
    quantity = request.args.get('quantity')

    # Проверка параметров
    if not company or not date or not quantity:
        return jsonify({
            'success': False,
            'error': 'Необходимо указать: company, date, quantity'
        }), 400

    try:
        quantity = int(quantity)
        if quantity <= 0:
            return jsonify({
                'success': False,
                'error': 'Количество акций должно быть положительным числом'
            }), 400
    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Количество акций должно быть целым числом'
        }), 400

    # Проверка формата даты
    try:
        datetime.strptime(date, '%d.%m.%Y')
    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Дата должна быть в формате дд.мм.гггг'
        }), 400

    # Расчет прибыли
    result = calculate_profit(company, date, quantity)

    if not result['success']:
        return jsonify(result), 404

    return jsonify(result)


@app.route('/api/companies')
def get_companies():
    """API для получения списка компаний"""
    companies = db.get_all_companies()
    return jsonify({'companies': companies})


@app.route('/api/prices/<company_name>')
def get_prices(company_name):
    """API для получения цен компании"""
    latest = db.get_latest_by_company(company_name)
    return jsonify(latest)


@app.route('/api/statistics')
def get_statistics():
    """API для получения статистики"""
    stats = db.get_statistics()
    return jsonify(stats)


@app.context_processor
def utility_processor():
    """Добавляет текущую дату в шаблоны"""
    return {'now': datetime.now()}


if __name__ == '__main__':
    print("🚀 Запуск веб-сервера...")
    print("📊 S&C Tracker - Система отслеживания акций")
    print("🌐 Откройте http://localhost:5000 в браузере")
    app.run(debug=True, host='0.0.0.0', port=5000)