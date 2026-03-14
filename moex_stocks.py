import requests
import pandas as pd
from datetime import datetime
import time


def get_moex_data_direct():
    """
    Получение данных напрямую с API Московской биржи (ISS MOEX)
    Документация: https://iss.moex.com/iss/reference/
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

    print(f"\n📊 Загрузка данных с Московской биржи ({datetime.now().strftime('%H:%M:%S')})")
    print("=" * 60)

    for ticker, company_name in companies.items():
        try:
            # API Московской биржи (ISS)
            url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json"

            # Добавляем заголовки для имитации браузера
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
                    # Создаем словарь для удобства
                    row = market_data[0]
                    cols = market_cols

                    # Индексы основных полей
                    # LAST - последняя цена
                    # LASTCHANGE - изменение в пунктах
                    # LASTCHANGEPRCNT - изменение в процентах
                    # VOLUME - объем

                    price_idx = cols.index('LAST') if 'LAST' in cols else -1
                    change_idx = cols.index('LASTCHANGEPRCNT') if 'LASTCHANGEPRCNT' in cols else -1
                    volume_idx = cols.index('VOLUME') if 'VOLUME' in cols else -1

                    if price_idx >= 0 and row[price_idx] is not None:
                        current_price = float(row[price_idx])
                        change_percent = float(row[change_idx]) if change_idx >= 0 and row[
                            change_idx] is not None else 0
                        volume = int(row[volume_idx]) if volume_idx >= 0 and row[volume_idx] is not None else 0

                        stocks_data.append({
                            'Тикер': ticker,
                            'Компания': company_name,
                            'Цена (RUB)': round(current_price, 2),
                            'Изм. %': round(change_percent, 2),
                            'Объем': f"{volume:,}" if volume > 0 else "0"
                        })

                        # Цветной вывод в зависимости от изменения
                        if change_percent > 0:
                            print(f"✅ {company_name}: {round(current_price, 2)} ₽ (+{round(change_percent, 2)}%)")
                        elif change_percent < 0:
                            print(f"📉 {company_name}: {round(current_price, 2)} ₽ ({round(change_percent, 2)}%)")
                        else:
                            print(f"⏸️ {company_name}: {round(current_price, 2)} ₽ (0%)")
                    else:
                        print(f"❌ {company_name}: нет данных о цене (возможно, нет торгов)")
                else:
                    print(f"❌ {company_name}: нет рыночных данных")
            else:
                print(f"❌ {company_name}: ошибка API {response.status_code}")

        except requests.exceptions.Timeout:
            print(f"❌ {company_name}: таймаут соединения")
        except requests.exceptions.ConnectionError:
            print(f"❌ {company_name}: ошибка соединения")
        except Exception as e:
            print(f"❌ {company_name}: ошибка {str(e)[:50]}")

        # Небольшая задержка между запросами
        time.sleep(0.5)

    print("=" * 60)
    return pd.DataFrame(stocks_data)


def display_moex_table():
    """Отображает таблицу с данными"""
    df = get_moex_data_direct()

    print("\n" + "=" * 80)
    print(f"📈 ДАННЫЕ ПО АКЦИЯМ МОСКОВСКОЙ БИРЖИ (ГОЛУБЫЕ ФИШКИ)")
    print(f"🕒 Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print("=" * 80)

    if df.empty:
        print("\n❌ Данные не получены")
        print("\nВозможные причины:")
        print("  • Биржа закрыта (торги с 10:00 до 18:45 МСК)")
        print("  • Сегодня выходной день")
        print("  • Технический перерыв (с 14:00 до 14:30 МСК)")
        print("  • Проблемы с интернет-соединением")
        print("\n💡 Совет: Запустите скрипт в рабочее время биржи")
    else:
        # Настройки отображения
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.max_colwidth', 25)

        print("\n" + df.to_string(index=False))

        # Статистика
        print("\n" + "-" * 80)
        print(f"✅ Компаний с данными: {len(df)}")

        if 'Изм. %' in df.columns:
            df_numeric = df[pd.to_numeric(df['Изм. %'], errors='coerce').notna()]
            if not df_numeric.empty:
                df_numeric['Изм. %'] = pd.to_numeric(df_numeric['Изм. %'])

                avg_change = df_numeric['Изм. %'].mean()
                max_growth = df_numeric.loc[df_numeric['Изм. %'].idxmax()]
                max_fall = df_numeric.loc[df_numeric['Изм. %'].idxmin()]

                print(f"📊 Среднее изменение: {avg_change:.2f}%")
                print(f"📈 Максимальный рост: {max_growth['Компания']} ({max_growth['Изм. %']}%)")
                print(f"📉 Максимальное падение: {max_fall['Компания']} ({max_fall['Изм. %']}%)")

    return df


def monitor_moex(interval=60):
    """
    Непрерывный мониторинг с заданным интервалом
    """
    print(f"\n🔄 Запуск мониторинга (обновление каждые {interval} сек.)")
    print("Нажмите Ctrl+C для остановки\n")

    try:
        while True:
            print(f"\n{'=' * 60}")
            print(f"🕒 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
            print(f"{'=' * 60}")

            df = get_moex_data_direct()

            if not df.empty:
                print("\n📋 Краткая сводка:")
                display_df = df[['Компания', 'Цена (RUB)', 'Изм. %']].copy()
                print(display_df.to_string(index=False))
            else:
                print("⚠️ Данные временно недоступны")

            print(f"\n⏱️ Следующее обновление через {interval} сек.")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n🛑 Мониторинг остановлен")


if __name__ == "__main__":
    print("📊 СБОРЩИК ДАННЫХ МОСКОВСКОЙ БИРЖИ")
    print("=" * 40)

    # Проверяем рабочее время биржи
    current_time = datetime.now()
    current_hour = current_time.hour
    current_minute = current_time.minute
    current_weekday = current_time.weekday()  # 0-4 понедельник-пятница

    is_weekend = current_weekday >= 5
    is_working_hours = (10 <= current_hour < 18) or (current_hour == 18 and current_minute <= 45)
    is_break_time = (14 <= current_hour < 14) or (current_hour == 14 and current_minute < 30)

    if is_weekend:
        print("\n⚠️ Сегодня выходной. Биржа закрыта.")
    elif not is_working_hours:
        print("\n⚠️ Биржа закрыта. Рабочее время: 10:00 - 18:45 МСК")
    elif is_break_time:
        print("\n⚠️ Технический перерыв (14:00 - 14:30)")

    # Получаем и отображаем данные
    df = display_moex_table()

    if not df.empty:
        # Сохранение в CSV
        save_option = input("\n💾 Сохранить данные в CSV? (y/n): ").lower()
        if save_option == 'y':
            filename = f"moex_blue_chips_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"✅ Данные сохранены в файл: {filename}")

        # Мониторинг
        monitor_option = input("\n🔄 Запустить непрерывный мониторинг? (y/n): ").lower()
        if monitor_option == 'y':
            try:
                interval = int(input("⏱️ Интервал обновления в секундах (по умолчанию 60): ") or 60)
            except ValueError:
                interval = 60
            monitor_moex(interval)