import mysql.connector
from mysql.connector import errorcode
import os
import boto3
import time
from botocore.client import Config
from curl_cffi import requests
from bs4 import BeautifulSoup
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
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "x-imdb-client-name": "imdb-web-next-localized",
        "x-imdb-client-version": "1.0.0",
        "x-imdb-user-country": "US",
        "x-imdb-user-language": "en-US",
    }
    payload = {
        "operationName": "GetTitle",
        "variables": {"id": movie_id},
        "query": """
        query GetTitle($id: ID!) {
          title(id: $id) {
            id
            titleText { text }
            primaryImage { url }
          }
        }
        """
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
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_DATABASE,
            port=DB_PORT,
            ssl_ca="ca.pem" 
        )
        return conn
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Erreur: Nom d'utilisateur ou mot de passe incorrect.")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Erreur: La base de données n'existe pas.")
        else:
            print(f"Erreur de connexion à la base de données : {err} (Tentative sur {DB_HOST}:{DB_PORT})")
        return None


def init_client_r2():
     try:
        s3 = boto3.client('s3',
            endpoint_url=f'https://{os.environ.get("R2_ACCOUNT_ID")}.r2.cloudflarestorage.com',
            aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"),
            config=Config(signature_version='s3v4')
        )
        return s3
     except Exception as e:
        print(f"Erreur lors de la suppression du fichier R2 : {e}")
        return False
     

def get_r2_signed_url(filename):
    try:
        s3 = init_client_r2()
        
        url = s3.generate_presigned_url('get_object',
                                         Params={'Bucket': os.environ.get("R2_BUCKET_NAME", "mes-films") , 'Key': filename}, ExpiresIn=10800)
        return url
    except Exception as e:
        print(f"Erreur lors de la génération du lien R2 : {e}")
        return None


def get_r2_storage_usage():
    try:
        s3 = init_client_r2()
        if not s3:
            return 0
        
        total_size = 0
        continuation_token = None
        
        while True:
            kwargs = {'Bucket': os.environ.get("R2_BUCKET_NAME", "mes-films")}
            if continuation_token:
                kwargs['ContinuationToken'] = continuation_token
                
            response = s3.list_objects_v2(**kwargs)
            for obj in response.get('Contents', []):
                total_size += obj['Size']
                
            if not response.get('IsTruncated'):
                break
            continuation_token = response.get('NextContinuationToken')
            
        return total_size
    except Exception as e:
        print(f"Erreur lors du calcul du stockage R2 : {e}")
        return 0


def delete_r2_file(filename):
    print(filename)
    try:
        s3 = init_client_r2()
        
        s3.delete_object(
            Bucket=os.environ.get("R2_BUCKET_NAME", "mes-films"),
            Key=filename
        )
        
        print(f"Fichier '{filename}' supprimé avec succès.")
        return True

    except Exception as e:
        print(f"Erreur lors de la suppression du fichier R2 : {e}")
        return False
    

def load_data(limit=None):
    conn = get_db_connection()
    if not conn: return []

    cursor = conn.cursor(dictionary=True)
    try:
        query = "SELECT id_movie, title, poster, url, movie_url FROM movie ORDER BY id_movie DESC"
        if limit:
            query += f" LIMIT {int(limit)}"
            
        cursor.execute(query)
        movies = cursor.fetchall()
        return movies
    except Exception as e:
        print(f"Erreur lors du chargement des données : {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def save_movie(movie):
    conn = get_db_connection()
    if not conn: return

    cursor = conn.cursor()
    try:
        add_movie_query = (
            "INSERT INTO movie (title, poster, url, movie_url) "
            "VALUES (%s, %s, %s, %s)"
        )
        data_movie = (movie["title"], movie["poster"], movie["url"], movie.get("movie_url", ""))
        cursor.execute(add_movie_query, data_movie)
        conn.commit()
    except Exception as e:
        print(f"Erreur lors de l'enregistrement du film : {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def update_movie(id_movie, movie):
    conn = get_db_connection()
    if not conn: return

    cursor = conn.cursor()
    try:
        update_query = (
            "UPDATE movie SET title = %s, poster = %s, url = %s, movie_url = %s "
            "WHERE id_movie = %s"
        )
        data_movie = (movie["title"], movie["poster"], movie["url"], movie.get("movie_url", ""), id_movie)
        cursor.execute(update_query, data_movie)
        conn.commit()
    except Exception as e:
        print(f"Erreur lors de la mise à jour du film {id_movie} : {e}")
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
        delete_query = "DELETE FROM movie WHERE id_movie = %s"
        cursor.execute(delete_query, (id_movie,))
        conn.commit()
        filename = movie[0]
        if filename and not filename.startswith("http"):
           delete_r2_file(filename)
    except Exception as e:
        print(f"Erreur lors de la suppression du film {id_movie} : {e}")
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
        filename = movie[0]
        if filename and not filename.startswith("http"):
           delete_r2_file(filename)
    except Exception as e:
        print(f"Erreur lors de la suppression du film {id_movie} : {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def get_movie_by_id(id_movie):
    conn = get_db_connection()
    if not conn: return None

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id_movie, title, poster, url, movie_url FROM movie WHERE id_movie = %s", (id_movie,))
        movie = cursor.fetchone()
        filename = movie.get('movie_url', '')
       
        if "directlink" in filename:
            movie['play_url'] = filename.replace("directlink ", "")
            return movie

        signed_url = get_r2_signed_url(filename)
        if signed_url:
            movie['play_url'] = signed_url
            return movie

        else:
            print(f"Impossible de générer le lien pour {filename}")
        return movie
    except Exception as e:
        print(f"Erreur lors de la récupération du film {id_movie} : {e}")
        return None
    finally:
        cursor.close()
        conn.close()