# SmartShop AI Product Recommendation Discovery Engine

SmartShop is a modern, high-performance, AI-driven product discovery engine featuring card-based grids, collection-based wishlist management, styled lookbooks based on user vibes, interactive search query matching, and an AI-driven chatbot assistant.

---

## Quick Start (How to Run)

To make it as easy as possible to run this project (even after unzipping on a new computer), we have provided startup launchers that automatically set up the virtual environment, install dependencies, seed the database, and launch the server.

### On Windows
1. Double-click the **`run.bat`** file in the root folder.
2. A command prompt will open, set up everything, and launch the server.
3. Your default web browser will automatically open to `http://127.0.0.1:5000/`.

### On macOS / Linux
1. Open your terminal in the project directory.
2. Grant execution permission to the shell script:
   ```bash
   chmod +x run.sh
   ```
3. Run the script:
   ```bash
   ./run.sh
   ```
4. Open your web browser and navigate to `http://127.0.0.1:5000/`.

---

## Technical Stack & Features

- **Backend**: Python Flask web server.
- **AI Recommendation Engine**: Content-based filtering using **TF-IDF Vectorization** and **Cosine Similarity** (`scikit-learn` & `numpy`) to suggest products based on user interaction history.
- **Database**: SQLite3 database (`data/shop.db`) containing products, users, wishlists/saved items, and marketplace prices.
- **Frontend**: Clean and premium responsive UI styled using Vanilla CSS, complete with custom animations, glassmorphism components, and a custom interactive chat interface.
- **AI Chatbot**: Rule and keyword-based assistant for product categorization, budget filtering, and product recommendations.
