"""
Модуль для управления базой данных акций
Версия для автоматического обновления через планировщик задач
"""

import sqlite3
import json
from datetime import datetime
import os
from moex_stocks import get_moex_data_direct


class StockDatabase:
    """
    Класс для управления базой данных акций
    """

    def __init__(self, db_name="stocks.db"):
        """
        Инициализация подключения к базе данных
        """
        self.db_name = db_name
        self.connection = None
        self.cursor = None
        self._connect()
        self._create_table()

    def _connect(self):
        """Устанавливает соединение с базой данных"""
        # ВАЖНО: check_same_thread=False для работы с планировщиком
        self.connection = sqlite3.connect(self.db_name, check_same_thread=False)
        self.cursor = self.connection.cursor()
        print(f"✅ Подключение к базе данных: {self.db_name}")

    def _create_table(self):
        """
        Создает таблицу stocks, если она не существует
        """
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            название TEXT NOT NULL,
            дата TEXT NOT NULL,
            цена REAL NOT NULL,
            валюта TEXT NOT NULL,
            тикер TEXT,
            изменение_процент REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        self.cursor.execute(create_table_sql)
        self.connection.commit()
        print("✅ Таблица 'stocks' создана/проверена")

    def insert_stock_data(self, stock_info):
        """
        Вставляет данные об акции в базу данных
        """
        insert_sql = """
        INSERT INTO stocks (название, дата, цена, валюта, тикер, изменение_процент)
        VALUES (?, ?, ?, ?, ?, ?)
        """

        self.cursor.execute(insert_sql, (
            stock_info.get('название'),
            stock_info.get('дата'),
            stock_info.get('цена'),
            stock_info.get('валюта'),
            stock_info.get('тикер'),
            stock_info.get('изменение_процент')
        ))

        self.connection.commit()
        return self.cursor.lastrowid

    def update_all_data(self, stocks_data):
        """
        Обновляет базу данных новыми данными
        """
        if not stocks_data:
            print("⚠️ Нет данных для обновления")
            return 0

        count = 0
        for stock in stocks_data:
            self.insert_stock_data(stock)
            count += 1

        print(f"✅ Добавлено {count} записей в базу данных")
        return count

    def get_price_by_date(self, company_name, date):
        """
        Получает цену акции на определенную дату
        """
        self.cursor.execute("""
            SELECT цена FROM stocks 
            WHERE название = ? AND дата = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (company_name, date))

        row = self.cursor.fetchone()
        if row:
            return row[0]
        return None

    def get_current_price(self, company_name):
        """
        Получает последнюю доступную цену акции
        """
        self.cursor.execute("""
            SELECT цена FROM stocks 
            WHERE название = ? 
            ORDER BY дата DESC, created_at DESC
            LIMIT 1
        """, (company_name,))

        row = self.cursor.fetchone()
        if row:
            return row[0]
        return None

    def get_all_data(self):
        """
        Получает все данные из таблицы stocks
        """
        self.cursor.execute("SELECT * FROM stocks ORDER BY дата DESC, название")
        rows = self.cursor.fetchall()
        columns = [description[0] for description in self.cursor.description]

        result = []
        for row in rows:
            result.append(dict(zip(columns, row)))
        return result

    def get_latest_by_company(self, company_name):
        """
        Получает последние данные по конкретной компании
        """
        self.cursor.execute("""
            SELECT * FROM stocks 
            WHERE название = ? 
            ORDER BY дата DESC, created_at DESC
            LIMIT 1
        """, (company_name,))

        row = self.cursor.fetchone()
        if row:
            columns = [description[0] for description in self.cursor.description]
            return dict(zip(columns, row))
        return None

    def get_statistics(self):
        """
        Получает статистику по данным
        """
        self.cursor.execute("""
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT название) as total_companies,
                MIN(дата) as first_date,
                MAX(дата) as last_date
            FROM stocks
        """)

        row = self.cursor.fetchone()
        return {
            'total_records': row[0],
            'total_companies': row[1],
            'first_date': row[2],
            'last_date': row[3]
        }

    def get_available_dates(self, company_name):
        """
        Получает список доступных дат для компании
        """
        self.cursor.execute("""
            SELECT DISTINCT дата FROM stocks 
            WHERE название = ?
            ORDER BY дата DESC
        """, (company_name,))

        return [row[0] for row in self.cursor.fetchall()]

    def get_all_companies(self):
        """
        Получает список всех компаний
        """
        self.cursor.execute("SELECT DISTINCT название FROM stocks ORDER BY название")
        return [row[0] for row in self.cursor.fetchall()]

    def get_latest_prices(self):
        """
        Получает последние цены для всех компаний
        """
        self.cursor.execute("""
            SELECT название, MAX(дата) as last_date
            FROM stocks
            GROUP BY название
        """)
        latest_dates = self.cursor.fetchall()

        result = []
        for company, last_date in latest_dates:
            self.cursor.execute("""
                SELECT цена, изменение_процент, валюта FROM stocks 
                WHERE название = ? AND дата = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (company, last_date))

            row = self.cursor.fetchone()
            if row:
                result.append({
                    'название': company,
                    'цена': row[0],
                    'изменение_процент': row[1] if row[1] else 0,
                    'валюта': row[2] if row[2] else 'RUB'
                })

        return result

    def export_to_json(self, filename=None):
        """
        Экспортирует данные из базы в JSON файл
        """
        if filename is None:
            filename = f"db_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        data = self.get_all_data()

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        print(f"💾 Данные экспортированы в JSON: {filename}")
        return filename

    def close(self):
        """Закрывает соединение с базой данных"""
        if self.connection:
            self.connection.close()
            print("🔒 Соединение с базой данных закрыто")


def main():
    """
    Основная функция: собирает данные и обновляет базу данных
    (без интерактивного ввода, для работы с планировщиком)
    """
    print("=" * 60)
    print("📈 СИСТЕМА СБОРА И ХРАНЕНИЯ ДАННЫХ ОБ АКЦИЯХ")
    print(f"🕒 Время запуска: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print("=" * 60)

    # Создаем объект базы данных
    db = StockDatabase("stocks.db")

    # Получаем актуальные данные с биржи
    print("\n🔍 Сбор актуальных данных...")
    stocks_data = get_moex_data_direct()

    if stocks_data:
        # Обновляем базу данных
        print("\n💾 Обновление базы данных...")
        count = db.update_all_data(stocks_data)

        # Показываем статистику
        stats = db.get_statistics()
        print("\n📊 Статистика базы данных:")
        print(f"   Всего записей: {stats['total_records']}")
        print(f"   Уникальных компаний: {stats['total_companies']}")
        print(f"   Период данных: {stats['first_date']} - {stats['last_date']}")

        # Показываем последние данные (первые 3 компании для краткости)
        print("\n📋 Последние данные по компаниям:")
        companies = ['Сбербанк', 'Газпром', 'Лукойл']
        for company in companies:
            latest = db.get_latest_by_company(company)
            if latest:
                print(f"   {company}: {latest['цена']} {latest['валюта']} ({latest['дата']})")

        # Автоматический экспорт в JSON (опционально, можно закомментировать)
        # db.export_to_json(f"db_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

    else:
        print("❌ Данные не получены. База данных не обновлена.")

    # Закрываем соединение
    db.close()

    print("\n✅ Работа завершена")
    print("=" * 60)


if __name__ == "__main__":
    main()