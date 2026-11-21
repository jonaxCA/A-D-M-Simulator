"""El perfil de la app móvil: cada cuenta consulta la suya, con la base y el rol svc_usuarios reales."""


def test_la_capturista_consulta_su_perfil_y_no_el_de_otros(api, sesion):
    propia = sesion("capturista")
    r = api("usuarios", "GET", "/api/v1/users/me", propia["access"])
    assert r.status_code == 200, r.text
    perfil = r.json()
    assert (perfil["id"], perfil["username"], perfil["roles"]) == (
        propia["id"], "karla.trevino", ["CAPTURISTA"])
    assert "password_hash" not in perfil
    assert api("usuarios", "GET", "/api/v1/users/%d" % propia["id"],
               propia["access"]).status_code == 403
