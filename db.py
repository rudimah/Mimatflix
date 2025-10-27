import mysql.connector
from mysql.connector import errorcode
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "password")
DB_DATABASE = os.environ.get("DB_DATABASE", "defaultdb") # Utilise 'defaultdb' comme spécifié
# Ajout de DB_PORT, par défaut 3306 si non spécifié
DB_PORT = int(os.environ.get("DB_PORT", 3306))

def get_db_connection():
    """Établit et retourne une nouvelle connexion à la base de données."""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_DATABASE,
            port=DB_PORT # Utilisation du port spécifié
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
        delete_query = "DELETE FROM movie WHERE id_movie = %s"
        cursor.execute(delete_query, (id_movie,))
        conn.commit()
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
        return movie
    except Exception as e:
        print(f"Erreur lors de la récupération du film {id_movie} : {e}")
        return None
    finally:
        cursor.close()
        conn.close()