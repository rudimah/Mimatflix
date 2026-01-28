from flask import Flask, render_template, request, redirect, url_for, abort
from data import scrape_imdb, load_data, save_movie, update_movie, delete_movie_by_id, get_movie_by_id, delete_video_by_id, flux_mp4
import os
from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)


@app.route("/")
def index():
    movies = load_data()
    return render_template("index.html", movies=movies)


@app.route(os.environ.get("ADMIN_URL", "/ADMIN"), methods=["GET", "POST"])
def add_movie():
    movies = load_data()
    if request.method == "POST":
        imdb_url = request.form.get("imdb_url")

        url = request.form.get("film_url")
        
        try:
            movie = scrape_imdb(imdb_url)
            if "streamtape" in url and "token" not in url:
                movie["movie_url"] = flux_mp4(url)    
            else:
                movie["movie_url"] = url
            save_movie(movie)
            return redirect(url_for("add_movie"))
        except ValueError as e:
            return render_template("admin.html", movies=movies, error=f"Erreur de scraping: {e}"), 400
        except Exception as e:
            return render_template("admin.html", movies=movies, error=f"Erreur système: {e}"), 500

    return render_template("admin.html", movies=movies)


@app.route("/edit/<int:id_movie>", methods=["GET", "POST"])
def edit_movie(id_movie):
    movie = get_movie_by_id(id_movie)
    if movie is None:
        abort(404)

    if request.method == "POST":
        imdb_url = request.form.get("imdb_url")
        url = request.form.get("film_url")
        
        try:
            updated_movie_details = scrape_imdb(imdb_url)
            if "streamtape" in url and "token" not in url:
                updated_movie_details["movie_url"] = flux_mp4(url)    
            else:
                updated_movie_details["movie_url"] = url

            update_movie(id_movie, updated_movie_details)
            return redirect(url_for("add_movie"))
        except ValueError as e:
            return render_template("edit.html", movie=movie, error=f"Erreur: {e}"), 400
        except Exception as e:
            return render_template("edit.html", movie=movie, error=f"Erreur système: {e}"), 500

    return render_template("edit.html", movie=movie)


@app.route("/<int:id_movie>", methods=["POST"])
def delete_movie(id_movie):
    delete_movie_by_id(id_movie)
    return redirect(url_for("add_movie"))


@app.route("/video/<int:id_movie>", methods=["POST"])
def delete_video(id_movie):
    delete_video_by_id(id_movie)
    return redirect(url_for("add_movie"))


@app.route("/movie/<int:id_movie>")
def movie_detail(id_movie):
    movie = get_movie_by_id(id_movie)
    if movie is None:
        abort(404) 

    return render_template("detail.html", movie=movie)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)