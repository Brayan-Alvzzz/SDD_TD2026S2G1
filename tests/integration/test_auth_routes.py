def test_register_route_get(client):
    res = client.get("/register")
    assert res.status_code == 200
    assert b"Registrarse" in res.data


def test_register_route_success(client):
    res = client.post("/register", data={
        "email": "nuevo@example.com",
        "password": "validpassword123"
    }, follow_redirects=True)
    assert res.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get("user_email") == "nuevo@example.com"
        assert sess.get("user_id") is not None


def test_register_route_short_password(client):
    res = client.post("/register", data={
        "email": "nuevo2@example.com",
        "password": "short"
    }, follow_redirects=True)
    assert res.status_code == 400
    assert "al menos 8 caracteres".encode("utf-8") in res.data


def test_register_route_duplicate_email(client):
    client.post("/register", data={
        "email": "dupe@example.com",
        "password": "validpassword123"
    })
    res = client.post("/register", data={
        "email": "dupe@example.com",
        "password": "validpassword123"
    }, follow_redirects=True)
    assert res.status_code == 409
    assert "ya se encuentra registrado".encode("utf-8") in res.data


def test_login_route_success(client):
    client.post("/register", data={
        "email": "login@example.com",
        "password": "validpassword123"
    })
    client.post("/logout")
    res = client.post("/login", data={
        "email": "login@example.com",
        "password": "validpassword123"
    }, follow_redirects=True)
    assert res.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get("user_email") == "login@example.com"


def test_login_route_invalid_credentials(client):
    res = client.post("/login", data={
        "email": "nonexistent@example.com",
        "password": "badpassword"
    }, follow_redirects=True)
    assert res.status_code == 401
    assert "Credenciales incorrectas".encode("utf-8") in res.data


def test_logout_route(client):
    client.post("/register", data={
        "email": "out@example.com",
        "password": "validpassword123"
    })
    res = client.post("/logout", follow_redirects=True)
    assert res.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None
