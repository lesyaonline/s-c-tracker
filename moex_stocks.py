from moexalgo import Ticker
import pandas as pd
from datetime import datetime


def get_moex_blue_chips_data():
    """
    Получает данные по голубым фишкам Московской биржи через moexalgo
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

    print(f"Загрузка данных для {len(companies)} компаний...")

    for ticker, company_name in companies.items():
        try:
            # Создаем объект тикера
            t = Ticker(ticker)

            # Получаем текущие рыночные данные
            market_data = t.marketdata()  # ← ВАЖНО: вызываем как функцию!

            # Получаем последние свечи для расчета изменения
            candles = t.candles(period='D', limit=2)  # Последние 2 дня

            if market_data is not None and candles is not None:
                # Преобразуем в DataFrame для удобства
                if hasattr(market_data, 'to_dict'):
                    md_dict = market_data.to_dict()

                    # Извлекаем цену (обычно в поле 'last' или 'price')
                    current_price = md_dict.get('last', 0)

                    # Рассчитываем изменение за 24ч из свечей
                    if len(candles) >= 2:
                        df_candles = pd.DataFrame(candles)
                        prev_close = df_candles['close'].iloc[-2]
                        change_percent = ((current_price - prev_close) / prev_close) * 100
                    else:
                        change_percent = 0

                    stocks_data.append({
                        'Тикер': ticker,
                        'Компания': company_name,
                        'Цена (RUB)': round(float(current_price), 2),
                        'Изм. за 24ч (%)': round(float(change_percent), 2)
                    })

                    print(f"✓ {company_name}: {round(float(current_price), 2)} ₽")
                else:
                    print(f"✗ {company_name}: данные в неожиданном формате")
            else:
                print(f"✗ {company_name}: нет данных")

        except Exception as e:
            print(f"✗ Ошибка для {company_name}: {e}")

    return pd.DataFrame(stocks_data)


def display_moex_table():
    """Отображает таблицу с данными"""
    df = get_moex_blue_chips_data()

    print("\n" + "=" * 70)
    print(f"ДАННЫЕ ПО АКЦИЯМ МОСКОВСКОЙ БИРЖИ")
    print(f"Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print("=" * 70)

    if df.empty:
        print("\n❌ Данные не получены")
        print("   Возможные причины:")
        print("   • Биржа закрыта (торги с 10:00 до 18:45 МСК)")
        print("   • Нет соединения с API Московской биржи")
    else:
        print("\n" + df.to_string(index=False))

        # Статистика
        print("\n" + "-" * 70)
        print(f"Всего компаний: {len(df)}")

        if 'Изм. за 24ч (%)' in df.columns:
            avg_change = df['Изм. за 24ч (%)'].mean()
            print(f"Среднее изменение: {avg_change:.2f}%")

    return df


if __name__ == "__main__":
    df = display_moex_table()