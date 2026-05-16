"""
S&C Tracker — Модуль управления базой данных
Пользователи, активы, курсы валют
"""
import sqlite3
from datetime import datetime

DB_NAME = 'portfolio.db'


def get_connection():
    """Создать подключение к БД"""
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Инициализация всех таблиц базы данных"""
    conn = get_connection()
    cur = conn.cursor()

    # Пользователи
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            login      TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Активы пользователя
    cur.execute('''
        CREATE TABLE IF NOT EXISTS assets (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL,
            asset_type     TEXT NOT NULL,
            asset_code     TEXT NOT NULL,
            asset_name     TEXT NOT NULL,
            quantity       REAL NOT NULL,
            purchase_price REAL NOT NULL,
            purchase_date  TEXT NOT NULL,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Курсы валют по дням (кэш от MOEX / ЦБ РФ)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS exchange_rates (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT UNIQUE NOT NULL,
            usd_rub    REAL,
            cny_rub    REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print('✅ База данных инициализирована')


# ─── Пользователи ─────────────────────────────────────────────────────────────

def get_or_create_user(login: str) -> int:
    """Найти пользователя или создать нового. Вернуть id."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT id FROM users WHERE login = ?', (login,))
    row = cur.fetchone()
    if row:
        user_id = row['id']
    else:
        cur.execute('INSERT INTO users (login) VALUES (?)', (login,))
        conn.commit()
        user_id = cur.lastrowid
    conn.close()
    return user_id


# ─── Активы ───────────────────────────────────────────────────────────────────

def get_user_assets(user_id: int) -> list:
    """Получить все активы пользователя"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT id, asset_type, asset_code, asset_name,
               quantity, purchase_price, purchase_date
        FROM assets
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (user_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_asset(user_id: int, asset_type: str, code: str, name: str,
              quantity: float, purchase_price: float, purchase_date: str) -> int:
    """Добавить актив. Вернуть id новой записи."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO assets
            (user_id, asset_type, asset_code, asset_name,
             quantity, purchase_price, purchase_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, asset_type, code, name, quantity, purchase_price, purchase_date))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def delete_asset(asset_id: int, user_id: int) -> bool:
    """Удалить актив пользователя"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM assets WHERE id = ? AND user_id = ?', (asset_id, user_id))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def partial_delete_group(ids: list, qty_to_delete: float, user_id: int) -> None:
    """
    Удалить часть позиции из группы.
    Удаляет целые записи начиная с самых новых; последнюю запись, если нужно,
    уменьшает до остатка — чтобы история покупок сохранилась.
    """
    conn = get_connection()
    cur = conn.cursor()
    placeholders = ','.join('?' for _ in ids)
    cur.execute(
        f'SELECT id, quantity FROM assets '
        f'WHERE id IN ({placeholders}) AND user_id = ? '
        f'ORDER BY created_at DESC',
        (*ids, user_id),
    )
    rows = cur.fetchall()
    remaining = qty_to_delete
    for row in rows:
        if remaining <= 1e-9:
            break
        if row['quantity'] <= remaining + 1e-9:
            cur.execute('DELETE FROM assets WHERE id = ? AND user_id = ?',
                        (row['id'], user_id))
            remaining -= row['quantity']
        else:
            cur.execute('UPDATE assets SET quantity = ? WHERE id = ? AND user_id = ?',
                        (round(row['quantity'] - remaining, 10), row['id'], user_id))
            remaining = 0
    conn.commit()
    conn.close()


# ─── Курсы валют ──────────────────────────────────────────────────────────────

def get_cached_rates(date_str: str) -> dict | None:
    """Получить курсы из кэша БД по дате (YYYY-MM-DD)"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT usd_rub, cny_rub FROM exchange_rates WHERE date = ?', (date_str,))
    row = cur.fetchone()
    conn.close()
    if row and row['usd_rub'] and row['cny_rub']:
        return {'usd_rub': row['usd_rub'], 'cny_rub': row['cny_rub']}
    return None


def save_rates(date_str: str, usd_rub: float, cny_rub: float):
    """Сохранить / обновить курсы в кэше БД"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO exchange_rates (date, usd_rub, cny_rub)
        VALUES (?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            usd_rub    = excluded.usd_rub,
            cny_rub    = excluded.cny_rub,
            updated_at = CURRENT_TIMESTAMP
    ''', (date_str, usd_rub, cny_rub))
    conn.commit()
    conn.close()
