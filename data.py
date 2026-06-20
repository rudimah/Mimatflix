import mysql.connector
from mysql.connector import errorcode
import os
import boto3
from botocore.client import Config
from curl_cffi import requests
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "password")
DB_DATABASE = os.environ.get("DB_DATABASE", "defaultdb")
DB_PORT = int(os.environ.get("DB_PORT", 3306))

def scrape_imdb(url):
    BASE_URL = "https://caching.graphql.imdb.com/"
    for elem in url.split("/"):
        if elem.startswith("tt"):
            movie_id = elem
    HEADERS = {
        "accept": "application/graphql+json, application/json",
        "content-type": "application/json",
        "origin": "https://www.imdb.com",
        "referer": "https://www.imdb.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "x-imdb-client-name": "imdb-web-next-localized",
        "x-imdb-client-version": "1.0.0",
        "x-imdb-user-country": "US",
        "x-imdb-user-language": "en-US",
    }
    payload = {
        "operationName": "GetTitle",
        "variables": {"id": movie_id},
        "query": """query GetTitle($id: ID!) {title(id: $id) {titleText { text } primaryImage { url }}}"""
    }
    r = requests.post(BASE_URL, headers=HEADERS, json=payload)
    r.raise_for_status()
    title = r.json().get("data", {}).get("title")
    if not title:
        raise ValueError("Titre introuvable")
    return {
        "title": title["titleText"]["text"],
        "poster": title.get("primaryImage", {}).get("url"),
        "url": url
    }

def get_db_connection():
    try:
        return mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_DATABASE, port=DB_PORT, ssl_ca="ca.pem")
    except:
        return None

def init_client_r2():
    try:
        return boto3.client('s3', endpoint_url=f'https://{os.environ.get("R2_ACCOUNT_ID")}.r2.cloudflarestorage.com', aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"), aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"), config=Config(signature_version='s3v4'))
    except:
        return False

def get_r2_signed_url(filename):
    try:
        s3 = init_client_r2()
        return s3.generate_presigned_url('get_object', Params={'Bucket': os.environ.get("R2_BUCKET_NAME", "mes-films") , 'Key': filename}, ExpiresIn=10800)
    except:
        return None

def get_r2_storage_usage():
    try:
        s3 = init_client_r2()
        if not s3: return 0
        total_size = 0
        continuation_token = None
        while True:
            kwargs = {'Bucket': os.environ.get("R2_BUCKET_NAME", "mes-films")}
            if continuation_token: kwargs['ContinuationToken'] = continuation_token
            response = s3.list_objects_v2(**kwargs)
            for obj in response.get('Contents', []): total_size += obj['Size']
            if not response.get('IsTruncated'): break
            continuation_token = response.get('NextContinuationToken')
        return total_size
    except:
        return 0

def delete_r2_file(filename):
    try:
        s3 = init_client_r2()
        s3.delete_object(Bucket=os.environ.get("R2_BUCKET_NAME", "mes-films"), Key=filename)
        return True
    except:
        return False

def add_pending_movie(movie, source_link):
    conn = get_db_connection()
    if not conn: return
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO movie (title, poster, url, source_link, status) VALUES (%s, %s, %s, %s, 'pending')", (movie["title"], movie["poster"], movie["url"], source_link))
        conn.commit()
    except:
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def get_pending_downloads():
    conn = get_db_connection()
    if not conn: return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id_movie, title, poster, source_link FROM movie WHERE status = 'pending'")
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_api_pending_downloads():
    return get_pending_downloads()

def complete_movie_download(id_movie, filename):
    conn = get_db_connection()
    if not conn: return
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE movie SET movie_url = %s, status = 'available' WHERE id_movie = %s", (filename, id_movie))
        conn.commit()
    except:
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def load_data(limit=None, home=False):
    conn = get_db_connection()
    if not conn: return []
    cursor = conn.cursor(dictionary=True)
    try:
        if home:
            query = "SELECT id_movie, title, poster, url, movie_url, status, created_at, updated_at FROM movie WHERE status IN ('available', 'deleted') ORDER BY status = 'available' DESC, updated_at DESC, id_movie DESC"
        else:
            query = "SELECT id_movie, title, poster, url, movie_url, status, created_at, updated_at FROM movie WHERE status IN ('available', 'deleted') ORDER BY updated_at DESC, id_movie DESC"
        if limit:
            query += f" LIMIT {int(limit)}"
        cursor.execute(query)
        movies = cursor.fetchall()
        for m in movies:
            if m.get('created_at'): m['created_at_str'] = m['created_at'].strftime('%d/%m/%Y')
            if m.get('updated_at'): m['updated_at_str'] = m['updated_at'].strftime('%d/%m/%Y')
            m['download'] = (m.get('status') == 'available')
        return movies
    except:
        return []
    finally:
        cursor.close()
        conn.close()

def save_movie(movie):
    conn = get_db_connection()
    if not conn: return
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO movie (title, poster, url, movie_url, status) VALUES (%s, %s, %s, %s, 'available')", (movie["title"], movie["poster"], movie["url"], movie.get("movie_url", "")))
        conn.commit()
    except:
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def update_movie(id_movie, movie):
    conn = get_db_connection()
    if not conn: return
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE movie SET title = %s, poster = %s, url = %s, movie_url = %s, source_link = %s WHERE id_movie = %s", (movie["title"], movie["poster"], movie["url"], movie.get("movie_url", ""), movie.get("source_link", ""), id_movie))
        conn.commit()
    except:
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def delete_movie_by_id(id_movie):
    conn = get_db_connection()
    if not conn: return
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT movie_url FROM movie WHERE id_movie = %s", (id_movie,))
        movie = cursor.fetchone()
        cursor.execute("DELETE FROM movie WHERE id_movie = %s", (id_movie,))
        conn.commit()
        if movie and movie[0] and not movie[0].startswith("http"): delete_r2_file(movie[0])
    except:
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def delete_video_by_id(id_movie):
    conn = get_db_connection()
    if not conn: return
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT movie_url FROM movie WHERE id_movie = %s", (id_movie,))
        movie = cursor.fetchone()
        cursor.execute("UPDATE movie SET movie_url = NULL, status = 'deleted' WHERE id_movie = %s", (id_movie,))
        conn.commit()
        if movie and movie[0] and not movie[0].startswith("http"): delete_r2_file(movie[0])
    except:
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def get_movie_by_id(id_movie):
    conn = get_db_connection()
    if not conn: return None
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id_movie, title, poster, url, movie_url, status, source_link, created_at, updated_at FROM movie WHERE id_movie = %s", (id_movie,))
        movie = cursor.fetchone()
        if not movie: return None
        movie['download'] = (movie.get('status') == 'available')
        filename = movie.get('movie_url')
        if not filename:
            movie['play_url'] = ''
            return movie
        if "directlink" in filename:
            movie['play_url'] = filename.replace("directlink ", "")
            return movie
        signed_url = get_r2_signed_url(filename)
        movie['play_url'] = signed_url if signed_url else ''
        return movie
    except:
        return None
    finally:
        cursor.close()
        conn.close()