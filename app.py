from flask import Flask, render_template, request, redirect, url_for
import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

app = Flask(__name__)

# --- Google Sheets setup ---
# Mets ton fichier service_account.json dans le même dossier que app.py
SERVICE_ACCOUNT_FILE = "service_account.json"

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
client = gspread.authorize(creds)

# Nom de la feuille Google
SHEET_NAME = "Movies"
sheet = client.open(SHEET_NAME).sheet1

# --- Fonctions utilitaires Google Sheets ---
def load_data():
    records = sheet.get_all_records()
    return records

def save_movie(movie):
    sheet.append_row([movie["title"], movie["poster"], movie["url"], movie.get("movie_url", "")])

def update_movie(index, movie):
    row = index + 2  # +1 pour l'en-tête, +1 car gspread commence à 1
    sheet.update(f"A{row}", movie["title"])
    sheet.update(f"B{row}", movie["poster"])
    sheet.update(f"C{row}", movie["url"])
    sheet.update(f"D{row}", movie.get("movie_url", ""))

def delete_movie_row(index):
    row = index + 2
    sheet.delete_row(row)

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
        img_url = img_tag["src"].replace("_UX128_", "_UX600_")
    else:
        img_url = ""

    return {"title": title, "poster": img_url, "url": url}

# --- Routes ---
@app.route("/")
def index():
    movies = load_data()
    return render_template("index.html", movies=movies)

@app.route("/hamidur", methods=["GET", "POST"])
def add_movie():
    data = load_data()
    if request.method == "POST":
        imdb_url = request.form.get("imdb_url")
        movie_url = request.form.get("film_url")
        try:
            movie = scrape_imdb(imdb_url)
            movie["movie_url"] = movie_url
            save_movie(movie)
            return redirect(url_for("add_movie"))
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
            update_movie(index, updated_movie)
            return redirect(url_for("add_movie"))
        except Exception as e:
            return f"Erreur lors du traitement : {e}"

    return render_template("edit.html", movie=movie, index=index)

@app.route("/supprimer/<int:index>", methods=["GET"])
def delete_movie(index):
    movies = load_data()
    if index < 0 or index >= len(movies):
        return "Film introuvable", 404
    delete_movie_row(index)
    return redirect(url_for("add_movie"))

@app.route("/movie/<int:index>")
def movie_detail(index):
    movies = load_data()
    if index < 0 or index >= len(movies):
        return "Film introuvable", 404
    movie = movies[index]
    return render_template("detail.html", movie=movie)

# --- Run Flask ---
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
