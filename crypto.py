from pycoingecko import CoinGeckoAPI
from datetime import datetime
import sys

from flask import Flask, render_template, request, jsonify
import pandas as pd
from database_manager import StockDatabase

cg = CoinGeckoAPI()

COIN_MAPPING = {
    "биткоин": "bitcoin",
    "btc": "bitcoin",
    "эфириум": "ethereum",
    "eth": "ethereum",
    "солана": "solana",
    "sol": "solana",
    "догикоин": "dogecoin",
    "doge": "dogecoin",
    "рипл": "ripple",
    "xrp": "ripple"
}


def print_available_coins():
    """Выводит список доступных монет."""
    print("Доступные монеты: биткоин (btc), эфириум (eth), солана (sol), догикоин (doge), рипл (xrp)")
    print("-" * 50)


def get_coin_id():
    """Запрашивает у пользователя название монеты и возвращает её ID для API."""
    coin_input = input("Введите название монеты (например, btc или эфириум): ").strip().lower()
    if coin_input not in COIN_MAPPING:
        print("Ошибка: монета не найдена. Проверьте написание.")
        sys.exit(1)
    coin_id = COIN_MAPPING[coin_input]
    print(f"Вы выбрали: {coin_input} (ID: {coin_id})")
    return coin_input, coin_id


def get_date():
    """Запрашивает дату в формате ДД-ММ-ГГГГ и возвращает её после проверки."""
    date_input = input("Введите дату покупки в формате ДД-ММ-ГГГГ (например, 15-03-2025): ").strip()
    try:
        datetime.strptime(date_input, "%d-%m-%Y")
        return date_input
    except ValueError:
        print("Ошибка: дата должна быть в формате ДД-ММ-ГГГГ")
        sys.exit(1)


def get_buy_price():
    """Запрашивает цену покупки в USD и возвращает её как float."""
    try:
        buy_price = float(input("Введите цену покупки в USD (например, 50000): ").strip())
        return buy_price
    except ValueError:
        print("Ошибка: цена должна быть числом")
        sys.exit(1)


def fetch_current_price(coin_id):
    """Получает текущую цену монеты через API."""
    try:
        data = cg.get_price(ids=coin_id, vs_currencies='usd')
        return data[coin_id]['usd']
    except Exception as e:
        print(f"Ошибка при получении текущей цены: {e}")
        sys.exit(1)


def fetch_historical_price(coin_id, date_str):
    """Получает историческую цену монеты на заданную дату."""
    try:
        history = cg.get_coin_history_by_id(id=coin_id, date=date_str)
        return history['market_data']['current_price']['usd']
    except Exception as e:
        print(f"Не удалось получить цену на {date_str}. Возможно, для этой монеты нет данных на эту дату.")
        print(f"Ошибка: {e}")
        sys.exit(1)


def calculate_profit_loss(current, historical, price):
    """Вычисляет разницу и процентное изменение."""
    diff = price / historical * current - price
    percent = (diff / price) * 100
    return diff, percent


def display_result(coin_name, historical_price, current_price, diff, percent, date_str):
    """Форматированный вывод результата."""
    print("\n" + "=" * 50)
    print("РЕЗУЛЬТАТ:")
    print(f"Монета: {coin_name.upper()}")
    print(f"Цена покупки: ${historical_price:,.2f} (на {date_str})")
    print(f"Текущая цена: ${current_price:,.2f}")
    print("-" * 50)
    if diff > 0:
        print(f"📈 ВЫ В ПЛЮСЕ на ${diff:,.2f} (+{percent:.2f}%)")
    elif diff < 0:
        print(f"📉 ВЫ В МИНУСЕ на ${abs(diff):,.2f} ({percent:.2f}%)")
    else:
        print("Цена не изменилась.")
    print("=" * 50)


def crypto():
    """Главная функция, объединяющая все этапы."""
    print_available_coins()

    coin_input, coin_id = get_coin_id()
    date_str = get_date()
    price = get_buy_price()  # цену покупки мы спрашиваем, но далее не используем? По коду она не применяется, оставим запрос как в оригинале

    print("\nЗагружаем данные... Пожалуйста, подождите.")

    current_price = fetch_current_price(coin_id)
    historical_price = fetch_historical_price(coin_id, date_str)

    print(f"Текущая цена: ${current_price:,.2f}")
    print(f"Цена на дату {date_str}: ${historical_price:,.2f}")

    diff, percent = calculate_profit_loss(current_price, historical_price, price)
    display_result(coin_input, historical_price, current_price, diff, percent, date_str) 

if __name__ == '__main__': 
    crypto()