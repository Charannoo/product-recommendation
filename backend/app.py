from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import urllib.parse
import os
import glob
import random
import time
import smtplib
from email.message import EmailMessage
from flask import make_response
from datetime import timedelta
import re

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_env_file():
    env_path = os.path.join(base_dir, '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    os.environ.setdefault(key.strip(), val.strip().strip("'\""))

load_env_file()

app = Flask(__name__, template_folder=os.path.join(base_dir, 'frontend', 'templates'), static_folder=os.path.join(base_dir, 'frontend', 'static'))
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'smartshop_secret_key')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# Validation helpers
def is_valid_email(val):
    if not val:
        return False
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', val))

def is_valid_mobile(val):
    if not val:
        return False
    return bool(re.match(r'^\d{10}$', val))

# OTP Rate limiting state
otp_requests = {}  # { identifier: [timestamps] }
ip_requests = {}   # { ip_address: [timestamps] }

def check_otp_rate_limit(identifier, ip):
    now = time.time()
    
    # Clean up old timestamps (older than 1 hour)
    if identifier in otp_requests:
        otp_requests[identifier] = [t for t in otp_requests[identifier] if now - t < 3600]
    else:
        otp_requests[identifier] = []
        
    if ip in ip_requests:
        ip_requests[ip] = [t for t in ip_requests[ip] if now - t < 3600]
    else:
        ip_requests[ip] = []
        
    # IP limit: max 10 requests per minute
    ip_1m = [t for t in ip_requests[ip] if now - t < 60]
    if len(ip_1m) >= 10:
        return True, "Too many OTP requests from this IP. Please wait a minute."
        
    # Identifier limit 1: max 3 requests per minute
    id_1m = [t for t in otp_requests[identifier] if now - t < 60]
    if len(id_1m) >= 3:
        return True, f"Please wait {int(60 - (now - id_1m[0]))} seconds before requesting a new OTP."
        
    # Identifier limit 2: max 5 requests per hour
    if len(otp_requests[identifier]) >= 5:
        return True, f"Max OTP limit reached. Please try again in {int((3600 - (now - otp_requests[identifier][0])) // 60) + 1} minutes."
        
    return False, ""

def record_otp_request(identifier, ip):
    now = time.time()
    if identifier not in otp_requests:
        otp_requests[identifier] = []
    otp_requests[identifier].append(now)
    
    if ip not in ip_requests:
        ip_requests[ip] = []
    ip_requests[ip].append(now)

@app.before_request
def make_session_permanent():
    session.permanent = True

import json
try:
    from chatbot import get_chatbot_response
except ImportError:
    from backend.chatbot import get_chatbot_response

# Load Mock Data
def load_catalog():
    try:
        try:
            from db import get_db_connection, setup_database, get_base_dir
        except ImportError:
            from backend.db import get_db_connection, setup_database, get_base_dir
        setup_database()
        conn = get_db_connection()
        products_db = conn.execute("SELECT * FROM products").fetchall()
        conn.close()
        
        products = [dict(p) for p in products_db]
        
        # Enrich with brand, color, size, and discount from catalog.json
        catalog_path = os.path.join(get_base_dir(), 'data', 'catalog.json')
        if os.path.exists(catalog_path):
            with open(catalog_path, 'r', encoding='utf-8') as f:
                catalog = json.load(f)
            catalog_map = {p['id']: p for p in catalog if 'id' in p}
            for p in products:
                cat_item = catalog_map.get(p['id'])
                if cat_item:
                    for k, v in cat_item.items():
                        if k not in p:
                            p[k] = v
        return products
    except Exception as e:
        print("Failed to load catalog.json:", e)
        return []

mock_products = load_catalog()


def _pick_existing_static_image(pattern: str) -> str | None:
    matches = glob.glob(os.path.join(app.static_folder, pattern))
    if not matches:
        return None
    filename = os.path.basename(matches[0])
    return f"/static/{filename}"


def normalize_product_image(product):
    """Keep critical category images visible even when external hosts fail."""
    category = product.get("category", "")
    image = (product.get("image") or "").strip()
    product_id = product.get("id")

    # Ensure men fashion always has a local image fallback.
    if category == "Men Fashion":
        if image.startswith("/static/"):
            return
        local_men = _pick_existing_static_image(f"men_{product_id}_*.svg")
        product["image"] = local_men or "/static/placeholders/clothing.svg"
        return

    # Ensure toys always has a local image fallback.
    if category == "Toys":
        if image.startswith("/static/"):
            return
        local_toy = _pick_existing_static_image(f"toy_real_{product_id}.jpg")
        product["image"] = local_toy or "/static/placeholders/toys.svg"


def normalize_products_images(products):
    for product in products:
        normalize_product_image(product)

# Import the ML model
try:
    from model import get_user_recommendations
except ImportError:
    from backend.model import get_user_recommendations

def extract_user_history_ids():
    ids = set()
    user = session.get('user')
    if user:
        try:
            from db import get_db_connection
        except ImportError:
            from backend.db import get_db_connection
        conn = get_db_connection()
        rows = conn.execute("SELECT product_id FROM carts WHERE email = ?", (user,)).fetchall()
        for r in rows: ids.add(r['product_id'])
        rows = conn.execute("SELECT product_id FROM saved_items WHERE email = ?", (user,)).fetchall()
        for r in rows: ids.add(r['product_id'])
        rows = conn.execute("SELECT items_json FROM orders WHERE email = ?", (user,)).fetchall()
        for r in rows:
            items = json.loads(r['items_json'])
            for it in items: ids.add(it.get('id', 0))
        conn.close()
    else:
        cart_items = session.get('cart') if session.get('cart') is not None else mock_cart_items
        for item in cart_items:
            match = next((p for p in mock_products if p.get('name') == item.get('name')), None)
            if match:
                ids.add(match.get('id'))
    return list(ids)

mock_cart_items = [
    {
        "name": "Sony WH-1000XM4", 
        "price": 24999, 
        "quantity": 2,
        "image": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?q=80&w=1000&auto=format&fit=crop"
    }
]

def get_filtered_products(args):
    # reload catalog each request so updates to catalog.json are picked up without restarting
    display_products = load_catalog()
    
    # Extract query params supporting both legacy '?filter=X&val=Y' and new multi-params '?category=X&brand=Y'
    filter_type = args.get('filter')
    val = args.get('val')
    range_val = args.get('range')
    
    category = args.get('category') or (val if filter_type == 'category' else None)
    search = args.get('search') or (val if filter_type == 'search' else None)
    brand = args.get('brand') or (val if filter_type == 'brand' else None)
    discount = args.get('discount') or (val if filter_type == 'discount' else None)
    price = args.get('price') or (range_val if filter_type == 'price' else None)
    max_price = args.get('max_price')
    rating = args.get('rating') or (val if filter_type == 'rating' else None)
    popularity = args.get('popularity') or (val if filter_type == 'popularity' else None)
    sort = args.get('sort')
    
    if category:
        display_products = [p for p in display_products if p.get('category', '').lower() == category.lower()]
        
    cat_min = 0
    cat_max = 200000
    if display_products:
        cat_min = min(p.get('price', 0) for p in display_products)
        cat_max = max(p.get('price', 0) for p in display_products)
        
    if search:
        q = search.lower()
        
        # Smart synonym mapping for better semantic search matches
        synonyms = {
            "phone": ["iphone", "smartphone", "mobile", "galaxy", "cellphone"],
            "shoes": ["sneakers", "footwear", "running", "air max"],
            "tv": ["television", "smart tv", "screen", "display"],
            "clothes": ["fashion", "shirt", "jeans", "t-shirt", "jacket", "activewear"],
            "laptop": ["computer", "notebook", "inspiron", "macbook", "pc"],
            "watch": ["smartwatch", "wearable", "timepiece"],
            "earphones": ["headphones", "airpods", "buds", "headset"],
            "audio": ["headphones", "airpods", "buds", "headset", "speaker"]
        }
        
        search_terms = [q]
        for key, related in synonyms.items():
            if key in q or q in key:
                search_terms.extend(related)
                
        def product_matches_search(p):
            p_text = (p.get('name', '') + ' ' + p.get('description', '') + ' ' + p.get('category', '')).lower()
            return any(term in p_text for term in search_terms)
            
        display_products = [p for p in display_products if product_matches_search(p)]
        
    if brand:
        display_products = [p for p in display_products if brand.lower() in p.get('name', '').lower() or brand.lower() in p.get('description', '').lower()]
        
    if discount:
        try:
            d = int(discount)
            display_products = [p for p in display_products if p.get('discount', 0) >= d]
        except ValueError: pass
        
    if price:
        if price == 'under_1000':
            display_products = [p for p in display_products if p.get('price', 0) < 1000]
        elif price == '1000_5000':
            display_products = [p for p in display_products if 1000 <= p.get('price', 0) <= 5000]
        elif price == '5000_20000':
            display_products = [p for p in display_products if 5000 < p.get('price', 0) <= 20000]
        elif price == 'over_20000':
            display_products = [p for p in display_products if p.get('price', 0) > 20000]
        elif price == 'over_5000':
            display_products = [p for p in display_products if p.get('price', 0) > 5000]
            
    min_price = args.get('min_price')
    if min_price:
        try:
            m = int(min_price)
            display_products = [p for p in display_products if p.get('price', 0) >= m]
        except ValueError: pass

    if max_price:
        try:
            m = int(max_price)
            display_products = [p for p in display_products if p.get('price', 0) <= m]
        except ValueError: pass
            
    if rating:
        try:
            r = float(rating)
            display_products = [p for p in display_products if p.get('rating', 0) >= r]
        except ValueError: pass
        
    if popularity:
        if popularity == 'bestsellers':
            display_products = [p for p in display_products if p.get('popularity') or p.get('price', 0) > 20000]
        elif popularity == 'trending':
            history_ids = extract_user_history_ids()
            recs = get_user_recommendations(history_ids, mock_products, num_recommendations=20)
            rec_ids = {p['id'] for p in recs}
            display_products = [p for p in display_products if p.get('id') in rec_ids]

    if sort:
        if sort == 'low_to_high':
            display_products.sort(key=lambda x: x.get('price', 0))
        elif sort == 'high_to_low':
            display_products.sort(key=lambda x: x.get('price', 0), reverse=True)
        elif sort == 'rating':
            display_products.sort(key=lambda x: x.get('rating', 0.0), reverse=True)
        elif sort == 'popularity':
            display_products.sort(key=lambda x: x.get('popularity', False), reverse=True)
        elif sort == 'newest':
            display_products.sort(key=lambda x: x.get('id', 0), reverse=True)
        elif sort == 'recommended':
            history_ids = extract_user_history_ids()
            from model import get_user_recommendations
            recs = get_user_recommendations(history_ids, load_catalog(), num_recommendations=100)
            rec_order = {r['id']: idx for idx, r in enumerate(recs)}
            display_products.sort(key=lambda x: rec_order.get(x.get('id'), 9999))

    # Track search queries in search history
    search = args.get('search')
    if search:
        search_history = session.get('search_history', [])
        if search not in search_history:
            search_history.insert(0, search)
            session['search_history'] = search_history[:5]

    try: from db import get_db_connection
    except ImportError: from backend.db import get_db_connection
    conn = get_db_connection()
    for p in display_products:
        normalize_product_image(p)
        p_id = p.get('id')
        price_rows = conn.execute("SELECT * FROM product_prices WHERE product_id = ?", (p_id,)).fetchall()
        if not price_rows:
            import random
            random.seed(p_id)
            for m in ['Amazon', 'Flipkart', 'Myntra', 'AJIO']:
                price = int(p.get('price', 0) * random.uniform(0.85, 1.15))
                discount = random.randint(5, 40)
                conn.execute('''
                    INSERT OR REPLACE INTO product_prices (product_id, marketplace_name, price, discount_percentage)
                    VALUES (?, ?, ?, ?)
                ''', (p_id, m, price, discount))
            conn.commit()
            price_rows = conn.execute("SELECT * FROM product_prices WHERE product_id = ?", (p_id,)).fetchall()
            
        competitor_prices = {}
        for r in price_rows:
            competitor_prices[r['marketplace_name']] = r['price']
            
        p['competitor_prices'] = competitor_prices
        if competitor_prices:
            p['cheapest_platform'] = min(competitor_prices, key=competitor_prices.get)
        else:
            p['cheapest_platform'] = 'Amazon'
    conn.close()

    return display_products, category, cat_min, cat_max

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.get_json() or {}
    msg = data.get('message', '')
    try:
        response = get_chatbot_response(msg)
    except Exception as e:
        app.logger.error(f'Chatbot error: {e}')
        response = {'reply': "Sorry, I'm having trouble connecting right now.", 'recommendations': []}
    return jsonify(response)

@app.route("/")
def index():
    # Allow anonymous users to view the storefront on the root route.
    # Previously this redirected to login which hid products for unauthenticated visitors.
    products, active_category, cat_min, cat_max = get_filtered_products(request.args)
    show_modal = False
    if session.get('show_new_user_quiz'):
        show_modal = True
        session.pop('show_new_user_quiz', None)
    return render_template("index.html", products=products, active_category=active_category, cat_min=cat_min, cat_max=cat_max, show_new_user_modal=show_modal)

@app.route("/dashboard")
def dashboard():
    history_ids = extract_user_history_ids()
    recommended_products = get_user_recommendations(history_ids, mock_products, num_recommendations=6)
    return render_template("dashboard.html", recommendations=recommended_products)

@app.route('/quiz', methods=['GET'])
def quiz():
    return render_template('quiz.html', active_category=None)

def get_styled_outfits(products, vibe=None):
    """Returns dynamic outfit arrays by extracting items from the database based on vibe."""
    try:
        from db import get_db_connection
    except ImportError:
        from backend.db import get_db_connection
        
    conn = get_db_connection()
    c = conn.cursor()
    
    women_outfit = []
    men_outfit = []
    
    if vibe:
        # Perfect outfit curation based on vibe
        if vibe == 'cool':
            w_items = c.execute("SELECT * FROM products WHERE category='Women Fashion' AND (name LIKE '%Crop%' OR name LIKE '%Jacket%' OR name LIKE '%Hoodie%' OR name LIKE '%Streetwear%') ORDER BY RANDOM() LIMIT 1").fetchall()
            if not w_items: w_items = c.execute("SELECT * FROM products WHERE category='Women Fashion' ORDER BY RANDOM() LIMIT 1").fetchall()
            w_shoes = c.execute("SELECT * FROM products WHERE category='Shoes' AND (name LIKE '%Sneaker%' OR name LIKE '%Nike%' OR name LIKE '%Adidas%' OR name LIKE '%Puma%') ORDER BY RANDOM() LIMIT 1").fetchall()
            if not w_shoes: w_shoes = c.execute("SELECT * FROM products WHERE category='Shoes' ORDER BY RANDOM() LIMIT 1").fetchall()
            w_acc = c.execute("SELECT * FROM products WHERE (category='Electronics' AND (name LIKE '%Headphones%' OR name LIKE '%Earbuds%' OR name LIKE '%AirPods%' OR name LIKE '%Watch%')) OR (category='Beauty' AND name LIKE '%Perfume%') ORDER BY RANDOM() LIMIT 1").fetchall()
            if not w_acc: w_acc = c.execute("SELECT * FROM products WHERE category='Beauty' OR category='Electronics' ORDER BY RANDOM() LIMIT 1").fetchall()
            
            m_items = c.execute("SELECT * FROM products WHERE category='Men Fashion' AND (name LIKE '%Denim%' OR name LIKE '%Hoodie%' OR name LIKE '%Jacket%') ORDER BY RANDOM() LIMIT 1").fetchall()
            if not m_items: m_items = c.execute("SELECT * FROM products WHERE category='Men Fashion' ORDER BY RANDOM() LIMIT 1").fetchall()
            m_shoes = c.execute("SELECT * FROM products WHERE category='Shoes' AND (name LIKE '%Sneaker%' OR name LIKE '%Nike%' OR name LIKE '%Adidas%' OR name LIKE '%Puma%') ORDER BY RANDOM() LIMIT 1").fetchall()
            if not m_shoes: m_shoes = c.execute("SELECT * FROM products WHERE category='Shoes' ORDER BY RANDOM() LIMIT 1").fetchall()
            m_acc = c.execute("SELECT * FROM products WHERE category='Electronics' AND (name LIKE '%Headphones%' OR name LIKE '%Earbuds%' OR name LIKE '%AirPods%' OR name LIKE '%Watch%' OR name LIKE '%Speaker%') ORDER BY RANDOM() LIMIT 1").fetchall()
            if not m_acc: m_acc = c.execute("SELECT * FROM products WHERE category='Electronics' ORDER BY RANDOM() LIMIT 1").fetchall()
            
        elif vibe == 'professional':
            w_items = c.execute("SELECT * FROM products WHERE category='Women Fashion' AND (name LIKE '%Blazer%' OR name LIKE '%Shirt%' OR name LIKE '%Dress%' OR name LIKE '%Formal%') ORDER BY RANDOM() LIMIT 1").fetchall()
            if not w_items: w_items = c.execute("SELECT * FROM products WHERE category='Women Fashion' ORDER BY RANDOM() LIMIT 1").fetchall()
            w_shoes = c.execute("SELECT * FROM products WHERE category='Shoes' AND (name LIKE '%Oxford%' OR name LIKE '%Classic%' OR name LIKE '%Walk%') ORDER BY RANDOM() LIMIT 1").fetchall()
            if not w_shoes: w_shoes = c.execute("SELECT * FROM products WHERE category='Shoes' ORDER BY RANDOM() LIMIT 1").fetchall()
            w_acc = c.execute("SELECT * FROM products WHERE (category='Books' AND (name LIKE '%Steve Jobs%' OR name LIKE '%Win Friends%' OR name LIKE '%Habit%' OR name LIKE '%Great%' OR name LIKE '%Zero to One%')) OR (category='Electronics' AND (name LIKE '%Laptop%' OR name LIKE '%Notebook%' OR name LIKE '%Tablet%' OR name LIKE '%iPad%')) ORDER BY RANDOM() LIMIT 1").fetchall()
            if not w_acc: w_acc = c.execute("SELECT * FROM products WHERE category='Books' OR category='Electronics' ORDER BY RANDOM() LIMIT 1").fetchall()
            
            # Men's pro look is hardcoded to the injected lookbook
            m_items = c.execute("SELECT * FROM products WHERE id IN (9004)").fetchall()
            m_acc = c.execute("SELECT * FROM products WHERE id IN (9005)").fetchall()
            m_shoes = c.execute("SELECT * FROM products WHERE id IN (9006)").fetchall()
            
        elif vibe == 'party':
            # Women's party look is hardcoded
            w_items = c.execute("SELECT * FROM products WHERE id IN (9001)").fetchall()
            w_acc = c.execute("SELECT * FROM products WHERE id IN (9002)").fetchall()
            w_shoes = c.execute("SELECT * FROM products WHERE id IN (9003)").fetchall()
            
            m_items = c.execute("SELECT * FROM products WHERE category='Men Fashion' AND (name LIKE '%Shirt%' OR name LIKE '%Jacket%' OR name LIKE '%Polo%') ORDER BY RANDOM() LIMIT 1").fetchall()
            if not m_items: m_items = c.execute("SELECT * FROM products WHERE category='Men Fashion' ORDER BY RANDOM() LIMIT 1").fetchall()
            m_shoes = c.execute("SELECT * FROM products WHERE category='Shoes' AND (name LIKE '%Sneaker%' OR name LIKE '%Adidas%' OR name LIKE '%Nike%' OR name LIKE '%Puma%') ORDER BY RANDOM() LIMIT 1").fetchall()
            if not m_shoes: m_shoes = c.execute("SELECT * FROM products WHERE category='Shoes' ORDER BY RANDOM() LIMIT 1").fetchall()
            m_acc = c.execute("SELECT * FROM products WHERE (category='Electronics' AND (name LIKE '%Watch%' OR name LIKE '%Speaker%')) OR (category='Beauty' AND name LIKE '%Perfume%') ORDER BY RANDOM() LIMIT 1").fetchall()
            if not m_acc: m_acc = c.execute("SELECT * FROM products WHERE name LIKE '%Watch%' ORDER BY RANDOM() LIMIT 1").fetchall()
            
        elif vibe == 'comfort':
            # Women's comfort look is hardcoded
            w_items = c.execute("SELECT * FROM products WHERE id IN (9007)").fetchall()
            w_acc = c.execute("SELECT * FROM products WHERE category='Beauty' AND (name LIKE '%Moisture%' OR name LIKE '%Serum%' OR name LIKE '%Perfume%') ORDER BY RANDOM() LIMIT 1").fetchall()
            w_shoes = c.execute("SELECT * FROM products WHERE category='Shoes' AND (name LIKE '%Sneaker%' OR name LIKE '%Running%' OR name LIKE '%Walk%') ORDER BY RANDOM() LIMIT 1").fetchall()
            if not w_shoes: w_shoes = c.execute("SELECT * FROM products WHERE category='Shoes' ORDER BY RANDOM() LIMIT 1").fetchall()
            
            m_items = c.execute("SELECT * FROM products WHERE category='Men Fashion' AND (name LIKE '%T-Shirt%' OR name LIKE '%Sweat%' OR name LIKE '%Hoodie%' OR name LIKE '%Jogger%') ORDER BY RANDOM() LIMIT 1").fetchall()
            if not m_items: m_items = c.execute("SELECT * FROM products WHERE category='Men Fashion' ORDER BY RANDOM() LIMIT 1").fetchall()
            m_shoes = c.execute("SELECT * FROM products WHERE category='Shoes' AND (name LIKE '%Sneaker%' OR name LIKE '%Running%' OR name LIKE '%Walk%') ORDER BY RANDOM() LIMIT 1").fetchall()
            if not m_shoes: m_shoes = c.execute("SELECT * FROM products WHERE category='Shoes' ORDER BY RANDOM() LIMIT 1").fetchall()
            m_acc = []
            
        else:
            w_items = c.execute("SELECT * FROM products WHERE category='Women Fashion' ORDER BY RANDOM() LIMIT 1").fetchall()
            w_acc = c.execute("SELECT * FROM products WHERE category='Beauty' ORDER BY RANDOM() LIMIT 1").fetchall()
            w_shoes = c.execute("SELECT * FROM products WHERE category='Shoes' ORDER BY RANDOM() LIMIT 1").fetchall()
            m_items = c.execute("SELECT * FROM products WHERE category='Men Fashion' ORDER BY RANDOM() LIMIT 1").fetchall()
            m_acc = c.execute("SELECT * FROM products WHERE category='Electronics' ORDER BY RANDOM() LIMIT 1").fetchall()
            m_shoes = c.execute("SELECT * FROM products WHERE category='Shoes' ORDER BY RANDOM() LIMIT 1").fetchall()

        if w_items and w_shoes: 
            women_outfit = [dict(w_items[0]), dict(w_shoes[0])]
            if w_acc: women_outfit.insert(1, dict(w_acc[0]))
        
        if m_items and m_shoes: 
            men_outfit = [dict(m_items[0]), dict(m_shoes[0])]
            if m_acc: men_outfit.insert(1, dict(m_acc[0]))

    else:
        # Fallback to the original logic for quiz_results where vibe is None
        w_f = next((p for p in products if p.get('category') == 'Women Fashion'), None)
        w_b = next((p for p in products if p.get('category') == 'Beauty'), None)
        w_s = next((p for p in products if p.get('category') == 'Shoes'), None)
        if w_f and w_s:
            women_outfit = [w_f, w_b, w_s] if w_b else [w_f, w_s]
            
        m_f = next((p for p in products if p.get('category') == 'Men Fashion'), None)
        m_s = next((p for p in products if p.get('category') == 'Shoes' and p != w_s), None)
        if not m_s:
            m_s = next((p for p in products if p.get('category') == 'Shoes'), None)
            
        if m_f and m_s:
            men_outfit = [m_f, m_s]
            
    conn.close()
    return women_outfit, men_outfit

@app.route('/quiz/results', methods=['POST', 'GET'])
def quiz_results():
    if request.method == 'POST':
        category = request.form.get('category')
        budget = request.form.get('budget')
        purpose = request.form.get('purpose')
        experience = request.form.get('experience')
        priority = request.form.get('priority')
    else:
        return redirect(url_for('quiz'))
        
    try:
        from db import get_db_connection
    except ImportError:
        from backend.db import get_db_connection
        
    conn = get_db_connection()
    c = conn.cursor()
    
    # Base query for category and budget
    query = "SELECT * FROM products WHERE 1=1"
    params = []
    
    # 1. Category logic
    if category == 'Fashion':
        query += " AND category IN ('Men Fashion', 'Women Fashion', 'Kidsware', 'Shoes')"
    elif category == 'Other':
        query += " AND category IN ('Toys', 'Home Appliances')"
    elif category:
        query += " AND category = ?"
        params.append(category)
        
    # 2. Budget logic
    if budget == 'under_500':
        query += " AND price < 500"
    elif budget == '500_2000':
        query += " AND price >= 500 AND price <= 2000"
    elif budget == '2000_10000':
        query += " AND price > 2000 AND price <= 10000"
    elif budget == 'above_10000':
        query += " AND price > 10000"
        
    # 3. Priority / Sorting logic
    order_part = ""
    if priority == 'Price':
        order_part = " ORDER BY price ASC"
    elif priority == 'Quality':
        order_part = " ORDER BY rating DESC"
    elif priority == 'Brand':
        order_part = " ORDER BY popularity DESC, rating DESC"
    elif priority == 'Trends':
        order_part = " ORDER BY popularity DESC"
    else:
        order_part = " ORDER BY rating DESC"

    # Strict query with all filters
    strict_query = query
    if purpose == 'Daily':
        strict_query += " AND (rating >= 3.5 OR popularity = 1)"
    elif purpose == 'Gift':
        strict_query += " AND rating >= 4.0"
        
    if experience == 'Expert':
        strict_query += " AND rating >= 4.5"
    elif experience == 'Beginner':
        strict_query += " AND popularity = 1"

    products_raw = c.execute(strict_query + order_part + " LIMIT 20", params).fetchall()
    msg = "Here are your perfect matches!"
    
    if len(products_raw) == 0:
        # Fallback 1: Drop purpose and experience
        products_raw = c.execute(query + order_part + " LIMIT 20", params).fetchall()
        msg = "We couldn't perfectly match your purpose, but here are some options in your budget!"
        
    if len(products_raw) == 0:
        # Fallback 2: Drop budget
        base_cat_query = "SELECT * FROM products WHERE 1=1"
        base_params = []
        if category == 'Fashion':
            base_cat_query += " AND category IN ('Men Fashion', 'Women Fashion', 'Kidsware', 'Shoes')"
        elif category == 'Other':
            base_cat_query += " AND category IN ('Toys', 'Home Appliances')"
        elif category:
            base_cat_query += " AND category = ?"
            base_params.append(category)
        
        products_raw = c.execute(base_cat_query + order_part + " LIMIT 20", base_params).fetchall()
        msg = "We couldn't find items in that budget, but here are related top items!"
        
    if len(products_raw) == 0:
        # Fallback 3: Drop everything
        products_raw = c.execute("SELECT * FROM products" + order_part + " LIMIT 20").fetchall()
        msg = "Here are some top items across the store!"
        
    conn.close()
    
    products = [dict(p) for p in products_raw]
    
    women_outfit, men_outfit = get_styled_outfits(products, None)            
    return render_template('quiz_results.html', products=products, message=msg, active_category=category, women_outfit=women_outfit, men_outfit=men_outfit)

@app.route('/mood')
def mood_selector():
    return render_template('mood.html')

@app.route('/mood/<vibe>')
def mood_results(vibe):
    try:
        from db import get_db_connection
    except ImportError:
        from backend.db import get_db_connection
        
    conn = get_db_connection()
    c = conn.cursor()
    query = "SELECT * FROM products WHERE category NOT IN ('Kidsware', 'Toys')"
    
    if vibe == 'cool':
        # Cool vibe: Tech-savvy, trendy, Gen-Z feel
        query += """ AND (
            (category = 'Electronics' AND (name LIKE '%Headphones%' OR name LIKE '%Earbuds%' OR name LIKE '%AirPods%' OR name LIKE '%Watch%' OR name LIKE '%LED%' OR name LIKE '%Speaker%')) OR
            (category = 'Books' AND (name LIKE '%Atomic Habits%' OR name LIKE '%Habit%' OR name LIKE '%Rich Dad%' OR name LIKE '%Win Friends%' OR name LIKE '%Steve Jobs%' OR name LIKE '%Zero to One%' OR name LIKE '%Lean Startup%')) OR
            (category = 'Home Appliances' AND (name LIKE '%Fridge%' OR name LIKE '%Refrigerator%' OR name LIKE '%Coffee%')) OR
            (category = 'Beauty' AND (name LIKE '%Serum%' OR name LIKE '%Moisture%' OR name LIKE '%Perfume%')) OR
            (category = 'Women Fashion' AND (name LIKE '%Crop%' OR name LIKE '%Hoodie%' OR name LIKE '%Streetwear%')) OR
            (category = 'Men Fashion' AND (name LIKE '%T-Shirt%' OR name LIKE '%Denim%' OR name LIKE '%Jacket%')) OR
            (category = 'Shoes' AND (name LIKE '%Sneaker%' OR name LIKE '%Nike%' OR name LIKE '%Adidas%' OR name LIKE '%Puma%'))
        ) ORDER BY RANDOM() LIMIT 15"""
        msg = "😎 Cool Vibe Activated. Check out these fresh styles!"
    elif vibe == 'professional':
        # Always fetch core professional items first (suit, briefcase, shoes, formal shirt, trousers, blazer)
        core_raw = c.execute("SELECT * FROM products WHERE id IN (9004, 9005, 9006, 145, 63, 9015)").fetchall()
        core_ids = [p['id'] for p in core_raw]
        
        # Fetch other professional items randomly
        other_raw = c.execute(f"""SELECT * FROM products WHERE id NOT IN ({','.join(map(str, core_ids))}) AND (
            (category = 'Electronics' AND (name LIKE '%Laptop%' OR name LIKE '%Notebook%' OR name LIKE '%Tablet%' OR name LIKE '%iPad%' OR name LIKE '%MacBook%' OR name LIKE '%Monitor%' OR name LIKE '%Mouse%' OR name LIKE '%Keyboard%')) OR
            (category = 'Books' AND (name LIKE '%Steve Jobs%' OR name LIKE '%Thinking, Fast and Slow%' OR name LIKE '%Win Friends%' OR name LIKE '%Habit%' OR name LIKE '%Great%' OR name LIKE '%Zero to One%' OR name LIKE '%Lean Startup%' OR name LIKE '%Think and Grow Rich%')) OR
            (category = 'Men Fashion' AND (name LIKE '%Formal%' OR name LIKE '%Shirt%' OR name LIKE '%Trouser%' OR name LIKE '%Blazer%' OR name LIKE '%Suit%' OR name LIKE '%Briefcase%' OR name LIKE '%Chino%')) OR
            (category = 'Women Fashion' AND (name LIKE '%Blazer%' OR name LIKE '%Shirt%' OR name LIKE '%Formal%' OR name LIKE '%Suit%')) OR
            (category = 'Shoes' AND (name LIKE '%Oxford%' OR name LIKE '%Classic%' OR name LIKE '%Formal%' OR name LIKE '%Leather%'))
        ) ORDER BY RANDOM() LIMIT 9""").fetchall()
        
        products_raw = core_raw + other_raw
        msg = "💼 Professional Edge"
    elif vibe == 'party':
        query += """ AND (
            (category = 'Beauty' AND (name LIKE '%Lipstick%' OR name LIKE '%Palette%' OR name LIKE '%Gloss%' OR name LIKE '%Mascara%' OR name LIKE '%Kajal%' OR name LIKE '%Perfume%')) OR
            (category = 'Women Fashion' AND (name LIKE '%Dress%' OR name LIKE '%Gown%' OR name LIKE '%Crop%')) OR
            (category = 'Men Fashion' AND (name LIKE '%Shirt%' OR name LIKE '%Polo%' OR name LIKE '%Jeans%' OR name LIKE '%Jacket%')) OR
            (category = 'Shoes' AND (name LIKE '%Heels%' OR name LIKE '%Party%' OR name LIKE '%Sneaker%')) OR
            (category = 'Electronics' AND (name LIKE '%Speaker%' OR name LIKE '%TV%' OR name LIKE '%AirPods%')) OR
            (id IN (9001, 9002, 9003))
        ) ORDER BY RANDOM() LIMIT 15"""
        msg = "🎉 Party Glam"
    elif vibe == 'comfort':
        query += " AND ((category IN ('Women Fashion', 'Men Fashion') AND (name LIKE '%Sweat%' OR name LIKE '%Cozy%' OR name LIKE '%Hoodie%' OR name LIKE '%T-Shirt%' OR name LIKE '%Jogger%')) OR (category = 'Shoes' AND (name LIKE '%Sneaker%' OR name LIKE '%Running%' OR name LIKE '%Walk%')) OR id IN (9007, 9010, 9011, 9012, 9013, 9014, 9017)) ORDER BY RANDOM() LIMIT 15"
        msg = "🧘 Cozy Comfort"
    else:
        query += " LIMIT 15"
        msg = "Here are your products!"
        
    # Execute query only if products_raw hasn't been set by professional logic
    if vibe != 'professional':
        products_raw = c.execute(query).fetchall()
        
    conn.close()
    
    products = [dict(p) for p in products_raw]
    women_outfit, men_outfit = get_styled_outfits(products, vibe)
    
    # ensure lookbooks are removed from standard grid so they don't duplicate (except for professional vibe core items)
    if women_outfit:
        for item in women_outfit:
            if vibe == 'professional' and item['id'] in (9004, 9005, 9006, 9015):
                continue
            products = [p for p in products if p['id'] != item['id']]
    if men_outfit:
        for item in men_outfit:
            if vibe == 'professional' and item['id'] in (9004, 9005, 9006, 9015):
                continue
            products = [p for p in products if p['id'] != item['id']]
            
    return render_template('quiz_results.html', products=products, message=msg, women_outfit=women_outfit, men_outfit=men_outfit)


@app.route("/")
@app.route("/home")
def home():
    user = session.get('user')
    products, active_category, cat_min, cat_max = get_filtered_products(request.args)
    
    try: from db import get_db_connection
    except ImportError: from backend.db import get_db_connection
    conn = get_db_connection()
    
    # Most Viewed
    most_viewed_rows = conn.execute("SELECT id FROM products ORDER BY views DESC LIMIT 8").fetchall()
    most_viewed_ids = [r['id'] for r in most_viewed_rows]
    most_viewed = [p for p in mock_products if p['id'] in most_viewed_ids]
    most_viewed.sort(key=lambda x: most_viewed_ids.index(x['id']) if x['id'] in most_viewed_ids else 999)
    
    # Highest Rated
    highest_rated = sorted(mock_products, key=lambda x: x.get('rating', 0.0), reverse=True)[:8]
    
    # Trending Today
    trending_today = sorted(mock_products, key=lambda x: (x.get('rating', 0.0) * 1.5 + (20 if x.get('popularity') else 0) + (x.get('id') % 5)), reverse=True)[:8]
    
    # Most Recommended
    from model import get_user_recommendations
    history_ids = []
    if user:
        history_ids = extract_user_history_ids()
    most_recommended = get_user_recommendations(history_ids, mock_products, num_recommendations=8)
    
    conn.close()
    
    show_modal = False
    if session.get('show_new_user_quiz'):
        show_modal = True
        session.pop('show_new_user_quiz', None)
        
    return render_template("index.html", 
                           products=products, 
                           active_category=active_category, 
                           cat_min=cat_min, 
                           cat_max=cat_max, 
                           show_new_user_modal=show_modal,
                           trending_today=trending_today,
                           most_recommended=most_recommended,
                           most_viewed=most_viewed,
                           highest_rated=highest_rated)

@app.route("/products")
def products():
    products, active_category, cat_min, cat_max = get_filtered_products(request.args)
    return render_template("products.html", products=products, active_category=active_category, cat_min=cat_min, cat_max=cat_max)

@app.before_request
def refresh_mock_products():
    global mock_products
    mock_products = load_catalog()

@app.context_processor
def utility_processor():
    def get_fallback_image(category):
        cat_map = {
            'Men Fashion': 'clothing.svg',
            'Women Fashion': 'clothing.svg',
            'Kidsware': 'clothing.svg',
            'Toys': 'toys.svg',
            'Electronics': 'electronics.svg',
            'Shoes': 'shoes.svg',
            'Beauty': 'beauty.svg',
            'Books': 'books.svg',
            'Home Appliances': 'home_appliances.svg'
        }
        filename = cat_map.get(category, 'default.svg')
        return f"/static/placeholders/{filename}"
        
    def image_cache_buster(image_path):
        if not image_path:
            return ""
        if image_path.startswith('/static/'):
            clean_path = image_path.split('?')[0]
            local_path = os.path.join(app.static_folder, clean_path[8:])
            if os.path.exists(local_path):
                mtime = int(os.path.getmtime(local_path))
                return f"{clean_path}?v={mtime}"
        return image_path
        
    return dict(get_fallback_image=get_fallback_image, image_cache_buster=image_cache_buster)

def generate_ai_insights(product):
    name = product.get('name', '')
    category = product.get('category', '')
    desc = product.get('description', '')
    
    score = int(product.get('rating', 4.0) * 15 + (15 if product.get('popularity') else 5) + (product.get('id') % 10))
    score = min(max(score, 65), 99)
    
    if category == 'Shoes':
        pros = ["Superior cushioning for all-day comfort", "Durable grip and traction outsole", "Breathable mesh upper keeps feet dry"]
        cons = ["Requires a break-in period for some users", "Slightly narrow around the toes"]
        use_cases = "Running, casual walking, and training sessions."
        audience = "Athletes, runners, and fashion-conscious sneakerheads."
    elif category == 'Electronics':
        pros = ["Crisp high-resolution audio/visual reproduction", "Extremely long-lasting battery life", "Premium materials and build quality"]
        cons = ["Premium price point", "Companion application configuration required"]
        use_cases = "Media consumption, remote work, and travel comfort."
        audience = "Tech enthusiasts, audiophiles, and busy professionals."
    elif category == 'Home Appliances':
        pros = ["Eco-friendly energy-saving design", "Ultra-quiet compressor operation", "Smart companion app integration"]
        cons = ["Requires professional installation", "Larger footprint than expected"]
        use_cases = "Daily home chore automation and food preservation."
        audience = "Families, modern homeowners, and convenience seekers."
    elif category == 'Beauty':
        pros = ["Clean, skin-friendly ingredients", "Long-lasting formula", "Moisturizing and hydrating finish"]
        cons = ["Shade range could be expanded", "Light fragrance may irritate sensitive skin"]
        use_cases = "Daily skincare routines and professional makeup styling."
        audience = "Beauty seekers, skincare enthusiasts, and makeup artists."
    elif category == 'Toys':
        pros = ["Nontoxic child-safe ABS material", "Promotes logical thinking & coordination", "Highly reusable and versatile designs"]
        cons = ["Small parts present choking hazard for toddlers", "Storage box not included"]
        use_cases = "Interactive playtime and early childhood skill development."
        audience = "Kids aged 3+, parents, and educational educators."
    elif category == 'Books':
        pros = ["Compelling, thought-provoking narrative", "Clear writing style with actionable takeaways", "Premium hardcover binding and printing"]
        cons = ["Some chapters can feel a bit repetitive", "Does not include bookmark ribbon"]
        use_cases = "Personal growth, book clubs, and quiet afternoon reading."
        audience = "Avid readers, lifelong learners, and self-help seekers."
    else:
        pros = ["Outstanding performance and durability", "Highly reviewed by global consumers", "Great value for the current price"]
        cons = ["Limited color options available", "Instruction manual could be more detailed"]
        use_cases = "General daily utility and lifestyle enhancement."
        audience = "Smart shoppers looking for quality products."

    return {
        'score': score,
        'pros': pros,
        'cons': cons,
        'use_cases': use_cases,
        'audience': audience
    }

def get_pdp_recommendations(current_product, user_history_ids, recent_views, catalog, user_email=None):
    excluded_ids = set()
    helpful_categories = {}
    helpful_brands = {}
    
    if user_email:
        try: from db import get_db_connection
        except ImportError: from backend.db import get_db_connection
        conn = get_db_connection()
        feedback_rows = conn.execute("SELECT * FROM recommendation_feedback WHERE email = ?", (user_email,)).fetchall()
        conn.close()
        
        for row in feedback_rows:
            p_id = row['product_id']
            fb = row['feedback_type']
            if fb == 'not_relevant':
                excluded_ids.add(p_id)
            elif fb == 'helpful':
                p_item = next((p for p in catalog if p['id'] == p_id), None)
                if p_item:
                    cat = p_item.get('category')
                    if cat: helpful_categories[cat] = helpful_categories.get(cat, 0) + 1
                    words = p_item.get('name', '').split()
                    if words:
                        brand = words[0]
                        helpful_brands[brand] = helpful_brands.get(brand, 0) + 1

    base_candidates = [p for p in catalog if p['id'] != current_product['id'] and p['id'] not in excluded_ids]
    
    def compute_similarity(p):
        score = 0.0
        if p.get('category') == current_product.get('category'):
            score += 5.0
        curr_words = current_product.get('name', '').split()
        p_words = p.get('name', '').split()
        if curr_words and p_words and curr_words[0] == p_words[0]:
            score += 4.0
        curr_price = current_product.get('price', 1)
        p_price = p.get('price', 1)
        price_ratio = min(curr_price, p_price) / max(curr_price, p_price)
        score += price_ratio * 3.0
        
        cat = p.get('category')
        if cat in helpful_categories:
            score += helpful_categories[cat] * 1.5
        if p_words and p_words[0] in helpful_brands:
            score += helpful_brands[p_words[0]] * 1.5
        return score

    explore_similar = sorted(base_candidates, key=compute_similarity, reverse=True)[:6]
    
    def compute_history_similarity(p):
        score = 0.0
        for rv_id in recent_views:
            rv_item = next((x for x in catalog if x['id'] == rv_id), None)
            if rv_item:
                if p.get('category') == rv_item.get('category'):
                    score += 2.0
                rv_words = rv_item.get('name', '').split()
                p_words = p.get('name', '').split()
                if rv_words and p_words and rv_words[0] == p_words[0]:
                    score += 1.5
        if p['id'] in recent_views:
            score -= 10.0
        cat = p.get('category')
        if cat in helpful_categories:
            score += helpful_categories[cat] * 1.5
        return score
        
    you_may_also_like = sorted(base_candidates, key=compute_history_similarity, reverse=True)[:6]
    
    def compute_interaction_similarity(p):
        score = 0.0
        for h_id in user_history_ids:
            h_item = next((x for x in catalog if x['id'] == h_id), None)
            if h_item:
                if p.get('category') == h_item.get('category'):
                    score += 2.0
                h_words = h_item.get('name', '').split()
                p_words = p.get('name', '').split()
                if h_words and p_words and h_words[0] == p_words[0]:
                    score += 1.5
        if p.get('popularity'):
            score += 1.0
        score += p.get('rating', 0.0) * 0.5
        cat = p.get('category')
        if cat in helpful_categories:
            score += helpful_categories[cat] * 1.5
        return score
        
    recommended_for_you = sorted(base_candidates, key=compute_interaction_similarity, reverse=True)[:6]
    
    for p in explore_similar:
        p_words = p.get('name', '').split()
        curr_words = current_product.get('name', '').split()
        if curr_words and p_words and curr_words[0] == p_words[0]:
            p['why_recommended'] = f"Similar brand ({curr_words[0]}) matches your preference."
        elif p.get('category') == current_product.get('category'):
            p['why_recommended'] = f"Matches the '{p.get('category')}' category you are viewing."
        else:
            p['why_recommended'] = "Popular alternative in this price segment."
            
    for p in you_may_also_like:
        if recent_views:
            most_recent_id = recent_views[0]
            most_recent_item = next((x for x in catalog if x['id'] == most_recent_id), None)
            if most_recent_item:
                p['why_recommended'] = f"Similar to products you recently viewed ({most_recent_item.get('category')})."
            else:
                p['why_recommended'] = "Fits your recent browsing style."
        else:
            p['why_recommended'] = "Trending choice tailored to your tastes."
            
    for p in recommended_for_you:
        if p.get('popularity'):
            p['why_recommended'] = "Highly rated by users with similar profiles."
        elif p.get('rating', 0) >= 4.5:
            p['why_recommended'] = "Top tier item matches your budget and rating preferences."
        else:
            p['why_recommended'] = "Recommended based on your shopping interactions."

    return {
        'explore_similar': explore_similar,
        'you_may_also_like': you_may_also_like,
        'recommended_for_you': recommended_for_you
    }

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    product = next((p for p in mock_products if p.get('id') == product_id), None)
    if not product:
        return "Product not found", 404
        
    user = session['user']
    
    # Increment view count in DB
    try: from db import get_db_connection
    except ImportError: from backend.db import get_db_connection
    conn = get_db_connection()
    conn.execute("UPDATE products SET views = views + 1 WHERE id = ?", (product_id,))
    conn.commit()
    
    # Fetch marketplace comparison prices
    price_rows = conn.execute("SELECT * FROM product_prices WHERE product_id = ?", (product_id,)).fetchall()
    
    if not price_rows:
        import random
        random.seed(product_id)
        for m in ['Amazon', 'Flipkart', 'Myntra', 'AJIO']:
            price = int(product.get('price', 0) * random.uniform(0.85, 1.15))
            discount = random.randint(5, 40)
            conn.execute('''
                INSERT OR REPLACE INTO product_prices (product_id, marketplace_name, price, discount_percentage)
                VALUES (?, ?, ?, ?)
            ''', (product_id, m, price, discount))
        conn.commit()
        price_rows = conn.execute("SELECT * FROM product_prices WHERE product_id = ?", (product_id,)).fetchall()
    
    competitor_prices = {}
    for r in price_rows:
        competitor_prices[r['marketplace_name']] = {
            'price': r['price'],
            'discount': r['discount_percentage'],
            'last_updated': r['last_updated']
        }
    
    prices_list = [v['price'] for v in competitor_prices.values()]
    lowest_price = min(prices_list) if prices_list else product.get('price', 0)
    highest_price = max(prices_list) if prices_list else product.get('price', 0)
    
    import random
    random.seed(product_id + 50)
    history_trend = []
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    current_base = product.get('price', 0)
    for m_name in months:
        val = int(current_base * random.uniform(0.9, 1.1))
        history_trend.append({'month': m_name, 'price': val})
    
    cheapest_platform = min(competitor_prices.keys(), key=lambda k: competitor_prices[k]['price']) if competitor_prices else 'SmartShop'
    
    # Track browsing history
    recent_views = session.get('recent_views', [])
    if product_id in recent_views:
        recent_views.remove(product_id)
    recent_views.insert(0, product_id)
    session['recent_views'] = recent_views[:10]
    
    click_history = session.get('click_history', [])
    if product_id in click_history:
        click_history.remove(product_id)
    click_history.insert(0, product_id)
    session['click_history'] = click_history[:10]
    
    history_ids = extract_user_history_ids()
    ai_insights = generate_ai_insights(product)
    recs = get_pdp_recommendations(product, history_ids, recent_views, mock_products, user)
    
    reviews = [
        {"user": "Alex", "rating": 5, "comment": "Absolutely love this! The quality is amazing.", "date": "10 Oct 2023"},
        {"user": "Priya", "rating": 4, "comment": "Very good, but shipping took a bit long.", "date": "15 Sep 2023"},
        {"user": "John", "rating": 5, "comment": "Exceeded my expectations. Great value for the price.", "date": "22 Aug 2023"}
    ]
    
    brand_name = "Premium Brand"
    words = product.get('name', '').split()
    if words:
        brand_name = words[0]
        
    active_category = product.get('category')
    
    # Fetch lists of user's custom collections to show in the PDP wishlist dropdown
    col_rows = conn.execute("SELECT DISTINCT collection_name FROM saved_items WHERE email = ?", (user,)).fetchall()
    collections = [r['collection_name'] for r in col_rows]
    if 'Favorites' not in collections:
        collections.append('Favorites')
        
    conn.close()
    
    return render_template('product_detail.html', 
                           product=product, 
                           reviews=reviews, 
                           brand_name=brand_name, 
                           active_category=active_category, 
                           competitor_prices=competitor_prices, 
                           cheapest_platform=cheapest_platform,
                           ai_insights=ai_insights,
                           lowest_price=lowest_price,
                           highest_price=highest_price,
                           history_trend=history_trend,
                           explore_similar=recs['explore_similar'],
                           you_may_also_like=recs['you_may_also_like'],
                           recommended_for_you=recs['recommended_for_you'],
                           collections=collections)



@app.route("/cart")
def cart():
    return redirect(url_for('saved'))


@app.route('/api/cart/delete', methods=['POST'])
@app.route('/api/cart/save', methods=['POST'])
def deprecated_cart_api():
    return jsonify({'success': True})


@app.route('/api/saved/add', methods=['POST'])
def api_saved_add():
    data = request.get_json() or {}
    try: product_id = int(data.get('product_id'))
    except Exception: return jsonify({'error': 'invalid product id'}), 400

    user = session.get('user')
    if not user: return jsonify({'error': 'login_required'}), 401
    
    collection_name = data.get('collection', 'Favorites')
    if not collection_name or not collection_name.strip():
        collection_name = 'Favorites'
    collection_name = collection_name.strip()

    try: from db import get_db_connection
    except ImportError: from backend.db import get_db_connection
    conn = get_db_connection()
    conn.execute('''
        INSERT OR REPLACE INTO saved_items (email, product_id, collection_name)
        VALUES (?, ?, ?)
    ''', (user, product_id, collection_name))
    conn.commit()
    s = conn.execute("SELECT COUNT(*) FROM saved_items WHERE email = ?", (user,)).fetchone()[0] or 0
    conn.close()

    return jsonify({'success': True, 'saved_count': s})


@app.route('/saved')
def saved():
    user = session.get('user')
    if not user: return redirect(url_for('login'))
    
    try: from db import get_db_connection
    except ImportError: from backend.db import get_db_connection
    conn = get_db_connection()
    rows = conn.execute("SELECT product_id, collection_name FROM saved_items WHERE email = ?", (user,)).fetchall()
    
    saved_items = []
    collections = {}
    for r in rows:
        product = next((p for p in mock_products if p.get('id') == r['product_id']), None)
        if product:
            p_copy = dict(product)
            p_copy['collection_name'] = r['collection_name'] or 'Favorites'
            saved_items.append(p_copy)
            col_name = r['collection_name'] or 'Favorites'
            if col_name not in collections:
                collections[col_name] = []
            collections[col_name].append(p_copy)
            
    conn.close()
    return render_template('saved.html', items=saved_items, collections=collections)


@app.route('/api/saved/delete', methods=['POST'])
def api_saved_delete():
    data = request.get_json() or {}
    try: product_id = int(data.get('product_id'))
    except Exception: return jsonify({'error': 'invalid product id'}), 400

    user = session.get('user')
    if not user: return jsonify({'error': 'login_required'}), 401

    try: from db import get_db_connection
    except ImportError: from backend.db import get_db_connection
    conn = get_db_connection()
    conn.execute("DELETE FROM saved_items WHERE email = ? AND product_id = ?", (user, product_id))
    conn.commit()
    s = conn.execute("SELECT COUNT(*) FROM saved_items WHERE email = ?", (user,)).fetchone()[0] or 0
    conn.close()

    return jsonify({'success': True, 'saved_count': s})


@app.route('/api/saved/count')
def api_saved_count():
    user = session.get('user')
    if not user: return jsonify({'saved_count': 0})

    try: from db import get_db_connection
    except ImportError: from backend.db import get_db_connection
    conn = get_db_connection()
    s = conn.execute("SELECT COUNT(*) FROM saved_items WHERE email = ?", (user,)).fetchone()[0] or 0
    conn.close()

    return jsonify({'saved_count': s})


@app.route('/api/recommendations/feedback', methods=['POST'])
def api_recommendation_feedback():
    user = session.get('user')
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json() or {}
    product_id = data.get('product_id')
    feedback_type = data.get('feedback_type')
    if not product_id or not feedback_type:
        return jsonify({'error': 'Missing params'}), 400
        
    try: from db import get_db_connection
    except ImportError: from backend.db import get_db_connection
    conn = get_db_connection()
    conn.execute('''
        INSERT OR REPLACE INTO recommendation_feedback (email, product_id, feedback_type)
        VALUES (?, ?, ?)
    ''', (user, product_id, feedback_type))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/save', methods=['POST'])
def admin_save_product():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))
        
    product_id = request.form.get('id')
    name = request.form.get('name')
    price = request.form.get('price')
    category = request.form.get('category')
    description = request.form.get('description')
    rating = request.form.get('rating', '4.0')
    popularity = 'popularity' in request.form
    
    if not product_id or not name or not price or not category:
        return "Missing fields", 400
        
    try:
        price_val = float(price)
        rating_val = float(rating)
        prod_id_val = int(product_id)
    except ValueError:
        return "Invalid numeric inputs", 400
        
    image_file = request.files.get('image_file')
    image_url = request.form.get('image_url')
    
    import time
    final_image = image_url
    if image_file and image_file.filename:
        filename = f"uploaded_{prod_id_val}_{int(time.time())}.png"
        file_path = os.path.join(app.static_folder, filename)
        image_file.save(file_path)
        final_image = f"/static/{filename}"
        
    try: from db import get_db_connection
    except ImportError: from backend.db import get_db_connection
    conn = get_db_connection()
    
    exists = conn.execute("SELECT 1 FROM products WHERE id = ?", (prod_id_val,)).fetchone()
    if exists:
        if final_image:
            conn.execute('''
                UPDATE products 
                SET name = ?, price = ?, category = ?, description = ?, rating = ?, popularity = ?, image = ?
                WHERE id = ?
            ''', (name, price_val, category, description, rating_val, popularity, final_image, prod_id_val))
        else:
            conn.execute('''
                UPDATE products 
                SET name = ?, price = ?, category = ?, description = ?, rating = ?, popularity = ?
                WHERE id = ?
            ''', (name, price_val, category, description, rating_val, popularity, prod_id_val))
    else:
        if not final_image:
            final_image = "/static/placeholders/default.svg"
        conn.execute('''
            INSERT INTO products (id, name, price, category, description, rating, popularity, image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (prod_id_val, name, price_val, category, description, rating_val, popularity, final_image))
        
    conn.commit()
    conn.close()
    
    global mock_products
    mock_products = load_catalog()
    
    return redirect(url_for('admin'))


@app.route('/api/saved/move', methods=['POST'])
def api_saved_move():
    data = request.get_json() or {}
    try: product_id = int(data.get('product_id'))
    except Exception: return jsonify({'error': 'invalid product id'}), 400

    user = session.get('user')
    if not user: return jsonify({'error': 'login_required'}), 401

    try: from db import get_db_connection
    except ImportError: from backend.db import get_db_connection
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM saved_items WHERE email = ? AND product_id = ?", (user, product_id))
    if c.rowcount > 0:
        # It was actually in saved_items, move back to cart
        c.execute("SELECT quantity FROM carts WHERE email = ? AND product_id = ?", (user, product_id))
        row = c.fetchone()
        if row: c.execute("UPDATE carts SET quantity = quantity + 1 WHERE email = ? AND product_id = ?", (user, product_id))
        else: c.execute("INSERT INTO carts (email, product_id, quantity) VALUES (?, ?, 1)", (user, product_id))
    conn.commit()
    r = conn.execute("SELECT SUM(quantity) FROM carts WHERE email = ?", (user,)).fetchone()[0] or 0
    s = conn.execute("SELECT COUNT(*) FROM saved_items WHERE email = ?", (user,)).fetchone()[0] or 0
    conn.close()

    return jsonify({'success': True, 'total_items': r, 'saved_count': s})


@app.route('/checkout', methods=['GET', 'POST'])
@app.route('/order/confirmation')
@app.route('/checkout/confirm', methods=['GET', 'POST'])
@app.route('/api/quick_upi', methods=['POST'])
def deprecated_checkout_redirect():
    return redirect(url_for('dashboard'))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        # 1. Validation
        if not identifier:
            return render_template("login.html", error="Email or mobile number is required.")
        if not password:
            return render_template("login.html", error="Password is required.")
            
        if not (is_valid_email(identifier) or is_valid_mobile(identifier)):
            return render_template("login.html", error="Please enter a valid email address or 10-digit mobile number.")
            
        # 2. Database verification (User Existence Check)
        try:
            from db import get_db_connection
        except ImportError:
            from backend.db import get_db_connection
            
        conn = get_db_connection()
        c = conn.cursor()
        user_row = c.execute("SELECT * FROM users WHERE email = ?", (identifier,)).fetchone()
        conn.close()
        
        if not user_row:
            # Prevent invalid login attempt, trigger the popup
            return render_template("login.html", show_not_found_modal=True, entered_identifier=identifier)
            
        # 3. Rate Limiting Check
        ip_addr = request.remote_addr
        is_limited, limit_msg = check_otp_rate_limit(identifier, ip_addr)
        if is_limited:
            return render_template("login.html", error=limit_msg)
            
        # 4. Generate & Send OTP
        otp = str(random.randint(100000, 999999))
        expiry = int(time.time()) + 120  # 2 minutes
        session['pending_otp'] = {
            'code': otp, 
            'recipient': identifier, 
            'expires': expiry, 
            'last_sent': int(time.time()), 
            'resend_count': 0,
            'verify_attempts': 0,
            'is_registration': False
        }
        
        # Store OTP for display when SMTP is not configured (dev/simulated mode)
        smtp_configured = bool(os.environ.get('SMTP_EMAIL') and os.environ.get('SMTP_PASSWORD'))
        if not smtp_configured:
            session['simulated_otp'] = otp
        
        record_otp_request(identifier, ip_addr)
        
        try:
            sent = send_otp_to_recipient(identifier, otp)
            if not sent:
                return render_template("login.html", error="Failed to send OTP. Please try again.")
        except Exception as e:
            app.logger.error('Failed to send OTP: %s', e)
            return render_template("login.html", error="An error occurred while sending the OTP.")
            
        return redirect(url_for('verify_otp'))
        
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop('user', None)
    session.pop('simulated_otp', None)
    return redirect(url_for("home"))


@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    pending = session.get('pending_otp')
    if not pending:
        return redirect(url_for('login'))
    
    simulated_otp = session.get('simulated_otp')
    otp_delivery_status = session.get('otp_delivery_status')
    otp_delivery_error = session.get('otp_delivery_error')
        
    if request.method == 'POST':
        code = request.form.get('otp_code', '').strip()
        
        # 1. Check expiration
        if int(time.time()) > pending.get('expires', 0):
            session.pop('pending_otp', None)
            session.pop('simulated_otp', None)
            return render_template('verify_otp.html', error='OTP expired. Please request a new one.', show_debug=app.debug, pending=None, simulated_otp=None, otp_delivery_status=None, otp_delivery_error=None)
            
        # 2. Check attempts rate limit (brute force protection)
        attempts = pending.get('verify_attempts', 0) + 1
        pending['verify_attempts'] = attempts
        session['pending_otp'] = pending
        
        if attempts > 5:
            session.pop('pending_otp', None)
            session.pop('simulated_otp', None)
            return render_template('verify_otp.html', error='Too many incorrect OTP attempts. Please request a new one.', show_debug=app.debug, pending=None, simulated_otp=None, otp_delivery_status=None, otp_delivery_error=None)
            
        # 3. Verify OTP code
        if code == pending.get('code'):
            recipient = pending.get('recipient')
            is_reg = pending.get('is_registration', False)
            
            try:
                from db import get_db_connection
            except ImportError:
                from backend.db import get_db_connection
                
            conn = get_db_connection()
            
            if is_reg:
                # Registration: insert the new user
                try:
                    conn.execute("INSERT OR IGNORE INTO users (email) VALUES (?)", (recipient,))
                    conn.commit()
                    session['user_name'] = pending.get('reg_name', 'User')
                except Exception as e:
                    print("DB insertion failed during registration:", e)
                    conn.close()
                    return render_template('verify_otp.html', error='Failed to complete registration due to database error.', show_debug=app.debug, pending=pending, simulated_otp=simulated_otp, otp_delivery_status=otp_delivery_status, otp_delivery_error=otp_delivery_error)
                session['show_new_user_quiz'] = True
            else:
                # Login: load profile info (or generate name from identifier)
                if '@' in recipient:
                    session['user_name'] = recipient.split('@')[0]
                else:
                    session['user_name'] = "User " + recipient[-4:]
                    
            conn.close()
            
            # Authenticate user
            session['user'] = recipient
            session.pop('pending_otp', None)
            session.pop('simulated_otp', None)
            return redirect(url_for('index'))
        else:
            attempts_left = 5 - attempts
            return render_template('verify_otp.html', error=f'Invalid OTP. {attempts_left} attempts remaining.', show_debug=app.debug, pending=pending, simulated_otp=simulated_otp, otp_delivery_status=otp_delivery_status, otp_delivery_error=otp_delivery_error)
            
    return render_template('verify_otp.html', show_debug=app.debug, pending=pending, simulated_otp=simulated_otp, otp_delivery_status=otp_delivery_status, otp_delivery_error=otp_delivery_error)


@app.route('/debug/last_otp')
def debug_last_otp():
    # Local dev helper: return last pending OTP from session (only available in debug mode)
    if not app.debug:
        return jsonify({'error': 'debug endpoint disabled'}), 403
    pending = session.get('pending_otp')
    if not pending:
        return jsonify({'error': 'no pending otp'}), 404
    return jsonify({'pending_otp': pending})


@app.route('/debug/set_pending_expiry', methods=['POST'])
def debug_set_pending_expiry():
    # Local dev helper: set pending OTP expiry seconds from now (debug-only)
    if not app.debug:
        return jsonify({'error': 'debug endpoint disabled'}), 403
    pending = session.get('pending_otp')
    if not pending:
        return jsonify({'error': 'no pending otp'}), 404
    try:
        seconds = int(request.args.get('seconds', '0'))
    except Exception:
        seconds = 0
    pending['expires'] = int(time.time()) + seconds
    session['pending_otp'] = pending
    return jsonify({'success': True, 'new_expires': pending['expires']})


def send_otp_to_recipient(identifier, otp):
    if not identifier:
        return False
        
    if '@' in identifier:
        # Email flow
        smtp_email = os.environ.get('SMTP_EMAIL')
        smtp_password = os.environ.get('SMTP_PASSWORD')
        if not smtp_email or not smtp_password:
            session['simulated_otp'] = otp
            session['otp_delivery_status'] = 'not_configured'
            session.pop('otp_delivery_error', None)
            print(f"[SMTP] Credentials not configured. Simulated OTP to Email [{identifier}]: {otp}")
            return True
        try:
            msg = EmailMessage()
            msg['Subject'] = 'Your SmartShop OTP'
            msg['From'] = smtp_email
            msg['To'] = identifier
            msg.set_content(f'Your SmartShop OTP is: {otp}. It will expire in 2 minutes.')

            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.send_message(msg)
            server.quit()

            session.pop('simulated_otp', None)
            session['otp_delivery_status'] = 'sent'
            session.pop('otp_delivery_error', None)
            print(f"[SMTP] OTP sent to {identifier}")
            return True
        except Exception as e:
            session['simulated_otp'] = otp
            session['otp_delivery_status'] = 'failed'
            session['otp_delivery_error'] = str(e)
            print(f"[SMTP] Email error: {e}")
            print(f"[SMTP] Simulated fallback OTP to Email [{identifier}]: {otp}")
            return True
    else:
        # Mobile number flow (Simulated SMS delivery)
        session['simulated_otp'] = otp
        session['otp_delivery_status'] = 'simulated_sms'
        session.pop('otp_delivery_error', None)
        print(f"[SMS] Simulated OTP to {identifier}: {otp}")
        return True


@app.route('/resend_otp', methods=['POST'])
def resend_otp():
    pending = session.get('pending_otp')
    if not pending:
        return jsonify({'error': 'no_pending_otp'}), 400

    recipient = pending.get('recipient')
    ip_addr = request.remote_addr
    
    # 1. Check rate limits
    is_limited, limit_msg = check_otp_rate_limit(recipient, ip_addr)
    if is_limited:
        return jsonify({'error': limit_msg}), 429

    # 2. Cooldown check
    now = int(time.time())
    last_sent = pending.get('last_sent', 0)
    resend_count = pending.get('resend_count', 0)

    COOLDOWN = 30
    MAX_RESENDS = 3

    seconds_since = now - last_sent
    if resend_count >= MAX_RESENDS:
        return jsonify({'error': 'Maximum resend attempts reached for this session. Please login/register again.', 'attempts_left': 0}), 429
    if seconds_since < COOLDOWN:
        return jsonify({'error': f'Please wait {COOLDOWN - seconds_since}s before requesting a new OTP.', 'seconds_left': COOLDOWN - seconds_since, 'attempts_left': MAX_RESENDS - resend_count}), 429

    # Generate new OTP
    new_otp = str(random.randint(100000, 999999))
    pending['code'] = new_otp
    pending['expires'] = now + 120
    pending['last_sent'] = now
    pending['resend_count'] = resend_count + 1
    session['pending_otp'] = pending

    smtp_configured = bool(os.environ.get('SMTP_EMAIL') and os.environ.get('SMTP_PASSWORD'))
    if not smtp_configured:
        session['simulated_otp'] = new_otp

    record_otp_request(recipient, ip_addr)

    try:
        sent = send_otp_to_recipient(recipient, new_otp)
        if not sent:
            return jsonify({'error': 'Failed to send OTP.'}), 500
    except Exception as e:
        app.logger.error('Failed to resend OTP: %s', e)
        return jsonify({'error': 'Error occurred while sending OTP.'}), 500

    return jsonify({'success': True, 'seconds_left': 0, 'attempts_left': MAX_RESENDS - pending['resend_count']})


@app.route('/resend_status')
def resend_status():
    pending = session.get('pending_otp')
    if not pending:
        return jsonify({'has_pending': False})
    now = int(time.time())
    last_sent = pending.get('last_sent', 0)
    resend_count = pending.get('resend_count', 0)
    COOLDOWN = 30
    MAX_RESENDS = 3
    seconds_since = now - last_sent
    seconds_left = COOLDOWN - seconds_since if seconds_since < COOLDOWN else 0
    attempts_left = MAX_RESENDS - resend_count
    return jsonify({'has_pending': True, 'seconds_left': seconds_left if seconds_left>0 else 0, 'attempts_left': attempts_left})

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            name = request.form.get('name', '').strip()
            identifier = request.form.get('email', '').strip()
            password = request.form.get('password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()
            
            if not name:
                return render_template("register.html", error="Name is required.")
            if not identifier:
                return render_template("register.html", error="Mobile number or email is required.")
            if not password:
                return render_template("register.html", error="Password is required.")
            if len(password) < 6:
                return render_template("register.html", error="Password must be at least 6 characters.")
            if password != confirm_password:
                return render_template("register.html", error="Passwords do not match.")
            if not (is_valid_email(identifier) or is_valid_mobile(identifier)):
                return render_template("register.html", error="Please enter a valid email address or 10-digit mobile number.")
                
            from backend.db import get_db_connection
            conn = get_db_connection()
            user_row = conn.execute("SELECT * FROM users WHERE email = ?", (identifier,)).fetchone()
            conn.close()
            if user_row:
                return render_template("register.html", error="An account already exists with this email or mobile number. Please sign in.")
                
            ip_addr = request.remote_addr or "unknown"
            is_limited, limit_msg = check_otp_rate_limit(identifier, ip_addr)
            if is_limited:
                return render_template("register.html", error=limit_msg)
                
            otp = str(random.randint(100000, 999999))
            expiry = int(time.time()) + 120
            
            session['pending_otp'] = {
                'code': otp, 'recipient': identifier, 'expires': expiry,
                'last_sent': int(time.time()), 'resend_count': 0,
                'verify_attempts': 0, 'is_registration': True,
                'reg_name': name
            }
            
            if not bool(os.environ.get('SMTP_EMAIL') and os.environ.get('SMTP_PASSWORD')):
                session['simulated_otp'] = otp
            
            record_otp_request(identifier, ip_addr)
            send_otp_to_recipient(identifier, otp)
            return redirect(url_for('verify_otp'))
            
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            app.logger.error('Register error: %s', tb)
            return f"<h1>Register Error</h1><pre>{tb}</pre>", 500
        
    return render_template("register.html")

# Legacy product_detail route has been merged into line 160

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        # Update editable fields in session
        name = request.form.get('name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        if name:
            session['user_name'] = name
        if phone:
            session['phone'] = phone
        if address:
            session['address'] = address
        # After updating, redirect to GET to display updated info
        return redirect(url_for('profile'))
    return render_template('profile.html')

@app.route("/admin")
def admin():
    return render_template("admin.html", products=mock_products)


@app.route("/orders")
def orders():
    user = session.get('user')
    if not user: return redirect(url_for('login'))
    
    try: from db import get_db_connection
    except ImportError: from backend.db import get_db_connection
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM orders WHERE email = ? ORDER BY created_at DESC", (user,)).fetchall()
    orders = []
    for r in rows:
        orders.append({
            'id': r['id'],
            'total': r['total'],
            'payment_method': r['payment_method'],
            'date': r['created_at'],
            'items': json.loads(r['items_json'])
        })
    conn.close()
    return render_template('orders.html', orders=orders)


@app.route("/membership")
def membership():
    logged_in = 'user' in session
    membership_benefits = [
        "Free delivery on orders over ₹500",
        "Exclusive member deals and coupons",
        "Early access to sales and new products"
    ]
    payment_methods = [
        {"label": "Visa **** 4242", "expiry": "12/24"},
        {"label": "Mastercard **** 1111", "expiry": "11/25"}
    ]
    return render_template('membership.html', benefits=membership_benefits, payment_methods=payment_methods, logged_in=logged_in)


@app.route('/api/cart/add', methods=['POST'])
def api_cart_add():
    data = request.get_json() or {}
    try: product_id = int(data.get('product_id'))
    except Exception: return jsonify({'error': 'invalid product id'}), 400
    qty = int(data.get('quantity', 1)) if data.get('quantity') else 1
    
    user = session.get('user')
    if not user: return jsonify({'error': 'login_required'}), 401

    try: from db import get_db_connection
    except ImportError: from backend.db import get_db_connection
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT quantity FROM carts WHERE email = ? AND product_id = ?", (user, product_id))
    row = c.fetchone()
    if row:
        c.execute("UPDATE carts SET quantity = quantity + ? WHERE email = ? AND product_id = ?", (qty, user, product_id))
    else:
        c.execute("INSERT INTO carts (email, product_id, quantity) VALUES (?, ?, ?)", (user, product_id, qty))
    conn.commit()
    r = conn.execute("SELECT SUM(quantity) FROM carts WHERE email = ?", (user,)).fetchone()[0]
    conn.close()
    return jsonify({'success': True, 'total_items': r or 0})


@app.route('/api/cart/count')
def api_cart_count():
    user = session.get('user')
    if not user:
        return jsonify({'total_items': 0})
    try: from db import get_db_connection
    except ImportError: from backend.db import get_db_connection
    conn = get_db_connection()
    r = conn.execute("SELECT SUM(quantity) FROM carts WHERE email = ?", (user,)).fetchone()[0]
    conn.close()
    return jsonify({'total_items': r or 0})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)


# Hot reload trigger

# Hot reload trigger for people removal
