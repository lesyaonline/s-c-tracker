"""
Модуль для сбора данных с Московской биржи
Возвращает данные в формате JSON и сохраняет в базу данных
"""

import requests
import pandas as pd
from datetime import datetime
import time
import json
import os


def get_moex_data_direct():
    """
    Получение данных напрямую с API Московской биржи (ISS MOEX)

    Returns:
        list: Список словарей с данными по каждой компании
    """

    companies = {
        'SBER': 'Сбербанк',
        'GAZP': 'Газпром',
        'LKOH': 'Лукойл',
        'ROSN': 'Роснефть',
        'GMKN': 'Норильский никель',
        'NVTK': 'Новатэк',
        'MGNT': 'Магнит',
        'TATN': 'Татнефть',
        'TCSG': 'TCS Group (Тинькофф)',
        'CHMF': 'Северсталь'
    }

    stocks_data = []
    current_date = datetime.now().strftime('%d.%m.%Y')  # Формат даты: дд.мм.гггг

    print(f"\n📊 Загрузка данных с Московской биржи ({datetime.now().strftime('%H:%M:%S')})")
    print("=" * 60)

    for ticker, company_name in companies.items():
        try:
            # API Московской биржи (ISS)
            url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # Получаем данные о последней сделке
                market_data = data.get('marketdata', {}).get('data', [])
                market_cols = data.get('marketdata', {}).get('columns', [])

                if market_data and len(market_data) > 0:
                    row = market_data[0]
                    cols = market_cols

                    # Индексы основных полей
                    price_idx = cols.index('LAST') if 'LAST' in cols else -1
                    change_idx = cols.index('LASTCHANGEPRCNT') if 'LASTCHANGEPRCNT' in cols else -1

                    if price_idx >= 0 and row[price_idx] is not None:
                        current_price = float(row[price_idx])
                        change_percent = float(row[change_idx]) if change_idx >= 0 and row[
                            change_idx] is not None else 0

                        # Формируем данные в нужном формате
                        stock_info = {
                            'название': company_name,
                            'дата': current_date,
                            'цена': round(current_price, 2),
                            'валюта': 'RUB',
                            'тикер': ticker,
                            'изменение_процент': round(change_percent, 2)
                        }

                        stocks_data.append(stock_info)

                        # Вывод в консоль
                        if change_percent > 0:
                            print(f"✅ {company_name}: {round(current_price, 2)} ₽ (+{round(change_percent, 2)}%)")
                        elif change_percent < 0:
                            print(f"📉 {company_name}: {round(current_price, 2)} ₽ ({round(change_percent, 2)}%)")
                        else:
                            print(f"⏸️ {company_name}: {round(current_price, 2)} ₽ (0%)")
                    else:
                        print(f"❌ {company_name}: нет данных о цене")
                else:
                    print(f"❌ {company_name}: нет рыночных данных")
            else:
                print(f"❌ {company_name}: ошибка API {response.status_code}")

        except Exception as e:
            print(f"❌ {company_name}: ошибка {str(e)[:50]}")

        time.sleep(0.5)  # Задержка между запросами

    print("=" * 60)
    return stocks_data


def save_to_json(data, filename=None):
    """
    Сохраняет данные в JSON файл

    Args:
        data (list): Данные для сохранения
        filename (str): Имя файла (если None, генерируется автоматически)

    Returns:
        str: Путь к сохраненному файлу
    """
    if filename is None:
        filename = f"moex_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"💾 Данные сохранены в JSON: {filename}")
    return filename


def get_json_output():
    """
    Основная функция для получения данных в формате JSON

    Returns:
        str: JSON строка с данными
    """
    data = get_moex_data_direct()
    return json.dumps(data, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print("📊 СБОРЩИК ДАННЫХ МОСКОВСКОЙ БИРЖИ")
    print("=" * 40)

    # Получаем данные
    stocks_data = get_moex_data_direct()

    if stocks_data:
        # Сохраняем в JSON
        json_file = save_to_json(stocks_data)

        # Выводим JSON в консоль (первые 500 символов для краткости)
        json_output = json.dumps(stocks_data, ensure_ascii=False, indent=2)
        print("\n📄 JSON данные (первые 500 символов):")
        print(json_output[:500] + "..." if len(json_output) > 500 else json_output)

        # Сохраняем в CSV для удобства
        df = pd.DataFrame(stocks_data)
        csv_filename = f"moex_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        print(f"💾 Данные сохранены в CSV: {csv_filename}")

    else:
        print("❌ Данные не получены")