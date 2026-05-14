"""
S&C Tracker — Модуль получения рыночных данных
MOEX ISS API (акции) + CoinGecko API (крипта) + курсы валют
"""
import requests
from datetime import datetime, timedelta
from database import get_cached_rates, save_rates

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


# ═══════════════════════════════════════════════════════════════
#  КУРСЫ ВАЛЮТ
# ═══════════════════════════════════════════════════════════════

def fetch_usd_rub() -> float:
    """Курс USD/RUB через MOEX валютный рынок"""
    try:
        url = ('https://iss.moex.com/iss/engines/currency/markets/selt'
               '/boards/CETS/securities/USD000UTSTOM.json')
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            d = r.json()
            mdata = d.get('marketdata', {}).get('data', [])
            mcols = d.get('marketdata', {}).get('columns', [])
            if mdata and mcols:
                idx = mcols.index('LAST') if 'LAST' in mcols else -1
                if idx >= 0 and mdata[0][idx]:
                    return float(mdata[0][idx])
    except Exception as e:
        print(f'USD/RUB fetch error: {e}')
    return 90.0  # запасное значение


def fetch_cny_rub() -> float:
    """Курс CNY/RUB через ЦБ РФ"""
    try:
        r = requests.get('https://www.cbr-xml-daily.ru/daily_json.js', timeout=8)
        if r.status_code == 200:
            cny = r.json().get('Valute', {}).get('CNY', {})
            if cny:
                return float(cny['Value']) / float(cny.get('Nominal', 1))
    except Exception as e:
        print(f'CNY/RUB fetch error: {e}')
    return 12.5  # запасное значение


def get_rates() -> dict:
    """
    Получить актуальные курсы валют.
    Сначала смотрит в кэш БД (по сегодняшней дате),
    при отсутствии — запрашивает и сохраняет.
    Возвращает: {'usd_rub': float, 'cny_rub': float}
    """
    today = datetime.now().strftime('%Y-%m-%d')
    cached = get_cached_rates(today)
    if cached:
        return cached

    usd_rub = fetch_usd_rub()
    cny_rub = fetch_cny_rub()
    save_rates(today, usd_rub, cny_rub)
    return {'usd_rub': usd_rub, 'cny_rub': cny_rub}


def convert_usd(amount_usd: float, currency: str, rates: dict) -> float:
    """Конвертировать сумму из USD в выбранную валюту"""
    if currency == 'rub':
        return amount_usd * rates['usd_rub']
    if currency == 'cny':
        # 1 USD → RUB / (CNY → RUB) = CNY
        return amount_usd * rates['usd_rub'] / rates['cny_rub']
    return amount_usd  # usd по умолчанию


CURRENCY_SYMBOLS = {'usd': '$', 'rub': '₽', 'cny': '¥'}


def currency_symbol(currency: str) -> str:
    return CURRENCY_SYMBOLS.get(currency, '$')


# ═══════════════════════════════════════════════════════════════
#  АКЦИИ MOEX
# ═══════════════════════════════════════════════════════════════

def get_moex_price(ticker: str) -> float | None:
    """Текущая цена акции с MOEX ISS (в рублях)"""
    try:
        url = (f'https://iss.moex.com/iss/engines/stock/markets/shares'
               f'/boards/TQBR/securities/{ticker}.json')
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            d = r.json()
            mdata = d.get('marketdata', {}).get('data', [])
            mcols = d.get('marketdata', {}).get('columns', [])
            if mdata and mcols:
                row = mdata[0]
                idx = mcols.index('LAST') if 'LAST' in mcols else -1
                if idx >= 0 and row[idx] is not None:
                    return float(row[idx])
    except Exception as e:
        print(f'MOEX price error {ticker}: {e}')
    return None


def get_moex_history(ticker: str, days: int = 30) -> dict:
    """
    Исторические цены закрытия с MOEX ISS (в рублях).
    Возвращает {YYYY-MM-DD: float}
    """
    try:
        end   = datetime.now()
        start = end - timedelta(days=days + 14)
        url = (f'https://iss.moex.com/iss/engines/stock/markets/shares'
               f'/boards/TQBR/securities/{ticker}/history.json'
               f'?from={start.strftime("%Y-%m-%d")}&till={end.strftime("%Y-%m-%d")}&limit=200')
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            d    = r.json()
            rows = d.get('history', {}).get('data', [])
            cols = d.get('history', {}).get('columns', [])
            if rows and cols:
                ci = cols.index('CLOSE')     if 'CLOSE'     in cols else -1
                di = cols.index('TRADEDATE') if 'TRADEDATE' in cols else -1
                return {
                    row[di]: float(row[ci])
                    for row in rows
                    if di >= 0 and ci >= 0 and row[di] and row[ci] is not None
                }
    except Exception as e:
        print(f'MOEX history error {ticker}: {e}')
    return {}


# ═══════════════════════════════════════════════════════════════
#  КРИПТОВАЛЮТЫ (CoinGecko)
# ═══════════════════════════════════════════════════════════════

def get_crypto_price(coin_id: str) -> float | None:
    """Текущая цена криптовалюты в USD (CoinGecko)"""
    try:
        r = requests.get(
            f'https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd',
            timeout=10)
        if r.status_code == 200:
            return r.json().get(coin_id, {}).get('usd')
    except Exception as e:
        print(f'Crypto price error {coin_id}: {e}')
    return None


def get_crypto_history(coin_id: str, days: int = 30) -> dict:
    """
    Исторические цены крипты за период (CoinGecko market_chart).
    Возвращает {YYYY-MM-DD: float}
    """
    try:
        r = requests.get(
            f'https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart'
            f'?vs_currency=usd&days={days}&interval=daily',
            timeout=10)
        if r.status_code == 200:
            result = {}
            for ts_ms, price in r.json().get('prices', []):
                date_str = datetime.fromtimestamp(ts_ms / 1000).strftime('%Y-%m-%d')
                result[date_str] = price
            return result
    except Exception as e:
        print(f'Crypto history error {coin_id}: {e}')
    return {}


# ═══════════════════════════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНЫЕ
# ═══════════════════════════════════════════════════════════════

def nearest_price(history: dict, target_iso: str) -> float | None:
    """
    Найти ближайшую цену не позже target_iso из словаря {YYYY-MM-DD: price}.
    Используется как фолбек когда для конкретного дня нет данных.
    """
    if not history:
        return None
    prev = None
    for d in sorted(history.keys()):
        if d <= target_iso:
            prev = d
        else:
            break
    return history[prev] if prev else None
