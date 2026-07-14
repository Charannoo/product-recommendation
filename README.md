<div align="center">
  <img src="https://img.shields.io/badge/Python-3.13+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-2.3+-black?logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/scikit--learn-TF--IDF-orange?logo=scikit-learn&logoColor=white" alt="scikit-learn">
  <img src="https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/status-active-success" alt="Status">
</div>

<br>


<h1 align="center">🛍️ SmartShop AI</h1>
<h3 align="center">AI-Powered Product Recommendation & Discovery Engine</h3>

<p align="center">
  <i>A modern, high-performance e-commerce discovery platform featuring AI-driven recommendations, 
  vibe-based lookbooks, interactive search, and a smart chatbot assistant — all wrapped in a premium glassmorphic UI.</i>
</p>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🧠 **AI Recommendations** | Content-based filtering using TF-IDF + Cosine Similarity |
| 💬 **Smart Chatbot** | Multi-turn conversational assistant with keyword mapping & brand synonyms |
| 🎯 **Product Quiz** | 5-step questionnaire that matches users to perfect products |
| 🎨 **Vibe Check** | Discover products by mood — Cool, Professional, Party, Comfort |
| ❤️ **Wishlist & Collections** | Organize saved items into custom collections |
| 🏷️ **Multi-Marketplace Prices** | Compare prices across Amazon, Flipkart, Myntra & AJIO |
| 🔍 **Smart Search** | Synonym-aware query matching & multi-filter refinement |
| 📊 **AI Product Insights** | Auto-generated pros/cons, use cases & target audience |
| 📱 **Responsive UI** | Glassmorphism design with custom animations & interactive elements |
| 🔐 **OTP Authentication** | Email-based OTP login with rate limiting |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.13+
- pip (Python package manager)

### One-Click Run

**Windows** — Double-click `run.bat`  
**macOS / Linux** — Run `./run.sh`

Or manually:

```bash
# Clone the repository
git clone https://github.com/Charannoo/product-recommendation.git
cd product-recommendation

# Create virtual environment & install dependencies
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt

# Seed the database
python backend/inject_lookbooks.py

# Launch the server
python backend/app.py
```

Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser.

---

## 🏗️ Architecture

```
product-recommendation/
├── backend/
│   ├── app.py              # Flask server — 50+ routes
│   ├── chatbot.py          # Rule-based conversational AI
│   ├── db.py               # SQLite schema & migrations
│   ├── model.py            # TF-IDF recommendation engine
│   └── inject_lookbooks.py # Database seeding
├── frontend/
│   ├── templates/          # 20+ Jinja2 HTML templates
│   └── static/             # CSS, JS, images, icons
├── data/
│   ├── shop.db             # SQLite database
│   └── catalog.json        # Product catalog
├── .env                    # Environment variables
└── requirements.txt        # Python dependencies
```

---

## 🧠 AI Recommendation Engine

The recommendation system uses **content-based filtering**:

1. **Feature Extraction** — Constructs a text corpus from product names, descriptions & categories
2. **Vectorization** — Converts text to numerical vectors using TF-IDF
3. **Similarity Computation** — Calculates cosine similarity between all product pairs
4. **Personalization** — Recommends items similar to the user's interaction history

Falls back to top-rated / popular products for new users.

---

## 💬 Chatbot Capabilities

- 🗂️ **Category Detection** — Maps 150+ keywords to product categories
- 💰 **Budget Filtering** — Multi-turn price range refinement
- 🏷️ **Brand Matching** — Handles synonyms (e.g., "HM" ↔ "H&M")
- 🔄 **Filter Relaxation** — Drops constraints one-by-one to find results
- 🎯 **Exact Matching** — Direct product name lookup as final fallback

---

## 🎨 UI Highlights

- **Lamp Animation** — Interactive pull-cord toggle on the login page
- **Bokeh Canvas** — Animated particle background on product pages
- **Glassmorphism** — Frosted glass cards & modals throughout
- **Image Zoom** — Mouse-follow magnifier on product detail images
- **Animated Progress** — Step indicators in the quiz & OTP flows
- **Toast Notifications** — Non-intrusive feedback for all actions

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python, Flask, Gunicorn |
| **AI/ML** | scikit-learn (TF-IDF, Cosine Similarity), NumPy |
| **Database** | SQLite3 |
| **Frontend** | Vanilla CSS (glassmorphism, animations), Vanilla JS |
| **Auth** | Email OTP with rate limiting |
| **Deployment** | Render |

---


## 📄 License

This project is licensed under the MIT License.

---

<div align="center">
  Made with ❤️ by <a href="https://github.com/Charannoo">Charannoo</a>
</div>
