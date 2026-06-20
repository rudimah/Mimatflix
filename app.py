from flask import Flask, jsonify, render_template, request, redirect, url_for, abort, session
from functools import wraps
from data import scrape_imdb, load_data, save_movie, update_movie, delete_movie_by_id, get_movie_by_id, delete_video_by_id, get_r2_storage_usage, get_pending_downloads, get_api_pending_downloads, add_pending_movie, complete_movie_download
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "mimatflix_super_secret_key")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
def index():
    movies = load_data(limit=7, home=True)
    return render_template("index.html", movies=movies, is_home=True)

@app.route("/catalogue")
def catalogue():
    movies = load_data(home=False)
    return render_template("index.html", movies=movies, is_home=False)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for("add_movie"))
        return render_template("login.html", error="Mot de passe incorrect")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop('is_admin', None)
    return redirect(url_for("index"))

@app.route(("/manage"), methods=["GET", "POST"])
@login_required
def add_movie():
    movies = load_data(home=False)
    pending_movies = get_pending_downloads()
    usage_bytes = get_r2_storage_usage()
    usage_go = round(usage_bytes / (1024**3), 2)
    
    if request.method == "POST":
        imdb_url = request.form.get("imdb_url")
        film_url = request.form.get("film_url", "").strip()
        source_link = request.form.get("source_link", "").strip()
        try:
            movie = scrape_imdb(imdb_url)
            if not film_url:
                add_pending_movie(movie, source_link)
            else:
                movie["movie_url"] = film_url
                save_movie(movie)
            return redirect(url_for("add_movie"))
        except ValueError as e:
            return render_template("admin.html", movies=movies, pending=pending_movies, error=str(e), usage_go=usage_go), 400
        except Exception as e:
            return render_template("admin.html", movies=movies, pending=pending_movies, error=str(e), usage_go=usage_go), 500
    return render_template("admin.html", movies=movies, pending=pending_movies, usage_go=usage_go)

@app.route("/api/downloads/pending", methods=["GET"])
def api_get_pending():
    pending = get_api_pending_downloads()
    return jsonify(pending), 200

@app.route("/api/downloads/complete", methods=["POST"])
def api_complete_download():
    data = request.get_json()
    id_movie = data.get('id_movie')
    filename = data.get('filename')
    if not id_movie or not filename:
        return jsonify({"error": "Missing data"}), 400
    complete_movie_download(id_movie, filename)
    return jsonify({"message": "Success", "id_movie": id_movie}), 200

@app.route("/edit/<int:id_movie>", methods=["GET", "POST"])
@login_required
def edit_movie(id_movie):
    movie = get_movie_by_id(id_movie)
    if movie is None:
        abort(404)
    if request.method == "POST":
        imdb_url = request.form.get("imdb_url")
        url = request.form.get("film_url")
        source_link = request.form.get("source_link")
        try:
            updated_movie_details = scrape_imdb(imdb_url)
            updated_movie_details["movie_url"] = url
            updated_movie_details["source_link"] = source_link
            update_movie(id_movie, updated_movie_details)
            return redirect(url_for("add_movie"))
        except Exception as e:
            return render_template("edit.html", movie=movie, error=str(e)), 500
    return render_template("edit.html", movie=movie)

@app.route("/<int:id_movie>", methods=["POST"])
@login_required
def delete_movie(id_movie):
    delete_movie_by_id(id_movie)
    return redirect(url_for("add_movie"))

@app.route("/video/<int:id_movie>", methods=["POST"])
@login_required
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