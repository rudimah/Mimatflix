from flask import Flask, render_template, request, redirect, url_for, abort
import requests
from bs4 import BeautifulSoup
from db import load_data, save_movie, update_movie, delete_movie_by_id, get_movie_by_id



app = Flask(__name__)

# --- Scraping IMDb 
def scrape_imdb(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"}
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        raise ValueError(f"Impossible de charger la page IMDb (Status {res.status_code})")

    soup = BeautifulSoup(res.text, "html.parser")

    # Titre
    # IMDb utilise souvent la balise <h1 data-testid="hero-title-block__title">
    title_tag = soup.find("h1", {"data-testid": "hero-title-block__title"})
    if not title_tag: # Fallback pour les pages moins récentes
        title_tag = soup.find("h1")

    title = title_tag.text.strip() if title_tag else "Titre inconnu"

    # Image
    
    img_tag = soup.find("div", {"data-testid": "hero-media__poster"}).find("img") if soup.find("div", {"data-testid": "hero-media__poster"}) else None
    
    if not img_tag: # Fallback pour la classe ipc-image ou autre
        img_tag = soup.find("img", {"class": "ipc-image"})

    if img_tag and "src" in img_tag.attrs:
        # Tentative de récupérer une meilleure résolution
        img_url = img_tag["src"].replace("_UX128_", "_UX600_").split("._V1_")[0] + "._V1_.jpg"
    else:
        img_url = ""

    # Ajout d'une vérification minimale pour s'assurer que le scraping a réussi
    if title == "Titre inconnu" and img_url == "":
         raise ValueError("Scraping IMDb a échoué. Vérifiez l'URL ou les sélecteurs.")

    return {"title": title, "poster": img_url, "url": url}



@app.route("/")
def index():
    movies = load_data()
    return render_template("index.html", movies=movies)

@app.route("/hamidur", methods=["GET", "POST"])
def add_movie():
    movies = load_data()
    if request.method == "POST":
        imdb_url = request.form.get("imdb_url")
        movie_url = request.form.get("film_url")
        try:
            movie = scrape_imdb(imdb_url)
            movie["movie_url"] = movie_url
            save_movie(movie)
            # Redirige après succès pour éviter la soumission multiple
            return redirect(url_for("add_movie"))
        except ValueError as e:
            return render_template("admin.html", movies=movies, error=f"Erreur de scraping/validation: {e}"), 400
        except Exception as e:
            # Erreur de DB, etc.
            return render_template("admin.html", movies=movies, error=f"Erreur système: {e}"), 500

    return render_template("admin.html", movies=movies)

@app.route("/edit/<int:id_movie>", methods=["GET", "POST"])
def edit_movie(id_movie):
    movie = get_movie_by_id(id_movie)
    if movie is None:
        abort(404) # Film introuvable

    if request.method == "POST":
        imdb_url = request.form.get("imdb_url")
        movie_url = request.form.get("film_url")
        try:
            # Utiliser scrape_imdb pour potentiellement mettre à jour le titre et l'affiche
            updated_movie_details = scrape_imdb(imdb_url)
            updated_movie_details["movie_url"] = movie_url

            update_movie(id_movie, updated_movie_details)
            return redirect(url_for("add_movie"))
        except ValueError as e:
            return render_template("edit.html", movie=movie, error=f"Erreur de scraping/validation: {e}"), 400
        except Exception as e:
            return render_template("edit.html", movie=movie, error=f"Erreur système: {e}"), 500

    return render_template("edit.html", movie=movie)

@app.route("/delete/<int:id_movie>", methods=["POST"])
def delete_movie(id_movie):
    delete_movie_by_id(id_movie)
    return redirect(url_for("add_movie"))

@app.route("/movie/<int:id_movie>")
def movie_detail(id_movie):
    movie = get_movie_by_id(id_movie)
    if movie is None:
        abort(404) # Film introuvable
    return render_template("detail.html", movie=movie)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)