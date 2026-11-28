import os

from dotenv import load_dotenv

# Se carga aqui porque Config se lee ANTES de importar backend_web (que es
# donde db.py hacia load_dotenv en el monolito plano).
load_dotenv()


class Config:
    # La cookie firmada de Flask (flash y el nombre de la cuenta). Con D36 la web ya no firma
    # JWT: los emite auth. Mientras no haya SECRET_KEY propio se usa JWT_SECRET_KEY, y
    # create_app() se niega a arrancar si no hay ninguno.
    SECRET_KEY = os.environ.get("SECRET_KEY") or os.environ.get("JWT_SECRET_KEY")
    # El PDF de un reporte pesa hasta 20 MB (D35); el resto, el formulario. Igual que nginx.
    MAX_CONTENT_LENGTH = 21 * 1024 * 1024
