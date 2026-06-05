import sqlite3
import os
import json

def get_base_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_db_path():
    return os.path.join(get_base_dir(), 'data', 'shop.db')

def get_db_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Create Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create Products table
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

    # Add views column to products if not exists
    try:
        c.execute("ALTER TABLE products ADD COLUMN views INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # Create Carts table
    c.execute('''
        CREATE TABLE IF NOT EXISTS carts (
            email TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (email, product_id),
            FOREIGN KEY (email) REFERENCES users (email),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')
    
    # Create Saved Items table
    c.execute('''
        CREATE TABLE IF NOT EXISTS saved_items (
            email TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            PRIMARY KEY (email, product_id),
            FOREIGN KEY (email) REFERENCES users (email),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')

    # Add collection_name column to saved_items if not exists
    try:
        c.execute("ALTER TABLE saved_items ADD COLUMN collection_name TEXT DEFAULT 'Favorites'")
    except sqlite3.OperationalError:
        pass

    # Create Recommendation Feedback table
    c.execute('''
        CREATE TABLE IF NOT EXISTS recommendation_feedback (
            email TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            feedback_type TEXT NOT NULL,
            PRIMARY KEY (email, product_id)
        )
    ''')

    # Create Product Prices (marketplace comparisons) table
    c.execute('''
        CREATE TABLE IF NOT EXISTS product_prices (
            product_id INTEGER NOT NULL,
            marketplace_name TEXT NOT NULL,
            price REAL NOT NULL,
            discount_percentage REAL NOT NULL DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (product_id, marketplace_name),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')

    # Create Orders table
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            total REAL NOT NULL,
            payment_method TEXT NOT NULL,
            items_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (email) REFERENCES users (email)
        )
    ''')

    conn.commit()
    conn.close()

def migrate_catalog_to_db():
    """Migrate data from catalog.json to the sqlite database if the products table is empty."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM products")
    count = c.fetchone()[0]
    
    if count == 0:
        print("Migrating catalog.json into SQLite Database...")
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
    products = c.execute("SELECT id, price FROM products").fetchall()
    import random
    for p in products:
        p_id, base_price = p['id'], p['price']
        # Check if we already have 4 marketplaces seeded for this product
        exists = c.execute("SELECT COUNT(*) FROM product_prices WHERE product_id = ?", (p_id,)).fetchone()[0]
        if exists < 4:
            # Seed by product ID so price generation is deterministic
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
    """Sync product catalog updates into the database."""
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
                c.execute(
                    "UPDATE products SET name = ?, price = ?, description = ?, category = ?, rating = ?, image = ? WHERE id = ?",
                    (
                        product.get('name', ''),
                        product.get('price', 0),
                        product.get('description', ''),
                        product.get('category', ''),
                        product.get('rating', 0.0),
                        product.get('image', ''),
                        product.get('id')
                    )
                )
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
        
        # Delete products not in catalog
        catalog_ids = [p.get('id') for p in catalog if p.get('id') is not None]
        if catalog_ids:
            placeholders = ', '.join(['?'] * len(catalog_ids))
            c.execute(f"DELETE FROM products WHERE id NOT IN ({placeholders})", tuple(catalog_ids))
        
        conn.commit()
    conn.close()

if __name__ == '__main__':
    setup_database()
