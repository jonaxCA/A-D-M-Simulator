import os

from dotenv import load_dotenv

# Se carga aqui porque Config se lee ANTES de importar backend_web (que es
# donde db.py hacia load_dotenv en el monolito plano).
load_dotenv()


class Config:
    # Mismo secreto para la cookie de flash() y para firmar el JWT, como en app.py.
    # Sin valor por omision: create_app() lo vuelve a pedir con
    # backend_web.auth.secreto_jwt(), que se niega a arrancar si falta.
    SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
