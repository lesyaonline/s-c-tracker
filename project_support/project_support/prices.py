"""
S&C Tracker — Модуль получения рыночных данных
MOEX ISS API (акции) + CoinGecko API (крипта) + курсы валют
"""
import requests
from concurrent.futures import ThreadPoolExecutor
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
    return 90.0


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
    return 12.5


def get_rates() -> dict:
    """
    Получить актуальные курсы валют.
    Кэшируются в БД по дате — один запрос в сутки.
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
    """Конвертировать сумму из USD в выбранную валюту отображения"""
    if currency == 'rub':
        return amount_usd * rates['usd_rub']
    if currency == 'cny':
        return amount_usd * rates['usd_rub'] / rates['cny_rub']
    return amount_usd


def to_usd(amount: float, from_currency: str, rates: dict) -> float:
    """Конвертировать сумму из произвольной валюты в USD для хранения"""
    if from_currency == 'rub':
        return amount / rates['usd_rub']
    if from_currency == 'cny':
        return amount * rates['cny_rub'] / rates['usd_rub']
    return amount  # уже USD


CURRENCY_SYMBOLS = {'usd': '$', 'rub': '₽', 'cny': '¥'}


def currency_symbol(currency: str) -> str:
    return CURRENCY_SYMBOLS.get(currency, '$')


# ═══════════════════════════════════════════════════════════════
#  АКЦИИ MOEX
# ═══════════════════════════════════════════════════════════════

def get_moex_prices_batch(tickers: list) -> dict:
    """
    Текущие цены нескольких акций MOEX одним запросом.
    Возвращает {ticker: float|None} в рублях.
    MOEX ISS поддерживает фильтр ?securities=SBER,GAZP,...
    """
    if not tickers:
        return {}
    try:
        securities_param = ','.join(tickers)
        url = (
            'https://iss.moex.com/iss/engines/stock/markets/shares'
            f'/boards/TQBR/securities.json'
            f'?securities={securities_param}&iss.meta=off'
        )
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200:
            d     = r.json()
            mdata = d.get('marketdata', {}).get('data', [])
            mcols = d.get('marketdata', {}).get('columns', [])
            sdata = d.get('securities', {}).get('data', [])
            scols = d.get('securities', {}).get('columns', [])
            result = {}
            if mdata and mcols:
                si = mcols.index('SECID') if 'SECID' in mcols else -1
                li = mcols.index('LAST')  if 'LAST'  in mcols else -1
                for row in mdata:
                    if si >= 0 and li >= 0 and row[si] and row[li] is not None:
                        result[row[si]] = float(row[li])
            # Для тикеров без LAST берём PREVPRICE из таблицы securities
            if sdata and scols:
                sec_si = scols.index('SECID')     if 'SECID'     in scols else -1
                sec_pi = scols.index('PREVPRICE') if 'PREVPRICE' in scols else -1
                if sec_si >= 0 and sec_pi >= 0:
                    for row in sdata:
                        tid = row[sec_si]
                        if tid not in result and row[sec_pi] is not None:
                            result[tid] = float(row[sec_pi])
            return result
        print(f'MOEX batch status {r.status_code}')
    except Exception as e:
        print(f'MOEX batch price error: {e}')
    return {t: None for t in tickers}


def get_moex_price(ticker: str):
    """Текущая цена одной акции MOEX. Обёртка над батч-функцией."""
    return get_moex_prices_batch([ticker]).get(ticker)


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

def get_crypto_price(coin_id: str):
    """Текущая цена криптовалюты в USD (CoinGecko). Возвращает float или None."""
    result = get_crypto_prices_batch([coin_id])
    return result.get(coin_id)


def get_crypto_prices_batch(coin_ids: list) -> dict:
    """
    Текущие цены нескольких криптовалют одним запросом к CoinGecko.
    Возвращает {coin_id: float|None}.
    CoinGecko поддерживает до ~50 монет в одном запросе — гораздо надёжнее
    параллельных одиночных запросов, которые легко получают 429.
    """
    if not coin_ids:
        return {}
    try:
        ids_str = ','.join(coin_ids)
        r = requests.get(
            f'https://api.coingecko.com/api/v3/simple/price'
            f'?ids={ids_str}&vs_currencies=usd',
            headers=HEADERS, timeout=12)
        if r.status_code == 200:
            data = r.json()
            return {cid: data.get(cid, {}).get('usd') for cid in coin_ids}
        print(f'CoinGecko batch status {r.status_code}')
    except Exception as e:
        print(f'Crypto batch price error: {e}')
    return {cid: None for cid in coin_ids}


def get_crypto_history(coin_id: str, days: int = 30) -> dict:
    """
    Исторические цены крипты за период (CoinGecko market_chart, интервал — день).
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

def nearest_price(history: dict, target_iso: str):
    """
    Ближайшая цена не позже target_iso из {YYYY-MM-DD: price}.
    Используется как фолбек когда нет данных на конкретный день.
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
