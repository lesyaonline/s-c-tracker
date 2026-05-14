from pycoingecko import CoinGeckoAPI
from datetime import datetime

cg = CoinGeckoAPI()

coin_mapping = {
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

print("Доступные монеты: биткоин (btc), эфириум (eth), солана (sol), догикоин (doge), рипл (xrp)")
print("-" * 50)

coin_input = input("Введите название монеты (например, btc или эфириум): ").strip().lower()

if coin_input not in coin_mapping:
    print("Ошибка: монета не найдена. Проверьте написание.")
    exit()

coin_id = coin_mapping[coin_input]
print(f"Вы выбрали: {coin_input} (ID: {coin_id})")

date_input = input("Введите дату покупки в формате ДД-ММ-ГГГГ (например, 15-03-2025): ").strip()

try:
    datetime.strptime(date_input, "%d-%m-%Y")
except ValueError:
    print("Ошибка: дата должна быть в формате ДД-ММ-ГГГГ")
    exit()

try:
    buy_price = float(input("Введите цену покупки в USD (например, 50000): ").strip())
except ValueError:
    print("Ошибка: цена должна быть числом")
    exit()

print("\nЗагружаем данные... Пожалуйста, подождите.")

try:
    current_data = cg.get_price(ids=coin_id, vs_currencies='usd')
    current_price = current_data[coin_id]['usd']
    print(f"Текущая цена: ${current_price:,.2f}")
except Exception as e:
    print(f"Ошибка при получении текущей цены: {e}")
    exit()

try:
    history = cg.get_coin_history_by_id(id=coin_id, date=date_input)
    historical_price = history['market_data']['current_price']['usd']
    print(f"Цена на дату {date_input}: ${historical_price:,.2f}")
except Exception as e:
    print(f"Не удалось получить цену на {date_input}. Возможно, для этой монеты нет данных на эту дату.")
    print(f"Ошибка: {e}")
    exit()

difference = current_price - historical_price
percent_change = (difference / historical_price) * 100

print("\n" + "=" * 50)
print("РЕЗУЛЬТАТ:")
print(f"Монета: {coin_input.upper()}")
print(f"Цена покупки: ${historical_price:,.2f} (на {date_input})")
print(f"Текущая цена: ${current_price:,.2f}")
print("-" * 50)

if difference > 0:
    print(f"📈 ВЫ В ПЛЮСЕ на ${difference:,.2f} (+{percent_change:.2f}%)")
elif difference < 0:
    print(f"📉 ВЫ В МИНУСЕ на ${abs(difference):,.2f} ({percent_change:.2f}%)")
else:
    print("Цена не изменилась.")

print("=" * 50)
