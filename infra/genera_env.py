# Llena en infra/.env las contraseñas que usa el compose y que todavía están vacías, con
# valores aleatorios. No toca las que ya tienen valor y nunca imprime una: solo dice cuáles
# agregó. Si infra/.env no existe, parte de infra/.env.example.
#
#     python infra/genera_env.py
import re
import secrets
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SECRETAS = re.compile(
    r"\$\{(REDIS_PASSWORD|JWT_SECRET_KEY|POSTGRES_PASSWORD|EPIDEMIA_APP_PASSWORD|DB_PASSWORD_[A-Z_]+)\b")


def main(ruta):
    nombres = sorted(set(SECRETAS.findall((AQUI / "docker-compose.yml").read_text(encoding="utf-8"))))
    origen = ruta if ruta.exists() else AQUI / ".env.example"
    lineas = origen.read_text(encoding="utf-8").splitlines()
    existentes = {}
    for i, linea in enumerate(lineas):
        m = re.match(r"([A-Z_]+)=(.*)$", linea)
        if m:
            existentes[m.group(1)] = (i, m.group(2).strip())

    agregadas, con_encabezado = [], False
    for nombre in nombres:
        posicion, valor = existentes.get(nombre, (None, ""))
        if valor:
            continue
        # token_urlsafe solo usa letras, números, "-" y "_": no rompe las URL de conexión.
        nueva = "%s=%s" % (nombre, secrets.token_urlsafe(32))
        if posicion is not None:
            lineas[posicion] = nueva
        else:
            if not con_encabezado:
                lineas += ["", "# --- Generadas por infra/genera_env.py " + "-" * 51]
                con_encabezado = True
            lineas.append(nueva)
        agregadas.append(nombre)

    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    print("%s: %d contraseñas nuevas%s" % (ruta, len(agregadas), (": " + ", ".join(agregadas)) if agregadas else ""))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else AQUI / ".env")
