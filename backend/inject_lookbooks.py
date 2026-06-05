import json
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def add_lookbook_items():
    images = {
        "VIBE_PARTY_1": "/static/modest_evening_gown.png",
        "VIBE_PARTY_2": "https://images.unsplash.com/photo-1596462502278-27bfdc403348?q=80&w=800",
        "VIBE_PARTY_3": "/static/shoes/shoe_9003.png",
        "VIBE_PRO_1": "https://images.unsplash.com/photo-1594938298603-c8148c4dae35?q=80&w=800",
        "VIBE_PRO_2": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?q=80&w=800",
        "VIBE_PRO_3": "/static/shoes/shoe_9006.png",
        "VIBE_COMFORT_1": "https://images.unsplash.com/photo-1624623278313-a930126a11c3?q=80&w=800",
        "VIBE_COMFORT_2": "https://images.unsplash.com/photo-1509631179647-0c7042a9b407?q=80&w=800",
        "VIBE_COMFORT_3": "https://images.unsplash.com/photo-1514066558159-fc8c737ef259?q=80&w=800"
    }

    products = [
        {"id": 9001, "name": "Elegant Evening Gown", "price": 5200, "category": "Women Fashion", "image": images["VIBE_PARTY_1"], "rating": 4.9, "description": "A sleek, modest evening gown perfect for classy parties.", "popularity": 1},
        {"id": 9002, "name": "Pro Beauty Kit Collection", "price": 3200, "category": "Beauty", "image": images["VIBE_PARTY_2"], "rating": 4.8, "description": "Everything you need for a flawless party glam look.", "popularity": 1},
        {"id": 9003, "name": "Stiletto Party Heels", "price": 2800, "category": "Shoes", "image": images["VIBE_PARTY_3"], "rating": 4.7, "description": "Classic red stilettos to complete any evening look.", "popularity": 1},
        {"id": 9004, "name": "Bespoke Navy Suit", "price": 12000, "category": "Men Fashion", "image": images["VIBE_PRO_1"], "rating": 4.9, "description": "A sharply tailored navy suit for the ultimate professional edge.", "popularity": 1},
        {"id": 9005, "name": "Executive Leather Briefcase", "price": 5600, "category": "Men Fashion", "image": images["VIBE_PRO_2"], "rating": 4.8, "description": "Premium leather crafted for your laptop and documents.", "popularity": 1},
        {"id": 9006, "name": "Classic Leather Oxfords", "price": 4200, "category": "Shoes", "image": images["VIBE_PRO_3"], "rating": 4.9, "description": "Timeless leather oxfords that step up your career.", "popularity": 1},
        {"id": 9007, "name": "Oversized Cozy Sweater", "price": 1800, "category": "Women Fashion", "image": images["VIBE_COMFORT_1"], "rating": 4.8, "description": "Sink into ultimate relaxation with this oversized knit.", "popularity": 1},
        {"id": 9010, "name": "Men's Relaxed Fit Cotton Hoodie", "price": 2500, "category": "Men Fashion", "image": "https://images.unsplash.com/photo-1556821840-3a63f95609a7?q=80&w=800", "rating": 4.8, "description": "A very comfortable and cozy hoodie for everyday wear.", "popularity": 1},
        {"id": 9011, "name": "Men's Cozy Lounge Joggers", "price": 1800, "category": "Men Fashion", "image": "https://images.unsplash.com/photo-1584865288642-42078afe6942?q=80&w=800", "rating": 4.7, "description": "Relaxed sweatpants perfect for lounging at home.", "popularity": 1},
        {"id": 9012, "name": "Women's Fleece Pullover Sweater", "price": 2800, "category": "Women Fashion", "image": "https://images.unsplash.com/photo-1576566588028-4147f3842f27?q=80&w=800", "rating": 4.9, "description": "Warm, fluffy, and stylish pullover sweater.", "popularity": 1},
        {"id": 9013, "name": "Unisex Classic Comfort Sneakers", "price": 3500, "category": "Shoes", "image": "/static/shoes/shoe_9013.png", "rating": 4.6, "description": "Soft inner lining and supportive sole for all-day comfort.", "popularity": 1},
        {"id": 9014, "name": "Men's Soft Cotton T-Shirt", "price": 900, "category": "Men Fashion", "image": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?q=80&w=800", "rating": 4.7, "description": "Breathable and incredibly soft t-shirt.", "popularity": 1}
    ]

    catalog_path = os.path.join(BASE_DIR, 'data', 'catalog.json')
    db_path = os.path.join(BASE_DIR, 'data', 'shop.db')

    with open(catalog_path, 'r', encoding='utf-8') as f:
        catalog = json.load(f)

    catalog = [p for p in catalog if p.get('id') < 9000]
    catalog.extend(products)

    with open(catalog_path, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=4)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    for p in products:
        c.execute('''
            INSERT OR REPLACE INTO products (id, name, price, description, category, rating, image, popularity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (p['id'], p['name'], p['price'], p['description'], p['category'], p['rating'], p['image'], p['popularity']))

    conn.commit()
    conn.close()

add_lookbook_items()
print("Lookbook items added to DB!")
