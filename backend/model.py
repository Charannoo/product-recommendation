from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

def get_user_recommendations(user_history_ids, catalog, num_recommendations=6):
    """
    Generate product recommendations using content-based filtering (TF-IDF & Cosine Similarity)
    user_history_ids: list of integer product IDs that the user has interacted with
    catalog: list of product dictionaries
    num_recommendations: max number of items to return
    """
    if not catalog:
        return []
        
    # If the user has no history, return the top rated/popular products
    if not user_history_ids:
        sorted_catalog = sorted(catalog, key=lambda x: (x.get('rating', 0), x.get('popularity', False)), reverse=True)
        return sorted_catalog[:num_recommendations]
        
    # Build a text corpus for each product
    corpus = []
    product_mapping = {} # maps matrix index to product ID
    
    for idx, product in enumerate(catalog):
        product_mapping[idx] = product
        # Combine relevant metadata into a single string
        name = product.get('name', '')
        desc = product.get('description', '')
        cat = product.get('category', '')
        text = f"{name} {desc} {cat}".lower()
        corpus.append(text)
        
    if not corpus:
        return []
        
    # Create TF-IDF matrix
    try:
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(corpus)
    except Exception as e:
        # Fallback if vectorizer completely fails
        return catalog[:num_recommendations]
        
    # Calculate similarity scores
    cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

    # Find the matrix indices of the products in the user's history
    history_indices = [idx for idx, product in product_mapping.items() if product.get('id') in user_history_ids]
    
    if not history_indices:
        # History IDs didn't match any catalog items
        sorted_catalog = sorted(catalog, key=lambda x: (x.get('rating', 0), x.get('popularity', False)), reverse=True)
        return sorted_catalog[:num_recommendations]
        
    # For each item not in the user's history, compute its average similarity to the history items
    recommendation_scores = []
    for target_idx in range(len(catalog)):
        if target_idx in history_indices:
            continue # Don't recommend what they already have
            
        sims = [cosine_sim[target_idx][hist_idx] for hist_idx in history_indices]
        avg_sim = np.mean(sims) if sims else 0
        recommendation_scores.append((avg_sim, target_idx))
        
    # Sort recommendations by highest average similarity
    recommendation_scores.sort(key=lambda x: x[0], reverse=True)
    
    # Extract the top N products
    recommended_products = []
    for score, idx in recommendation_scores[:num_recommendations]:
        recommended_products.append(product_mapping[idx])
        
    # If we didn't find enough recommendations, pad with top rated ones
    if len(recommended_products) < num_recommendations:
        already_recommended = {p['id'] for p in recommended_products}
        sorted_fallback = sorted(catalog, key=lambda x: (x.get('rating', 0), x.get('popularity', False)), reverse=True)
        for p in sorted_fallback:
            if p['id'] not in already_recommended and p['id'] not in user_history_ids:
                recommended_products.append(p)
                already_recommended.add(p['id'])
            if len(recommended_products) >= num_recommendations:
                break
                
    return recommended_products
