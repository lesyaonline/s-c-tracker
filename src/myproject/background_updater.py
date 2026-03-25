"""
Фоновый скрипт для автоматического обновления базы данных
Запускается один раз и работает постоянно
"""

import time
import logging
from datetime import datetime
from moex_stocks import get_moex_data_direct
from database_manager import StockDatabase

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('updater.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)


class BackgroundUpdater:
    def __init__(self, interval_seconds=3600):
        """
        Args:
            interval_seconds: интервал обновления в секундах (по умолчанию 3600 = 1 час)
        """
        self.interval = interval_seconds
        self.running = True
        self.db = StockDatabase("stocks.db")

    def is_trading_time(self):
        """
        Проверяет, идет ли сейчас торговая сессия
        """
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        weekday = now.weekday()

        # Выходные
        if weekday >= 5:
            return False

        # Рабочее время: 10:00 - 18:45 МСК
        if hour < 10 or (hour == 18 and minute > 45) or hour >= 19:
            return False

        # Технический перерыв 14:00-14:30
        if hour == 14 and minute < 30:
            return False

        return True

    def update_once(self):
        """Однократное обновление данных"""
        logging.info("Начало обновления данных...")

        try:
            stocks_data = get_moex_data_direct()

            if stocks_data:
                count = self.db.update_all_data(stocks_data)
                logging.info(f"✅ Добавлено {count} записей в базу")
                return True
            else:
                logging.warning("⚠️ Данные не получены")
                return False

        except Exception as e:
            logging.error(f"❌ Ошибка при обновлении: {e}")
            return False

    def run(self):
        """Запуск цикла обновлений"""
        logging.info(f"🚀 Запуск фонового обновления (интервал: {self.interval // 60} минут)")
        logging.info("Нажмите Ctrl+C для остановки")

        # Сразу выполняем первое обновление
        self.update_once()

        try:
            while self.running:
                # Ждем следующий интервал
                for _ in range(self.interval):
                    if not self.running:
                        break
                    time.sleep(1)

                # Проверяем, нужно ли обновлять (только в рабочее время)
                if self.is_trading_time():
                    self.update_once()
                else:
                    logging.info("Биржа закрыта, обновление пропущено")

        except KeyboardInterrupt:
            logging.info("🛑 Получен сигнал остановки")
        finally:
            self.stop()

    def stop(self):
        """Остановка обновлений"""
        self.running = False
        if self.db:
            self.db.close()
        logging.info("✅ Работа завершена")


if __name__ == "__main__":
    # Интервал 1 час = 3600 секунд
    # Можно изменить, например, 1800 = 30 минут
    updater = BackgroundUpdater(interval_seconds=3600)
    updater.run()