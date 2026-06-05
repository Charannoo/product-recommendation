import re
from typing import Dict, List

# Simple keyword → category mapping for quick look‑ups
KEYWORD_CATEGORY_MAP: Dict[str, str] = {
    # Specific category names
    "men fashion": "Men Fashion",
    "women fashion": "Women Fashion",
    "home appliances": "Home Appliances",
    "kidsware": "Kidsware",
    "kids wear": "Kidsware",
    "toys": "Toys",
    "toy": "Toys",
    "shoes": "Shoes",
    "shoe": "Shoes",
    "electronics": "Electronics",
    "beauty": "Beauty",
    "books": "Books",
    "book": "Books",
    
    # Synonyms / Subcategories
    "dress": "Women Fashion",
    "gown": "Women Fashion",
    "saree": "Women Fashion",
    "kurti": "Women Fashion",
    "top": "Women Fashion",
    "skirt": "Women Fashion",
    "bag": "Women Fashion",
    "handbag": "Women Fashion",
    "purse": "Women Fashion",
    "lehenga": "Women Fashion",
    "jewelry": "Women Fashion",
    "earrings": "Women Fashion",
    
    "shirt": "Men Fashion",
    "tshirt": "Men Fashion",
    "t-shirt": "Men Fashion",
    "jeans": "Men Fashion",
    "suit": "Men Fashion",
    "blazer": "Men Fashion",
    "trouser": "Men Fashion",
    "trousers": "Men Fashion",
    "kurta": "Men Fashion",
    "coat": "Men Fashion",
    "tie": "Men Fashion",
    "wallet": "Men Fashion",
    "socks": "Men Fashion",
    
    "sneakers": "Shoes",
    "sneaker": "Shoes",
    "heels": "Shoes",
    "flats": "Shoes",
    "boots": "Shoes",
    "sandals": "Shoes",
    "slippers": "Shoes",
    "loafers": "Shoes",
    "footwear": "Shoes",
    
    "blender": "Home Appliances",
    "ac": "Home Appliances",
    "air conditioner": "Home Appliances",
    "refrigerator": "Home Appliances",
    "fridge": "Home Appliances",
    "tv": "Home Appliances",
    "television": "Home Appliances",
    "saucepan": "Home Appliances",
    "cooker": "Home Appliances",
    "kettle": "Home Appliances",
    "oven": "Home Appliances",
    "microwave": "Home Appliances",
    "toaster": "Home Appliances",
    "iron": "Home Appliances",
    "mixer": "Home Appliances",
    
    "headphone": "Electronics",
    "headphones": "Electronics",
    "earbuds": "Electronics",
    "airpods": "Electronics",
    "laptop": "Electronics",
    "phone": "Electronics",
    "smartphone": "Electronics",
    "watch": "Electronics",
    "smartwatch": "Electronics",
    "keyboard": "Electronics",
    "mouse": "Electronics",
    "tablet": "Electronics",
    "ipad": "Electronics",
    "camera": "Electronics",
    
    "cosmetics": "Beauty",
    "makeup": "Beauty",
    "lipstick": "Beauty",
    "mascara": "Beauty",
    "concealer": "Beauty",
    "skincare": "Beauty",
    "perfume": "Beauty",
    "hair dryer": "Beauty",
    "straightener": "Beauty",
    "shampoo": "Beauty",
    "moisturizer": "Beauty",
    
    "novel": "Books",
    "fiction": "Books",
    "biography": "Books",
    "textbook": "Books",
    "comic": "Books",
    
    "drum": "Toys",
    "drums": "Toys",
    "guitar": "Toys",
    "piano": "Toys",
    "flute": "Toys",
    "musical instrument": "Toys",
    "music toy": "Toys",
    "violin": "Toys",
    "doll": "Toys",
    "barbie": "Toys",
    "teddy": "Toys",
    "lego": "Toys",
    "puzzle": "Toys",
    "blocks": "Toys",
    "board game": "Toys",
    "car toy": "Toys",
    "action figure": "Toys"
}

def _load_products() -> List[Dict]:
    """Helper to lazily import and load product catalog."""
    try:
        from .app import load_catalog
    except Exception:
        from app import load_catalog
    return load_catalog()

def is_brand_match(product: dict, brand_query: str) -> bool:
    if not brand_query:
        return False
    b_q = brand_query.lower().strip()
    p_b = product.get('brand', '').lower().strip()
    p_n = product.get('name', '').lower().strip()
    
    # Direct substring checks
    if b_q in p_b or p_b in b_q:
        return True
    if b_q in p_n:
        return True
        
    # Synonyms & mappings
    synonyms = {
        "hm": ["h&m", "h and m"],
        "h&m": ["hm", "h and m"],
        "loreal": ["l'oreal", "l'oréal"],
        "l'oreal": ["loreal", "l'oréal"],
        "l'oréal": ["loreal", "l'oreal"],
        "fenty": ["fenty beauty"],
        "fenty beauty": ["fenty"],
        "huda": ["huda beauty"],
        "huda beauty": ["huda"],
        "estee": ["estee lauder", "estée lauder", "estée"],
        "estee lauder": ["estee", "estée lauder", "estée"],
        "estée lauder": ["estee", "estee lauder", "estée"],
        "estée": ["estee", "estee lauder", "estée lauder"],
        "anastasia": ["anastasia beverly hills"],
        "mac": ["m.a.c", "m.a.c."]
    }
    
    for k, syn_list in synonyms.items():
        if b_q == k or b_q in syn_list:
            if p_b == k or any(s in p_b for s in syn_list) or k in p_n or any(s in p_n for s in syn_list):
                return True
                
    return False

def get_chatbot_response(message: str) -> Dict:
    """Generate a response for the SmartShop chatbot.
    
    The function returns a dict with two keys:
        * ``reply`` – a short text response.
        * ``recommendations`` – a list of up to three product dicts.
    """
    try:
        from flask import session
    except ImportError:
        session = {}

    products = _load_products()
    msg = message.lower()
    words = set(re.findall(r"\w+", msg))
    
    # Known attribute lists to detect even without explicit keywords like "color red"
    known_colors = {"red", "blue", "black", "white", "green", "yellow", "pink", "purple", "grey", "brown"}
    known_brands = {
        "apple", "samsung", "sony", "zara", "nike", "adidas", "red tape", "puma", 
        "skechers", "biba", "asus", "dell", "h&m", "l'oreal", "l'oréal", "loreal", 
        "fenty", "fabindia", "philips", "whirlpool", "lg", "havells", "blue star",
        "mac", "clinique", "forest essentials", "real techniques", "laneige",
        "sol de janeiro", "estée lauder", "estee lauder"
    }
    
    # Check if there is a pending interactive query from the previous turn
    pending_intent = session.get('chatbot_pending_intent') if hasattr(session, 'get') else None
    
    if pending_intent:
        # Check if user wants to change topic by entering a new matched category
        has_new_category = False
        for kw, cat in KEYWORD_CATEGORY_MAP.items():
            if re.search(r'\b' + re.escape(kw) + r'\b', msg):
                has_new_category = True
                break
                
        # Also check if they asked for a fresh greetings
        if words.intersection({"hi", "hii", "hello", "hey", "help"}) or has_new_category:
            if hasattr(session, 'pop'):
                session.pop('chatbot_pending_intent', None)
                session.pop('chatbot_pending_category', None)
                session.pop('chatbot_pending_brand', None)
        else:
            # Handle turn follow-ups based on pending intent
            if pending_intent == 'price_range':
                num_match = re.search(r"(\d+)", msg)
                if num_match:
                    price_limit = int(num_match.group(1))
                    matched_category = session.get('chatbot_pending_category') if hasattr(session, 'get') else None
                    
                    if hasattr(session, 'pop'):
                        session.pop('chatbot_pending_intent', None)
                        session.pop('chatbot_pending_category', None)
                        
                    filtered = products
                    if matched_category:
                        filtered = [p for p in filtered if p.get('category', '').lower() == matched_category.lower()]
                    filtered = [p for p in filtered if p.get('price', 0) <= price_limit]
                    
                    if filtered:
                        filtered.sort(key=lambda p: p.get('rating', 0), reverse=True)
                        cat_str = f"{matched_category.lower()}" if matched_category else "products"
                        return {
                            "reply": f"Here are {cat_str} under ₹{price_limit} matching your request:",
                            "recommendations": filtered[:3]
                        }
                    else:
                        cat_str = f"{matched_category.lower()}" if matched_category else "products"
                        return {
                            "reply": f"I couldn't find any {cat_str} under ₹{price_limit}. Feel free to try a different price range!",
                            "recommendations": []
                        }
                else:
                    matched_category = session.get('chatbot_pending_category') if hasattr(session, 'get') else None
                    cat_str = f"{matched_category.lower()}" if matched_category else "items"
                    return {
                        "reply": f"Please enter your price range as a number (e.g., under 1500 or below 3000) so I can help you filter the {cat_str}!",
                        "recommendations": []
                    }
                    
            elif pending_intent == 'brand':
                detected_brand = None
                for b in known_brands:
                    if re.search(r'\b' + re.escape(b) + r'\b', msg):
                        detected_brand = b
                        break
                if not detected_brand:
                    # Fallback check for any single non-ignored word
                    for w in words:
                        if len(w) > 2 and w not in {"the", "and", "for", "shoes", "dress", "shirts", "brand", "nike", "adidas", "zara"}:
                            detected_brand = w
                            break
                            
                if detected_brand:
                    matched_category = session.get('chatbot_pending_category') if hasattr(session, 'get') else None
                    if hasattr(session, 'pop'):
                        session.pop('chatbot_pending_intent', None)
                        session.pop('chatbot_pending_category', None)
                        
                    filtered = products
                    if matched_category:
                        filtered = [p for p in filtered if p.get('category', '').lower() == matched_category.lower()]
                    filtered = [p for p in filtered if is_brand_match(p, detected_brand)]
                    
                    if filtered:
                        filtered.sort(key=lambda p: p.get('rating', 0), reverse=True)
                        cat_str = f" {matched_category.lower()}" if matched_category else " products"
                        return {
                            "reply": f"Here are{cat_str} from {detected_brand.title()} matching your request:",
                            "recommendations": filtered[:3]
                        }
                    else:
                        cat_str = f" {matched_category.lower()}" if matched_category else " products"
                        return {
                            "reply": f"I couldn't find any{cat_str} from brand {detected_brand.title()}. Feel free to try another brand!",
                            "recommendations": []
                        }
                else:
                    matched_category = session.get('chatbot_pending_category') if hasattr(session, 'get') else None
                    cat_str = f" {matched_category.lower()}" if matched_category else " items"
                    return {
                        "reply": f"Please enter a brand name (e.g., Nike, Adidas, Samsung, Zara, Biba, etc.) so I can filter the{cat_str}!",
                        "recommendations": []
                    }
                    
            elif pending_intent == 'rating':
                num_match = re.search(r"(\d+(?:\.\d+)?)", msg)
                if num_match:
                    rating_limit = float(num_match.group(1))
                    matched_category = session.get('chatbot_pending_category') if hasattr(session, 'get') else None
                    brand_filter = session.get('chatbot_pending_brand') if hasattr(session, 'get') else None
                    
                    if hasattr(session, 'pop'):
                        session.pop('chatbot_pending_intent', None)
                        session.pop('chatbot_pending_category', None)
                        session.pop('chatbot_pending_brand', None)
                        
                    filtered = products
                    if matched_category:
                        filtered = [p for p in filtered if p.get('category', '').lower() == matched_category.lower()]
                    if brand_filter:
                        filtered = [p for p in filtered if is_brand_match(p, brand_filter)]
                    filtered = [p for p in filtered if float(p.get('rating', 0)) >= rating_limit]
                    
                    if filtered:
                        filtered.sort(key=lambda p: p.get('rating', 0), reverse=True)
                        brand_str = f" from {brand_filter.title()}" if brand_filter else ""
                        cat_str = f" {matched_category.lower()}" if matched_category else " products"
                        return {
                            "reply": f"Here are{cat_str}{brand_str} rated {rating_limit} stars and above:",
                            "recommendations": filtered[:3]
                        }
                    else:
                        brand_str = f" from {brand_filter.title()}" if brand_filter else ""
                        cat_str = f" {matched_category.lower()}" if matched_category else " products"
                        return {
                            "reply": f"I couldn't find any{cat_str}{brand_str} rated {rating_limit} stars and above. Let me know if you want to try a different rating!",
                            "recommendations": []
                        }
                else:
                    return {
                        "reply": "Please specify a minimum rating limit as a number (e.g., above 4 or above 4.5)!",
                        "recommendations": []
                    }
                    
            elif pending_intent == 'category':
                matched_category = None
                for kw, cat in KEYWORD_CATEGORY_MAP.items():
                    if re.search(r'\b' + re.escape(kw) + r'\b', msg):
                        matched_category = cat
                        break
                        
                if matched_category:
                    brand_filter = session.get('chatbot_pending_brand') if hasattr(session, 'get') else None
                    if hasattr(session, 'pop'):
                        session.pop('chatbot_pending_intent', None)
                        session.pop('chatbot_pending_brand', None)
                        
                    filtered = products
                    filtered = [p for p in filtered if p.get('category', '').lower() == matched_category.lower()]
                    if brand_filter:
                        filtered = [p for p in filtered if is_brand_match(p, brand_filter)]
                        
                    if filtered:
                        filtered.sort(key=lambda p: p.get('rating', 0), reverse=True)
                        brand_str = f" from {brand_filter.title()}" if brand_filter else ""
                        return {
                            "reply": f"Here are {matched_category.lower()}{brand_str} matching your request:",
                            "recommendations": filtered[:3]
                        }
                    else:
                        brand_str = f" from {brand_filter.title()}" if brand_filter else ""
                        return {
                            "reply": f"I couldn't find any {matched_category.lower()}{brand_str}. Feel free to search for another category!",
                            "recommendations": []
                        }
                else:
                    brand_filter = session.get('chatbot_pending_brand') if hasattr(session, 'get') else None
                    brand_str = f" {brand_filter.title()}" if brand_filter else ""
                    return {
                        "reply": f"Which category of{brand_str} products are you looking for? (e.g., Shoes, Electronics, Men Fashion, Women Fashion, Beauty, Home Appliances?)",
                        "recommendations": []
                    }

    # 1. Identify constraints from the message
    matched_category = None
    specific_keyword = None
    for kw, cat in KEYWORD_CATEGORY_MAP.items():
        if re.search(r'\b' + re.escape(kw) + r'\b', msg):
            matched_category = cat
            # Record if it's a specific product synonym/subcategory
            if kw not in ["men fashion", "women fashion", "home appliances", "kidsware", "kids wear", "toys", "toy", "shoes", "shoe", "electronics", "beauty", "books", "book"]:
                specific_keyword = kw
            break
            
    # Detect price request without number limit (robust to typos like "less prize", "low price", etc.)
    has_cheap_indicator = any(tok in msg for tok in ["cheap", "budget", "under", "below", "affordable", "pocket-friendly", "value for money"])
    has_low_indicator = any(tok in msg for tok in ["low", "less", "least", "lowest", "smaller", "reduced"])
    has_price_indicator = any(tok in msg for tok in ["price", "prize", "cost", "rate", "rates", "pricing", "amount", "money"])
    
    wants_budget = has_cheap_indicator or (has_low_indicator and has_price_indicator)
    
    price_limit = None
    num_match = re.search(r"(\d+)", msg)
    if num_match:
        price_limit = int(num_match.group(1))
        
    if wants_budget and price_limit is None:
        if hasattr(session, '__setitem__'):
            session['chatbot_pending_category'] = matched_category
            session['chatbot_pending_intent'] = 'price_range'
            
        cat_str = f" {matched_category.lower()}" if matched_category else " products"
        return {
            "reply": f"Sure! I can help you find low price{cat_str}. Which price range are you looking for? (e.g., under 1000, under 2000, or under 5000?)",
            "recommendations": []
        }
        
    # Detect brand request without specific brand name
    wants_brand = "brand" in words or "brands" in words or "by brand" in msg or "specific brand" in msg
    brand_filter = None
    for b in known_brands:
        if re.search(r'\b' + re.escape(b) + r'\b', msg):
            brand_filter = b
            break
            
    if wants_brand and brand_filter is None:
        if hasattr(session, '__setitem__'):
            session['chatbot_pending_category'] = matched_category
            session['chatbot_pending_intent'] = 'brand'
            
        cat_str = f" {matched_category.lower()}" if matched_category else " products"
        return {
            "reply": f"Sure! I can help you filter{cat_str} by brand. Which brand are you looking for? (e.g., Nike, Adidas, Samsung, Zara, Biba, etc. depending on the category)?",
            "recommendations": []
        }
        
    # Detect brand specified but no category specified
    if brand_filter and not matched_category:
        if hasattr(session, '__setitem__'):
            session['chatbot_pending_brand'] = brand_filter
            session['chatbot_pending_intent'] = 'category'
            
        filtered = [p for p in products if is_brand_match(p, brand_filter)]
        filtered.sort(key=lambda p: p.get('rating', 0), reverse=True)
        return {
            "reply": f"Sure! I can show you products from {brand_filter.title()}. Which category are you interested in? (e.g., Shoes, Electronics, Men Fashion, Women Fashion, Beauty, Home Appliances?)",
            "recommendations": filtered[:3]
        }
        
    # Detect rating request without rating limit
    wants_rating = any(tok in msg for tok in ["rating", "rated", "stars", "star"])
    rating_limit = None
    rating_match = re.search(r"(\d+(?:\.\d+)?)", msg) if wants_rating else None
    if rating_match:
        val = float(rating_match.group(1))
        if val <= 5.0:
            rating_limit = val
            
    if wants_rating and rating_limit is None:
        if hasattr(session, '__setitem__'):
            session['chatbot_pending_category'] = matched_category
            session['chatbot_pending_brand'] = brand_filter
            session['chatbot_pending_intent'] = 'rating'
            
        brand_str = f" from {brand_filter.title()}" if brand_filter else ""
        cat_str = f" {matched_category.lower()}" if matched_category else " products"
        return {
            "reply": f"Sure! I can find highly rated{cat_str}{brand_str} for you. What is your preferred minimum rating? (e.g., above 4 stars, above 4.5 stars?)",
            "recommendations": []
        }

    # Explicit attribute filters (e.g., "rating >= 4")
    discount_match = re.search(r'discount\s*(?:>=|>|=)?\s*(\d+)', msg)
    discount_limit = int(discount_match.group(1)) if discount_match else None
    
    size_match = re.search(r'size\s+(\w+)', msg)
    size_filter = size_match.group(1).lower() if size_match else None
    
    # Color filter
    color_filter = None
    explicit_color = re.search(r'color\s+(\w+)', msg)
    if explicit_color:
        color_filter = explicit_color.group(1).lower()
    else:
        found_colors = words.intersection(known_colors)
        if found_colors:
            color_filter = list(found_colors)[0]

    # 2. Filter products by combining all detected constraints
    has_filters = any([matched_category, price_limit, color_filter, brand_filter, size_filter, rating_limit, discount_limit])
    
    # Target exact match first
    filtered = products
    if matched_category:
        filtered = [p for p in filtered if p.get('category', '').lower() == matched_category.lower()]
    if price_limit is not None:
        filtered = [p for p in filtered if p.get('price', 0) <= price_limit]
    if color_filter:
        filtered = [p for p in filtered if p.get('color', '').lower() == color_filter]
    if brand_filter:
        filtered = [p for p in filtered if is_brand_match(p, brand_filter)]
    if size_filter:
        filtered = [p for p in filtered if p.get('size', '').lower() == size_filter]
    if rating_limit is not None:
        filtered = [p for p in filtered if float(p.get('rating', 0)) >= rating_limit]
    if discount_limit is not None:
        filtered = [p for p in filtered if int(p.get('discount', 0)) >= discount_limit]

    # 3. Direct product name match (only if no category or specific filters were applied)
    if not has_filters:
        for p in products:
            p_name = p.get('name', '').lower()
            if any(len(w) > 3 and w in p_name for w in words):
                return {
                    "reply": f"I think you might like *{p.get('name')}*.",
                    "recommendations": [p]
                }

    # 4. Prepare response based on filter results
    if has_filters and filtered:
        filtered.sort(key=lambda p: p.get('rating', 0), reverse=True)
        
        if specific_keyword:
            name_matched = [p for p in filtered if specific_keyword in p.get('name', '').lower() or specific_keyword in p.get('description', '').lower()]
            if name_matched:
                name_matched.sort(key=lambda p: p.get('rating', 0), reverse=True)
                return {
                    "reply": f"Here are products matching '{specific_keyword}':",
                    "recommendations": name_matched[:3]
                }
            else:
                # We don't have this exact item, recommend similar items from the category
                return {
                    "reply": f"We don't carry '{specific_keyword}' at the moment, but here are some related {matched_category.lower()} products you might like:",
                    "recommendations": filtered[:3]
                }
                
        return {
            "reply": "Here are products matching your criteria:",
            "recommendations": filtered[:3]
        }
        
    # 5. Smart multi-filter fallback relaxation
    if has_filters and not filtered:
        # Try dropping size filter first if it was the issue
        if size_filter:
            filtered_no_size = products
            if matched_category:
                filtered_no_size = [p for p in filtered_no_size if p.get('category', '').lower() == matched_category.lower()]
            if price_limit is not None:
                filtered_no_size = [p for p in filtered_no_size if p.get('price', 0) <= price_limit]
            if color_filter:
                filtered_no_size = [p for p in filtered_no_size if p.get('color', '').lower() == color_filter]
            if brand_filter:
                filtered_no_size = [p for p in filtered_no_size if is_brand_match(p, brand_filter)]
            if rating_limit is not None:
                filtered_no_size = [p for p in filtered_no_size if float(p.get('rating', 0)) >= rating_limit]
            if discount_limit is not None:
                filtered_no_size = [p for p in filtered_no_size if int(p.get('discount', 0)) >= discount_limit]
                
            if filtered_no_size:
                filtered_no_size.sort(key=lambda p: p.get('rating', 0), reverse=True)
                return {
                    "reply": f"I couldn't find exact matches in size '{size_filter}', but here are some options matching your other criteria:",
                    "recommendations": filtered_no_size[:3]
                }
                
        # Drop color/size and just filter by Brand + Category + Price (most important filters)
        fallback_filtered = products
        if matched_category:
            fallback_filtered = [p for p in fallback_filtered if p.get('category', '').lower() == matched_category.lower()]
        if brand_filter:
            fallback_filtered = [p for p in fallback_filtered if is_brand_match(p, brand_filter)]
        if price_limit is not None:
            fallback_filtered = [p for p in fallback_filtered if p.get('price', 0) <= price_limit]
            
        if fallback_filtered:
            fallback_filtered.sort(key=lambda p: p.get('rating', 0), reverse=True)
            brand_str = f" {brand_filter.title()}" if brand_filter else ""
            cat_str = f" {matched_category.lower()}" if matched_category else " products"
            price_str = f" under ₹{price_limit}" if price_limit is not None else ""
            return {
                "reply": f"I couldn't find products matching all your specific filters, but here are some{brand_str}{cat_str}{price_str}:",
                "recommendations": fallback_filtered[:3]
            }

    # 6. Fallbacks if filters are too strict
    if matched_category:
        cat_products = [p for p in products if p.get('category', '').lower() == matched_category.lower()]
        cat_products.sort(key=lambda p: p.get('rating', 0), reverse=True)
        return {
            "reply": f"I couldn't find exact matches for your criteria. Here are top picks in {matched_category.lower()}:",
            "recommendations": cat_products[:3]
        }
        
    # 7. Generic greeting / help
    greetings = {"hi", "hii", "hiii", "hello", "hey", "help"}
    if words.intersection(greetings) or (len(words) <= 1 and not has_filters):
        return {
            "reply": "Hello! I'm your SmartShop assistant. Ask me about a product or category and I’ll recommend something.",
            "recommendations": []
        }

    # 8. Ultimate fallback
    top_items = sorted(products, key=lambda p: p.get('rating', 0), reverse=True)[:3]
    return {
        "reply": "I'm here to help! Tell me what you're looking for and I'll suggest suitable products.",
        "recommendations": top_items
    }


