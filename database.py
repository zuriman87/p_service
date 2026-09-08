"""Warstwa danych: obsługa PostgreSQL (Supabase) oraz SQLite (lokalnie)."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
    cache_data = st.cache_data
except ImportError:
    STREAMLIT_AVAILABLE = False
    def cache_data(ttl=None):
        def decorator(func):
            return func
        return decorator

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

DB_PATH = Path(__file__).resolve().parent / "scrap_accounting.db"


class AppError(Exception):
    """Błąd logiki biznesowej pokazywany użytkownikowi."""


def _round_money(value: Any) -> float:
    return round(float(value), 2)


def _round_qty(value: Any) -> float:
    return round(float(value), 3)


# --- Функция для мгновенного сброса кэша при изменениях ---
def clear_app_cache():
    if STREAMLIT_AVAILABLE:
        st.cache_data.clear()


def get_database_url() -> str | None:
    if STREAMLIT_AVAILABLE:
        try:
            if "DATABASE_URL" in st.secrets:
                return str(st.secrets["DATABASE_URL"])
        except Exception:
            pass
    return os.environ.get("DATABASE_URL")


class DBConnection:
    def __init__(self, raw_conn: Any, is_pg: bool = False) -> None:
        self.raw_conn = raw_conn
        self.is_pg = is_pg

    def execute(self, sql: str, params: tuple | list = ()) -> Any:
        if self.is_pg:
            pg_sql = sql.replace("?", "%s")
            cur = self.raw_conn.cursor()
            cur.execute(pg_sql, params)
            return cur
        else:
            return self.raw_conn.execute(sql, params)

    def executescript(self, script: str) -> None:
        if self.is_pg:
            cur = self.raw_conn.cursor()
            cur.execute(script)
        else:
            self.raw_conn.executescript(script)


@contextmanager
def get_conn() -> Iterator[DBConnection]:
    db_url = get_database_url()
    if db_url and PSYCOPG2_AVAILABLE:
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        try:
            yield DBConnection(conn, is_pg=True)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield DBConnection(conn, is_pg=False)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def init_db() -> None:
    with get_conn() as conn:
        if conn.is_pg:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    sku TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    purchase_price NUMERIC(12, 2) NOT NULL CHECK (purchase_price >= 0),
                    sale_price NUMERIC(12, 2) NOT NULL CHECK (sale_price >= 0)
                );
                CREATE TABLE IF NOT EXISTS counterparties (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT,
                    inn TEXT,
                    address TEXT
                );
                CREATE TABLE IF NOT EXISTS warehouses (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT
                );
                CREATE TABLE IF NOT EXISTS stock (
                    warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
                    product_id INTEGER NOT NULL REFERENCES products(id),
                    quantity NUMERIC(12, 3) NOT NULL DEFAULT 0,
                    PRIMARY KEY (warehouse_id, product_id)
                );
                CREATE TABLE IF NOT EXISTS cashbox (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    balance NUMERIC(14, 2) NOT NULL DEFAULT 0
                );
                INSERT INTO cashbox (id, balance) VALUES (1, 0) ON CONFLICT (id) DO NOTHING;
                CREATE TABLE IF NOT EXISTS purchases (
                    id SERIAL PRIMARY KEY,
                    number TEXT NOT NULL UNIQUE,
                    doc_date DATE NOT NULL,
                    counterparty_id INTEGER NOT NULL REFERENCES counterparties(id),
                    warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
                    total NUMERIC(14, 2) NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS purchase_lines (
                    id SERIAL PRIMARY KEY,
                    purchase_id INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
                    product_id INTEGER NOT NULL REFERENCES products(id),
                    quantity NUMERIC(12, 3) NOT NULL CHECK (quantity > 0),
                    price NUMERIC(12, 2) NOT NULL CHECK (price >= 0),
                    amount NUMERIC(14, 2) NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sales (
                    id SERIAL PRIMARY KEY,
                    number TEXT NOT NULL UNIQUE,
                    doc_date DATE NOT NULL,
                    counterparty_id INTEGER NOT NULL REFERENCES counterparties(id),
                    warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
                    total NUMERIC(14, 2) NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS sale_lines (
                    id SERIAL PRIMARY KEY,
                    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
                    product_id INTEGER NOT NULL REFERENCES products(id),
                    quantity NUMERIC(12, 3) NOT NULL CHECK (quantity > 0),
                    price NUMERIC(12, 2) NOT NULL CHECK (price >= 0),
                    amount NUMERIC(14, 2) NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pallet_labels (
                    id SERIAL PRIMARY KEY,
                    code TEXT NOT NULL UNIQUE,
                    product_id INTEGER NOT NULL REFERENCES products(id),
                    net_weight NUMERIC(12, 3) NOT NULL CHECK (net_weight > 0),
                    tare_weight NUMERIC(12, 3) NOT NULL CHECK (tare_weight >= 0),
                    created_at TEXT NOT NULL
                );
                """
            )
        else:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    purchase_price REAL NOT NULL CHECK (purchase_price >= 0),
                    sale_price REAL NOT NULL CHECK (sale_price >= 0)
                );
                CREATE TABLE IF NOT EXISTS counterparties (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT,
                    inn TEXT,
                    address TEXT
                );
                CREATE TABLE IF NOT EXISTS warehouses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT
                );
                CREATE TABLE IF NOT EXISTS stock (
                    warehouse_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    quantity REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY (warehouse_id, product_id),
                    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
                    FOREIGN KEY (product_id) REFERENCES products(id)
                );
                CREATE TABLE IF NOT EXISTS cashbox (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    balance REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    number TEXT NOT NULL UNIQUE,
                    doc_date TEXT NOT NULL,
                    counterparty_id INTEGER NOT NULL,
                    warehouse_id INTEGER NOT NULL,
                    total REAL NOT NULL DEFAULT 0,
                    FOREIGN KEY (counterparty_id) REFERENCES counterparties(id),
                    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
                );
                CREATE TABLE IF NOT EXISTS purchase_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    purchase_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    quantity REAL NOT NULL CHECK (quantity > 0),
                    price REAL NOT NULL CHECK (price >= 0),
                    amount REAL NOT NULL,
                    FOREIGN KEY (purchase_id) REFERENCES purchases(id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                );
                CREATE TABLE IF NOT EXISTS sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    number TEXT NOT NULL UNIQUE,
                    doc_date TEXT NOT NULL,
                    counterparty_id INTEGER NOT NULL,
                    warehouse_id INTEGER NOT NULL,
                    total REAL NOT NULL DEFAULT 0,
                    FOREIGN KEY (counterparty_id) REFERENCES counterparties(id),
                    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
                );
                CREATE TABLE IF NOT EXISTS sale_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sale_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    quantity REAL NOT NULL CHECK (quantity > 0),
                    price REAL NOT NULL CHECK (price >= 0),
                    amount REAL NOT NULL,
                    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                );
                INSERT OR IGNORE INTO cashbox (id, balance) VALUES (1, 0);
                CREATE TABLE IF NOT EXISTS pallet_labels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    product_id INTEGER NOT NULL,
                    net_weight REAL NOT NULL CHECK (net_weight > 0),
                    tare_weight REAL NOT NULL CHECK (tare_weight >= 0),
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                );
                """
            )

def _row_to_dict(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)

def _rows(rows: list[Any]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]

def _next_number(conn: DBConnection, table: str, prefix: str) -> str:
    row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
    n = int(row["n"] if isinstance(row, dict) or hasattr(row, "keys") else row[0])
    return f"{prefix}-{n + 1:05d}"

def _stock_qty(conn: DBConnection, warehouse_id: int, product_id: int) -> float:
    row = conn.execute(
        "SELECT quantity FROM stock WHERE warehouse_id = ? AND product_id = ?",
        (warehouse_id, product_id),
    ).fetchone()
    if not row:
        return 0.0
    val = row["quantity"] if isinstance(row, dict) or hasattr(row, "keys") else row[0]
    return float(val or 0.0)

def _change_stock(conn: DBConnection, warehouse_id: int, product_id: int, delta: float) -> None:
    current = _stock_qty(conn, warehouse_id, product_id)
    new_qty = _round_qty(current + delta)
    if new_qty < -1e-9:
        product = conn.execute("SELECT sku, name FROM products WHERE id = ?", (product_id,)).fetchone()
        warehouse = conn.execute("SELECT name FROM warehouses WHERE id = ?", (warehouse_id,)).fetchone()
        label = f"{product['sku']} — {product['name']}" if product else str(product_id)
        wh = warehouse["name"] if warehouse else str(warehouse_id)
        raise AppError(f"Niewystarczający stan towaru w magazynie «{wh}»: {label}. Dostępne {current:g}, wymagana zmiana o {delta:g}.")
    conn.execute(
        "INSERT INTO stock (warehouse_id, product_id, quantity) VALUES (?, ?, ?) ON CONFLICT(warehouse_id, product_id) DO UPDATE SET quantity = excluded.quantity",
        (warehouse_id, product_id, max(new_qty, 0.0) if abs(new_qty) < 1e-9 else new_qty),
    )

def _change_cash(conn: DBConnection, delta: float) -> None:
    if conn.is_pg:
        conn.execute("UPDATE cashbox SET balance = ROUND(CAST(balance + ? AS numeric), 2) WHERE id = 1", (_round_money(delta),))
    else:
        conn.execute("UPDATE cashbox SET balance = ROUND(balance + ?, 2) WHERE id = 1", (_round_money(delta),))


# --- Товары ---

@cache_data(ttl=600)
def list_products() -> list[dict[str, Any]]:
    with get_conn() as conn:
        return _rows(conn.execute("SELECT id, sku, name, purchase_price, sale_price FROM products ORDER BY sku").fetchall())

@cache_data(ttl=600)
def get_product(product_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        return _row_to_dict(conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone())

def add_product(sku: str, name: str, purchase_price: float, sale_price: float) -> int:
    sku, name = sku.strip(), name.strip()
    if not sku or not name: raise AppError("Wypełnij indeks i nazwę towaru.")
    try:
        with get_conn() as conn:
            cur = conn.execute("INSERT INTO products (sku, name, purchase_price, sale_price) VALUES (?, ?, ?, ?) RETURNING id", (sku, name, _round_money(purchase_price), _round_money(sale_price)))
            row = cur.fetchone()
            clear_app_cache()
            return int(row["id"] if isinstance(row, dict) or hasattr(row, "keys") else row[0])
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower() or "integrity" in str(exc).lower(): raise AppError("Indeks musi być unikalny.") from exc
        raise

def update_product(product_id: int, sku: str, name: str, purchase_price: float, sale_price: float) -> None:
    sku, name = sku.strip(), name.strip()
    if not sku or not name: raise AppError("Wypełnij indeks i nazwę towaru.")
    try:
        with get_conn() as conn:
            cur = conn.execute("UPDATE products SET sku = ?, name = ?, purchase_price = ?, sale_price = ? WHERE id = ?", (sku, name, _round_money(purchase_price), _round_money(sale_price), product_id))
            if cur.rowcount == 0: raise AppError("Nie znaleziono towaru.")
            clear_app_cache()
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower() or "integrity" in str(exc).lower(): raise AppError("Indeks musi być unikalny.") from exc
        raise

def delete_product(product_id: int) -> None:
    with get_conn() as conn:
        used = conn.execute("SELECT 1 FROM purchase_lines WHERE product_id = ? UNION SELECT 1 FROM sale_lines WHERE product_id = ? UNION SELECT 1 FROM stock WHERE product_id = ? AND quantity > 0", (product_id, product_id, product_id)).fetchone()
        if used: raise AppError("Nie można usunąć towaru: jest używany w dokumentach lub ma stan magazynowy.")
        conn.execute("DELETE FROM stock WHERE product_id = ?", (product_id,))
        cur = conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        if cur.rowcount == 0: raise AppError("Nie znaleziono towaru.")
        clear_app_cache()


# --- Контрагенты ---

@cache_data(ttl=600)
def list_counterparties() -> list[dict[str, Any]]:
    with get_conn() as conn:
        return _rows(conn.execute("SELECT id, name, phone, inn, address FROM counterparties ORDER BY name").fetchall())

def add_counterparty(name: str, phone: str, inn: str, address: str) -> int:
    name = name.strip()
    if not name: raise AppError("Podaj nazwę kontrahenta.")
    with get_conn() as conn:
        cur = conn.execute("INSERT INTO counterparties (name, phone, inn, address) VALUES (?, ?, ?, ?) RETURNING id", (name, phone.strip(), inn.strip(), address.strip()))
        row = cur.fetchone()
        clear_app_cache()
        return int(row["id"] if isinstance(row, dict) or hasattr(row, "keys") else row[0])

def update_counterparty(counterparty_id: int, name: str, phone: str, inn: str, address: str) -> None:
    name = name.strip()
    if not name: raise AppError("Podaj nazwę kontrahenta.")
    with get_conn() as conn:
        cur = conn.execute("UPDATE counterparties SET name = ?, phone = ?, inn = ?, address = ? WHERE id = ?", (name, phone.strip(), inn.strip(), address.strip(), counterparty_id))
        if cur.rowcount == 0: raise AppError("Nie znaleziono kontrahenta.")
        clear_app_cache()

def delete_counterparty(counterparty_id: int) -> None:
    with get_conn() as conn:
        used = conn.execute("SELECT 1 FROM purchases WHERE counterparty_id = ? UNION SELECT 1 FROM sales WHERE counterparty_id = ?", (counterparty_id, counterparty_id)).fetchone()
        if used: raise AppError("Nie można usunąć kontrahenta: istnieją powiązane dokumenty.")
        cur = conn.execute("DELETE FROM counterparties WHERE id = ?", (counterparty_id,))
        if cur.rowcount == 0: raise AppError("Nie znaleziono kontrahenta.")
        clear_app_cache()


# --- Склады ---

@cache_data(ttl=600)
def list_warehouses() -> list[dict[str, Any]]:
    with get_conn() as conn:
        return _rows(conn.execute("SELECT id, name, description FROM warehouses ORDER BY name").fetchall())

def add_warehouse(name: str, description: str) -> int:
    name = name.strip()
    if not name: raise AppError("Podaj nazwę magazynu.")
    try:
        with get_conn() as conn:
            cur = conn.execute("INSERT INTO warehouses (name, description) VALUES (?, ?) RETURNING id", (name, description.strip()))
            row = cur.fetchone()
            clear_app_cache()
            return int(row["id"] if isinstance(row, dict) or hasattr(row, "keys") else row[0])
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower() or "integrity" in str(exc).lower(): raise AppError("Magazyn o takiej nazwie już istnieje.") from exc
        raise

def update_warehouse(warehouse_id: int, name: str, description: str) -> None:
    name = name.strip()
    if not name: raise AppError("Podaj nazwę magazynu.")
    try:
        with get_conn() as conn:
            cur = conn.execute("UPDATE warehouses SET name = ?, description = ? WHERE id = ?", (name, description.strip(), warehouse_id))
            if cur.rowcount == 0: raise AppError("Nie znaleziono magazynu.")
            clear_app_cache()
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower() or "integrity" in str(exc).lower(): raise AppError("Magazyn o takiej nazwie już istnieje.") from exc
        raise


# --- Касса и остатки ---

@cache_data(ttl=600)
def get_cash_balance() -> float:
    with get_conn() as conn:
        row = conn.execute("SELECT balance FROM cashbox WHERE id = 1").fetchone()
        val = row["balance"] if isinstance(row, dict) or hasattr(row, "keys") else (row[0] if row else 0)
        return _round_money(val or 0)

@cache_data(ttl=600)
def get_stock_report() -> list[dict[str, Any]]:
    with get_conn() as conn:
        return _rows(conn.execute("SELECT w.name AS warehouse, p.sku AS sku, p.name AS product, s.quantity AS quantity FROM stock s JOIN warehouses w ON w.id = s.warehouse_id JOIN products p ON p.id = s.product_id WHERE s.quantity > 0 ORDER BY w.name, p.sku").fetchall())

@cache_data(ttl=600)
def get_stock_qty(warehouse_id: int, product_id: int) -> float:
    with get_conn() as conn:
        return _stock_qty(conn, warehouse_id, product_id)


# --- Закупки ---

@cache_data(ttl=600)
def list_purchases() -> list[dict[str, Any]]:
    with get_conn() as conn:
        return _rows(conn.execute("SELECT p.id, p.number, p.doc_date, p.total, c.name AS counterparty, w.name AS warehouse FROM purchases p JOIN counterparties c ON c.id = p.counterparty_id JOIN warehouses w ON w.id = p.warehouse_id ORDER BY p.doc_date DESC, p.id DESC").fetchall())

@cache_data(ttl=600)
def get_purchase(purchase_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        header = _row_to_dict(conn.execute("SELECT p.id, p.number, p.doc_date, p.total, p.counterparty_id, p.warehouse_id, c.name AS counterparty, w.name AS warehouse FROM purchases p JOIN counterparties c ON c.id = p.counterparty_id JOIN warehouses w ON w.id = p.warehouse_id WHERE p.id = ?", (purchase_id,)).fetchone())
        if not header: return None
        header["lines"] = _rows(conn.execute("SELECT l.product_id, l.quantity, l.price, l.amount, pr.sku, pr.name AS product FROM purchase_lines l JOIN products pr ON pr.id = l.product_id WHERE l.purchase_id = ? ORDER BY l.id", (purchase_id,)).fetchall())
        return header

def create_purchase(doc_date: str, counterparty_id: int, warehouse_id: int, lines: list[dict[str, Any]]) -> str:
    if not doc_date: raise AppError("Podaj datę dokumentu zakupu.")
    if not counterparty_id: raise AppError("Wybierz kontrahenta (dostawcę).")
    if not warehouse_id: raise AppError("Wybierz magazyn przyjęcia.")
    if not lines: raise AppError("Dodaj co najmniej jeden wiersz w części tabelarycznej.")

    normalized, total = [], 0.0
    for line in lines:
        product_id, qty, price = int(line["product_id"]), _round_qty(line["quantity"]), _round_money(line["price"])
        if qty <= 0: raise AppError("Ilość w wierszu musi być większa od zera.")
        if price < 0: raise AppError("Cena nie może być ujemna.")
        amount = _round_money(qty * price)
        total += amount
        normalized.append((product_id, qty, price, amount))
    total = _round_money(total)

    with get_conn() as conn:
        number = _next_number(conn, "purchases", "ZK")
        cur = conn.execute("INSERT INTO purchases (number, doc_date, counterparty_id, warehouse_id, total) VALUES (?, ?, ?, ?, ?) RETURNING id", (number, doc_date, counterparty_id, warehouse_id, total))
        row = cur.fetchone()
        purchase_id = int(row["id"] if isinstance(row, dict) or hasattr(row, "keys") else row[0])
        for product_id, qty, price, amount in normalized:
            conn.execute("INSERT INTO purchase_lines (purchase_id, product_id, quantity, price, amount) VALUES (?, ?, ?, ?, ?)", (purchase_id, product_id, qty, price, amount))
            _change_stock(conn, warehouse_id, product_id, qty)
        _change_cash(conn, -total)
    clear_app_cache()
    return number

def delete_purchase(purchase_id: int) -> None:
    doc = get_purchase(purchase_id)
    if not doc: raise AppError("Nie znaleziono dokumentu zakupu.")
    with get_conn() as conn:
        for line in doc["lines"]: _change_stock(conn, doc["warehouse_id"], line["product_id"], -float(line["quantity"]))
        _change_cash(conn, float(doc["total"]))
        conn.execute("DELETE FROM purchase_lines WHERE purchase_id = ?", (purchase_id,))
        conn.execute("DELETE FROM purchases WHERE id = ?", (purchase_id,))
    clear_app_cache()


# --- Продажи ---

@cache_data(ttl=600)
def list_sales() -> list[dict[str, Any]]:
    with get_conn() as conn:
        return _rows(conn.execute("SELECT s.id, s.number, s.doc_date, s.total, c.name AS counterparty, w.name AS warehouse FROM sales s JOIN counterparties c ON c.id = s.counterparty_id JOIN warehouses w ON w.id = s.warehouse_id ORDER BY s.doc_date DESC, s.id DESC").fetchall())

@cache_data(ttl=600)
def get_sale(sale_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        header = _row_to_dict(conn.execute("SELECT s.id, s.number, s.doc_date, s.total, s.counterparty_id, s.warehouse_id, c.name AS counterparty, w.name AS warehouse FROM sales s JOIN counterparties c ON c.id = s.counterparty_id JOIN warehouses w ON w.id = s.warehouse_id WHERE s.id = ?", (sale_id,)).fetchone())
        if not header: return None
        header["lines"] = _rows(conn.execute("SELECT l.product_id, l.quantity, l.price, l.amount, pr.sku, pr.name AS product FROM sale_lines l JOIN products pr ON pr.id = l.product_id WHERE l.sale_id = ? ORDER BY l.id", (sale_id,)).fetchall())
        return header

def create_sale(doc_date: str, counterparty_id: int, warehouse_id: int, lines: list[dict[str, Any]]) -> str:
    if not doc_date: raise AppError("Podaj datę dokumentu sprzedaży.")
    if not counterparty_id: raise AppError("Wybierz kontrahenta (nabywcę).")
    if not warehouse_id: raise AppError("Wybierz magazyn wydania.")
    if not lines: raise AppError("Dodaj co najmniej jeden wiersz w części tabelarycznej.")

    normalized, totals_by_product, total = [], {}, 0.0
    for line in lines:
        product_id, qty, price = int(line["product_id"]), _round_qty(line["quantity"]), _round_money(line["price"])
        if qty <= 0: raise AppError("Ilość w wierszu musi być większa od zera.")
        if price < 0: raise AppError("Cena nie może być ujemna.")
        amount = _round_money(qty * price)
        total += amount
        normalized.append((product_id, qty, price, amount))
        totals_by_product[product_id] = totals_by_product.get(product_id, 0.0) + qty
    total = _round_money(total)

    with get_conn() as conn:
        for product_id, qty_need in totals_by_product.items():
            available = _stock_qty(conn, warehouse_id, product_id)
            if available + 1e-9 < qty_need:
                product = conn.execute("SELECT sku, name FROM products WHERE id = ?", (product_id,)).fetchone()
                label = f"{product['sku']} — {product['name']}" if product else str(product_id)
                raise AppError(f"Nie można zatwierdzić sprzedaży: w magazynie brakuje towaru «{label}». Dostępne {available:g}, w dokumencie {qty_need:g}.")

        number = _next_number(conn, "sales", "SP")
        cur = conn.execute("INSERT INTO sales (number, doc_date, counterparty_id, warehouse_id, total) VALUES (?, ?, ?, ?, ?) RETURNING id", (number, doc_date, counterparty_id, warehouse_id, total))
        row = cur.fetchone()
        sale_id = int(row["id"] if isinstance(row, dict) or hasattr(row, "keys") else row[0])
        for product_id, qty, price, amount in normalized:
            conn.execute("INSERT INTO sale_lines (sale_id, product_id, quantity, price, amount) VALUES (?, ?, ?, ?, ?)", (sale_id, product_id, qty, price, amount))
            _change_stock(conn, warehouse_id, product_id, -qty)
        _change_cash(conn, total)
    clear_app_cache()
    return number

def delete_sale(sale_id: int) -> None:
    doc = get_sale(sale_id)
    if not doc: raise AppError("Nie znaleziono dokumentu sprzedaży.")
    with get_conn() as conn:
        for line in doc["lines"]: _change_stock(conn, doc["warehouse_id"], line["product_id"], float(line["quantity"]))
        _change_cash(conn, -float(doc["total"]))
        conn.execute("DELETE FROM sale_lines WHERE sale_id = ?", (sale_id,))
        conn.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
    clear_app_cache()

@cache_data(ttl=600)
def get_dashboard_totals() -> dict[str, float]:
    with get_conn() as conn:
        p_row = conn.execute("SELECT COALESCE(SUM(total), 0) AS s FROM purchases").fetchone()
        purchases = p_row["s"] if isinstance(p_row, dict) or hasattr(p_row, "keys") else p_row[0]
        s_row = conn.execute("SELECT COALESCE(SUM(total), 0) AS s FROM sales").fetchone()
        sales = s_row["s"] if isinstance(s_row, dict) or hasattr(s_row, "keys") else s_row[0]
        c_row = conn.execute("SELECT balance FROM cashbox WHERE id = 1").fetchone()
        cash = c_row["balance"] if isinstance(c_row, dict) or hasattr(c_row, "keys") else (c_row[0] if c_row else 0)
    return {
        "purchases": _round_money(purchases),
        "sales": _round_money(sales),
        "profit": _round_money(float(sales) - float(purchases)),
        "cash": _round_money(cash),
    }

def peek_next_pallet_code() -> str:
    with get_conn() as conn: return _next_pallet_code(conn)

def _next_pallet_code(conn: DBConnection) -> str:
    row = conn.execute("SELECT MAX(CAST(code AS INTEGER)) AS m FROM pallet_labels").fetchone()
    val = row["m"] if isinstance(row, dict) or hasattr(row, "keys") else (row[0] if row else 0)
    n = int(val or 0) + 1
    if n > 999999: raise AppError("Wykorzystano pulę kodów palet (000001–999999).")
    return f"{n:06d}"

def create_pallet_label(product_id: int, net_weight: float, tare_weight: float) -> dict[str, Any]:
    if not product_id: raise AppError("Wybierz towar na etykietę.")
    net_weight, tare_weight = _round_qty(net_weight), _round_qty(tare_weight)
    if net_weight <= 0: raise AppError("Masa netto musi być większa od zera.")
    if tare_weight < 0: raise AppError("Tara nie może być ujemna.")
    with get_conn() as conn:
        product = conn.execute("SELECT id, sku, name FROM products WHERE id = ?", (product_id,)).fetchone()
        if not product: raise AppError("Nie znaleziono towaru.")
        code = _next_pallet_code(conn)
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute("INSERT INTO pallet_labels (code, product_id, net_weight, tare_weight, created_at) VALUES (?, ?, ?, ?, ?) RETURNING id", (code, product_id, net_weight, tare_weight, created_at))
        row = cur.fetchone()
        label_id = int(row["id"] if isinstance(row, dict) or hasattr(row, "keys") else row[0])
    clear_app_cache()
    return {
        "id": label_id, "code": code, "product_id": product_id,
        "sku": product["sku"], "product": product["name"],
        "net_weight": net_weight, "tare_weight": tare_weight,
        "gross_weight": _round_qty(net_weight + tare_weight),
        "created_at": created_at,
    }

@cache_data(ttl=600)
def list_pallet_labels(limit: int = 50) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = _rows(conn.execute("SELECT l.id, l.code, l.product_id, l.net_weight, l.tare_weight, l.created_at, p.sku, p.name AS product FROM pallet_labels l JOIN products p ON p.id = l.product_id ORDER BY l.id DESC LIMIT ?", (limit,)).fetchall())
    for row in rows: row["gross_weight"] = _round_qty(float(row["net_weight"]) + float(row["tare_weight"]))
    return rows

@cache_data(ttl=600)
def get_pallet_label(label_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = _row_to_dict(conn.execute("SELECT l.id, l.code, l.product_id, l.net_weight, l.tare_weight, l.created_at, p.sku, p.name AS product FROM pallet_labels l JOIN products p ON p.id = l.product_id WHERE l.id = ?", (label_id,)).fetchone())
    if not row: return None
    row["gross_weight"] = _round_qty(float(row["net_weight"]) + float(row["tare_weight"]))
    return row
