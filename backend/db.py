import os
import json
import re

def get_base_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_db_path():
    return os.path.join(get_base_dir(), 'data', 'shop.db')

def _is_postgres():
    return bool(os.environ.get('DATABASE_URL'))

PG_UPSERT_MAP = {
    'product_prices': (
        '(product_id, marketplace_name)',
        'price=EXCLUDED.price, discount_percentage=EXCLUDED.discount_percentage, last_updated=CURRENT_TIMESTAMP'
    ),
    'saved_items': (
        '(email, product_id)',
        'collection_name=EXCLUDED.collection_name'
    ),
    'recommendation_feedback': (
        '(email, product_id)',
        'feedback_type=EXCLUDED.feedback_type'
    ),
}

class _CompatCursor:
    """Wraps a psycopg2 cursor to return _CompatRow from fetch methods."""
    def __init__(self, cursor):
        self._cur = cursor
        self.description = cursor.description
        self.rowcount = cursor.rowcount
    @property
    def arraysize(self):
        return self._cur.arraysize
    @arraysize.setter
    def arraysize(self, value):
        self._cur.arraysize = value
    def execute(self, sql, params=None):
        if params is not None:
            self._cur.execute(sql, params)
        else:
            self._cur.execute(sql)
        self.description = self._cur.description
        self.rowcount = self._cur.rowcount
        return self
    def _wrap(self, row):
        if row is None:
            return None
        columns = [desc[0] for desc in self.description] if self.description else []
        return _CompatRow(row, columns)
    def fetchone(self):
        return self._wrap(self._cur.fetchone())
    def fetchall(self):
        return [self._wrap(r) for r in self._cur.fetchall()]
    def fetchmany(self, size=None):
        if size is None:
            return [self._wrap(r) for r in self._cur.fetchmany()]
        return [self._wrap(r) for r in self._cur.fetchmany(size)]
    def __iter__(self):
        for row in self._cur:
            yield self._wrap(row)

class _CompatRow:
    """Supports both dict access (row['name']) and integer index access (row[0])."""
    def __init__(self, row, columns):
        self._row = row
        self._columns = columns
    def __getitem__(self, key):
        if isinstance(key, int):
            return self._row[self._columns[key]]
        return self._row[key]
    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, IndexError):
            return default
    def __contains__(self, key):
        if isinstance(key, int):
            return 0 <= key < len(self._columns)
        return key in self._row
    def keys(self):
        return self._columns
    def values(self):
        return [self._row[c] for c in self._columns]
    def items(self):
        return [(c, self._row[c]) for c in self._columns]

class DBConnection:
    def __init__(self):
        self.is_postgres = _is_postgres()
        if self.is_postgres:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            database_url = os.environ['DATABASE_URL']
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            self.conn = psycopg2.connect(database_url)
            self._cursor_factory = RealDictCursor
        else:
            import sqlite3
            os.makedirs(os.path.join(get_base_dir(), 'data'), exist_ok=True)
            self.conn = sqlite3.connect(get_db_path())
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA busy_timeout=5000")

    def execute(self, sql, params=None):
        if self.is_postgres:
            sql = sql.replace('?', '%s')
            for table, (conflict, updates) in PG_UPSERT_MAP.items():
                if f'INSERT OR REPLACE INTO {table}' in sql:
                    sql = sql.replace(
                        f'INSERT OR REPLACE INTO {table}',
                        f'INSERT INTO {table}'
                    )
                    sql += f' ON CONFLICT {conflict} DO UPDATE SET {updates}'
                    break
            cur = self.conn.cursor(cursor_factory=self._cursor_factory)
        else:
            cur = self.conn.cursor()
        if params is not None:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        if self.is_postgres:
            return _CompatCursor(cur)
        return cur

    def close(self):
        self.conn.close()

    def commit(self):
        self.conn.commit()

    def cursor(self):
        if self.is_postgres:
            from psycopg2.extras import RealDictCursor
            return self.conn.cursor(cursor_factory=RealDictCursor)
        return self.conn.cursor()

def get_db_connection():
    return DBConnection()

def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT,
            category TEXT,
            rating REAL,
            popularity BOOLEAN,
            image TEXT,
            badge_class TEXT,
            badge_icon TEXT,
            badge_text TEXT
        )
    ''')

    try:
        c.execute("ALTER TABLE products ADD COLUMN views INTEGER DEFAULT 0")
    except Exception:
        pass

    c.execute('''
        CREATE TABLE IF NOT EXISTS carts (
            email TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (email, product_id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS saved_items (
            email TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            PRIMARY KEY (email, product_id)
        )
    ''')

    try:
        c.execute("ALTER TABLE saved_items ADD COLUMN collection_name TEXT DEFAULT 'Favorites'")
    except Exception:
        pass

    c.execute('''
        CREATE TABLE IF NOT EXISTS recommendation_feedback (
            email TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            feedback_type TEXT NOT NULL,
            PRIMARY KEY (email, product_id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS product_prices (
            product_id INTEGER NOT NULL,
            marketplace_name TEXT NOT NULL,
            price REAL NOT NULL,
            discount_percentage REAL NOT NULL DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (product_id, marketplace_name)
        )
    ''')

    if conn.is_postgres:
        c.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                email TEXT NOT NULL,
                total REAL NOT NULL,
                payment_method TEXT NOT NULL,
                items_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    else:
        c.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                total REAL NOT NULL,
                payment_method TEXT NOT NULL,
                items_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    conn.commit()
    conn.close()

def migrate_catalog_to_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM products")
    count = c.fetchone()[0]

    if count == 0:
        print("Migrating catalog.json into Database...")
        catalog_path = os.path.join(get_base_dir(), 'data', 'catalog.json')
        if os.path.exists(catalog_path):
            with open(catalog_path, 'r', encoding='utf-8') as f:
                catalog = json.load(f)
            for product in catalog:
                c.execute('''
                    INSERT INTO products
                    (id, name, price, description, category, rating, popularity, image, badge_class, badge_icon, badge_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    product.get('id'),
                    product.get('name', ''),
                    product.get('price', 0),
                    product.get('description', ''),
                    product.get('category', ''),
                    product.get('rating', 0.0),
                    product.get('popularity', False),
                    product.get('image', ''),
                    product.get('badge_class', ''),
                    product.get('badge_icon', ''),
                    product.get('badge_text', '')
                ))
            conn.commit()
            print(f"Successfully migrated {len(catalog)} products.")
        else:
            print("catalog.json not found. Could not migrate.")
    conn.close()

_last_catalog_mtime = 0

def populate_marketplace_prices():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, price FROM products")
    products = c.fetchall()
    import random
    for p_row in products:
        p_id = p_row[0] if conn.is_postgres else p_row['id']
        base_price = p_row[1] if conn.is_postgres else p_row['price']
        c.execute("SELECT COUNT(*) FROM product_prices WHERE product_id = ?", (p_id,))
        exists = c.fetchone()[0]
        if exists < 4:
            random.seed(p_id)
            for m in ['Amazon', 'Flipkart', 'Myntra', 'AJIO']:
                price = int(base_price * random.uniform(0.85, 1.15))
                discount = random.randint(5, 40)
                c.execute('''
                    INSERT OR REPLACE INTO product_prices (product_id, marketplace_name, price, discount_percentage)
                    VALUES (?, ?, ?, ?)
                ''', (p_id, m, price, discount))
    conn.commit()
    conn.close()

def setup_database():
    init_db()
    migrate_catalog_to_db()
    global _last_catalog_mtime
    catalog_path = os.path.join(get_base_dir(), 'data', 'catalog.json')
    if os.path.exists(catalog_path):
        current_mtime = os.path.getmtime(catalog_path)
        if current_mtime != _last_catalog_mtime:
            sync_catalog_images()
            _last_catalog_mtime = current_mtime
    populate_marketplace_prices()

def sync_catalog_images():
    conn = get_db_connection()
    c = conn.cursor()
    catalog_path = os.path.join(get_base_dir(), 'data', 'catalog.json')
    if os.path.exists(catalog_path):
        with open(catalog_path, 'r', encoding='utf-8') as f:
            catalog = json.load(f)
        for product in catalog:
            c.execute("SELECT 1 FROM products WHERE id = ?", (product.get('id'),))
            exists = c.fetchone()
            if exists:
                c.execute('''
                    UPDATE products SET name = ?, price = ?, description = ?, category = ?, rating = ?, image = ? WHERE id = ?
                ''', (
                    product.get('name', ''),
                    product.get('price', 0),
                    product.get('description', ''),
                    product.get('category', ''),
                    product.get('rating', 0.0),
                    product.get('image', ''),
                    product.get('id')
                ))
            else:
                c.execute('''
                    INSERT INTO products
                    (id, name, price, description, category, rating, popularity, image, badge_class, badge_icon, badge_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    product.get('id'),
                    product.get('name', ''),
                    product.get('price', 0),
                    product.get('description', ''),
                    product.get('category', ''),
                    product.get('rating', 0.0),
                    product.get('popularity', False),
                    product.get('image', ''),
                    product.get('badge_class', ''),
                    product.get('badge_icon', ''),
                    product.get('badge_text', '')
                ))
        catalog_ids = [p.get('id') for p in catalog if p.get('id') is not None]
        if catalog_ids:
            placeholders = ', '.join(['?'] * len(catalog_ids))
            c.execute(f"DELETE FROM products WHERE id NOT IN ({placeholders})", tuple(catalog_ids))
        conn.commit()
    conn.close()

if __name__ == '__main__':
    setup_database()
