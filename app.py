from flask import Flask, render_template, request, redirect, url_for
import requests
from bs4 import BeautifulSoup
import json
import os

app = Flask(__name__)
DATA_FILE = "movies.json"

# --- Fonctions utilitaires ---
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            return json.loads(content)
    except json.JSONDecodeError:
        return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# --- Scraping IMDb ---
def scrape_imdb(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        raise ValueError("Impossible de charger la page IMDb")

    soup = BeautifulSoup(res.text, "html.parser")

    # Titre
    title_tag = soup.find("h1")
    title = title_tag.text.strip() if title_tag else "Titre inconnu"

    # Image
    img_tag = soup.find("img", {"class": "ipc-image"})
    if img_tag and "src" in img_tag.attrs:
        img_url = img_tag["src"]
        # Améliorer la résolution
        img_url = img_url.replace("_UX128_", "_UX600_")
    else:
        img_url = ""

    return {"title": title, "poster": img_url, "url": url}

# --- Routes ---
@app.route("/")
def index():
    movies = load_data()
    return render_template("index.html", movies=movies)

@app.route("/admin", methods=["GET", "POST"])
def add_movie():
    data = load_data()
    if request.method == "POST":
        imdb_url = request.form.get("imdb_url")
        movie_url = request.form.get("film_url")
        try:
            movie = scrape_imdb(imdb_url)
            movie["movie_url"] = movie_url
            data.append(movie)
            save_data(data)
            return redirect(url_for("index"))
        except Exception as e:
            return f"Erreur lors du traitement : {e}"
    return render_template("admin.html", movies=data)

@app.route("/edit/<int:index>", methods=["GET", "POST"])
def edit_movie(index):
    data = load_data()
    if index < 0 or index >= len(data):
        return "Film introuvable", 404

    movie = data[index]

    if request.method == "POST":
        imdb_url = request.form.get("imdb_url")
        movie_url = request.form.get("film_url")
        try:
            updated_movie = scrape_imdb(imdb_url)
            updated_movie["movie_url"] = movie_url
            # Remplacer l'ancien film
            data[index] = updated_movie
            save_data(data)
            return redirect(url_for("add_movie"))
        except Exception as e:
            return f"Erreur lors du traitement : {e}"

    return render_template("edit.html", movie=movie, index=index)

@app.route("/supprimer/<int:index>", methods=["GET"])
def delete_movie(index):
    print("khdskjgfhdskjghdfkjgh")
    movies = load_data()
    if index < 0 or index >= len(movies):
        return "Film introuvable", 404
    movies.pop(index)
    save_data(movies)
    return redirect(url_for("add_movie"))

@app.route("/movie/<int:index>")
def movie_detail(index):
    movies = load_data()
    if index < 0 or index >= len(movies):
        return "Film introuvable", 404
    movie = movies[index]
    return render_template("detail.html", movie=movie)

# --- Lancement local ---
if __name__ == "__main__":
    app.run(debug=True)
