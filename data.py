import mysql.connector
from mysql.connector import errorcode
import os
import boto3
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
    """Établit et retourne une nouvelle connexion à la base de données."""
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
            # Affiche l'adresse et le port réels utilisés pour le débogage
            print(f"Erreur de connexion à la base de données : {err} (Tentative sur {DB_HOST}:{DB_PORT})")
        # En production, vous devriez logger cette erreur et peut-être arrêter l'application
        # Pour cet exemple, nous retournons None et gérons l'absence de connexion plus tard.
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


def flux_mp4(url):
    try:
        response = requests.get(url, impersonate="chrome110")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            hidden_elem = soup.find(id="norobotlink")
            if hidden_elem:
                link_base = hidden_elem.get_text()
                if not link_base:
                    return None
                    
                final_link = link_base + "&dl=1"
                final_link = "https:/" + final_link
                return final_link
            
    except Exception:
        return None


def delete_r2_file(filename):
    """
    Supprime un fichier spécifique du bucket R2.
    Retourne True si la commande a été envoyée avec succès, False sinon.
    """

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
    

# --- Fonctions utilitaires MySQL (CRUD) ---


def load_data():
    """Charge tous les films depuis la base de données."""
    conn = get_db_connection()
    if not conn: return []

    cursor = conn.cursor(dictionary=True)
    try:
        # Sélectionne tous les films
        cursor.execute("SELECT id_movie, title, poster, url, movie_url FROM movie ORDER BY id_movie DESC")
        movies = cursor.fetchall()
        return movies
    except Exception as e:
        print(f"Erreur lors du chargement des données : {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def save_movie(movie):
    """Ajoute un nouveau film dans la base de données."""
    conn = get_db_connection()
    if not conn: return

    cursor = conn.cursor()
    try:
        # Note: id_movie est AUTO_INCREMENT, donc on ne le fournit pas
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
    """Met à jour un film existant en utilisant son id_movie."""
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
    """Supprime un film en utilisant son id_movie."""
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
    """Supprime un film en utilisant son id_movie."""
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
    """Récupère un film unique par son id_movie."""
    conn = get_db_connection()
    if not conn: return None

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id_movie, title, poster, url, movie_url FROM movie WHERE id_movie = %s", (id_movie,))
        movie = cursor.fetchone()
        filename = movie.get('movie_url', '')
       
        if "token" in filename:
            movie['play_url'] = filename
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