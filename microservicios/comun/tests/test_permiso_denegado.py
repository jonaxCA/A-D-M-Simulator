from epidemia_comun import auditoria as audit


def test_un_403_queda_en_la_bitacora(crear_cliente, token, negados):
    cliente = crear_cliente("roles")
    r = cliente.get("/api/v1/roles?format=json", headers=token(roles=("EPIDEMIOLOGO",)))
    assert r.status_code == 403
    assert negados == [(7, "PERMISSION_DENIED", "roles", "/api/v1/roles",
                        {"metodo": "GET", "roles_requeridos": ["ADMINISTRADOR"]})]


def test_con_el_rol_no_se_anota_nada(crear_cliente, token, negados, monkeypatch):
    from microservicios.roles import rutas
    monkeypatch.setattr(rutas, "catalogo_roles", lambda: [])
    cliente = crear_cliente("roles")
    assert cliente.get("/api/v1/roles?format=json",
                       headers=token(roles=("ADMINISTRADOR",))).status_code == 200
    assert negados == []


def test_sin_token_es_401_y_no_se_anota(crear_cliente, negados):
    assert crear_cliente("roles").get("/api/v1/roles?format=json").status_code == 401
    assert negados == []


def test_si_la_bitacora_falla_el_403_sale_igual(crear_cliente, token, monkeypatch):
    def caida(*_, **__):
        raise ConnectionError("PostgreSQL apagado")
    monkeypatch.setattr(audit, "log_audit", caida)
    r = crear_cliente("roles").get("/api/v1/roles?format=json", headers=token(roles=("ANALISTA",)))
    assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE"
