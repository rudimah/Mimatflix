# 🎬 Mimatflix

**Mimatflix** est une application web personnelle pour visionner des films.

## 🚀 Fonctionnalités

* **Catalogue visuel** : Affichage des films sous forme de grille responsive avec affiches.
* **Ajout intelligent** : Saisissez simplement l'URL IMDb, et l'application récupère automatiquement le titre et l'affiche du film.
* **Lecteur intégré** : Support des iframes pour visionner les films directement depuis la page de détail.
* **Gestion complète (CRUD)** :
    * Ajouter un film.
    * Modifier les liens (IMDb ou streaming).
    * Supprimer un film.


## 🛠 Stack Technique

* **Backend** : Python, Flask.
* **Base de données** : MySQL.
* **Scraping** : BeautifulSoup4, Requests.
* **Stockage Fichiers** : Cloudflare R2 
* **Frontend** : HTML5, CSS3 (Responsive).
* **Serveur** : Gunicorn (pour la production).

## ⚙️ Prérequis

* Python 3.8+
* Compte Cloudflare (pour le bucket R2)
* Base de données MySQL

## 📦 Installation

1.  **Cloner le projet**
    ```bash
    git clone https://github.com/rudimah/Mimatflix
    cd mimatflix
    ```

2.  **Créer un environnement virtuel**
    ```bash
    python -m venv venv
    # Sur Windows
    venv\Scripts\activate
    # Sur Mac/Linux
    source venv/bin/activate
    ```

3.  **Installer les dépendances**
    ```bash
    pip install -r requirements.txt
    ```



4.  **Variables d'environnement**
    Le projet utilise des variables d'environnement pour la connexion BD et Cloudflare R2.
    
    Créez un fichier `.env` à la racine ([Voir l'example](.env.example)) 

## ▶️ Lancement

Pour lancer l'application en mode développement :

```bash
python app.py