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


def test_forgot_password_get_route(client):
    res = client.get("/forgot-password")
    assert res.status_code == 200
    assert "Recuperar Contraseña".encode("utf-8") in res.data


def test_forgot_password_post_registered_and_unregistered_identical_neutral_response(client):
    client.post("/register", data={
        "email": "registered_user@example.com",
        "password": "validpassword123"
    })

    neutral_msg = "Si la dirección de correo electrónico está registrada en el sistema, se ha enviado un enlace para restablecer la contraseña."

    # 1. Registered email
    res_reg = client.post("/forgot-password", data={"email": "registered_user@example.com"}, follow_redirects=True)
    assert res_reg.status_code == 200
    assert neutral_msg.encode("utf-8") in res_reg.data

    # 2. Unregistered email
    res_unreg = client.post("/forgot-password", data={"email": "unregistered_user@example.com"}, follow_redirects=True)
    assert res_unreg.status_code == 200
    assert neutral_msg.encode("utf-8") in res_unreg.data

    # HTML responses must not expose any hashes or user passwords
    assert b"password_hash" not in res_reg.data
    assert b"validpassword123" not in res_reg.data



def test_token_never_exposed_in_html_or_json_responses(client, user_service):
    user = user_service.register_user("secure_token_user@example.com", "password123")

    # Spy to capture the exact raw token issued
    captured_tokens = []
    original_send = user_service.notification_service.send_password_reset_link
    def spy_send(email, url):
        token_part = url.split("/reset-password/")[-1]
        captured_tokens.append(token_part)
        return original_send(email, url)

    user_service.notification_service.send_password_reset_link = spy_send

    # 1. HTML request
    res_html = client.post("/forgot-password", data={"email": "secure_token_user@example.com"}, follow_redirects=True)
    assert res_html.status_code == 200
    html_content = res_html.get_data(as_text=True)

    # 2. JSON request
    res_json = client.post("/forgot-password", json={"email": "secure_token_user@example.com"})
    assert res_json.status_code == 200
    json_text = res_json.get_data(as_text=True)
    json_data = res_json.get_json()

    # Verify each issued raw token and hash NEVER appears in HTML or JSON response bodies
    from src.infrastructure.models import PasswordResetTokenORM
    tokens_in_db = user_service.session.query(PasswordResetTokenORM).filter_by(user_id=user.id).all()
    assert len(tokens_in_db) > 0

    for token_orm in tokens_in_db:
        assert token_orm.token_hash not in html_content
        assert token_orm.token_hash not in json_text

    for raw_tok in captured_tokens:
        assert raw_tok not in html_content
        assert raw_tok not in json_text

    assert "token" not in json_data
    assert "token_hash" not in json_data


def test_forgot_password_post_invalid_email_format(client):
    res = client.post("/forgot-password", data={"email": "invalid-email-format"}, follow_redirects=True)
    assert res.status_code == 400
    assert "correo electrónico".encode("utf-8") in res.data


def test_forgot_password_api_json(client):
    neutral_msg = "Si la dirección de correo electrónico está registrada en el sistema, se ha enviado un enlace para restablecer la contraseña."

    res = client.post("/forgot-password", json={"email": "api_user@example.com"})
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["status"] == "success"
    assert json_data["message"] == neutral_msg

    # Invalid email format via JSON
    res_invalid = client.post("/forgot-password", json={"email": "bad_email"})
    assert res_invalid.status_code == 400
    assert res_invalid.get_json()["status"] == "error"


def test_reset_password_get_valid_token(client, user_service):
    user_service.register_user("reset_get_user@example.com", "validpassword123")
    token = user_service.request_password_reset("reset_get_user@example.com")

    res = client.get(f"/reset-password/{token}")
    assert res.status_code == 200
    assert "Restablecer Contraseña".encode("utf-8") in res.data
    assert "Nueva Contraseña".encode("utf-8") in res.data



def test_reset_password_get_invalid_or_expired_token(client):
    res = client.get("/reset-password/fake_nonexistent_token_123", follow_redirects=False)
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_reset_password_post_success(client, user_service):
    user_service.register_user("reset_post_user@example.com", "oldpassword123")
    token = user_service.request_password_reset("reset_post_user@example.com")

    res = client.post(f"/reset-password/{token}", data={
        "password": "brandnewpassword123",
        "password_confirm": "brandnewpassword123"
    }, follow_redirects=False)
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]

    # Now verify login with the new password
    login_res = client.post("/login", data={
        "email": "reset_post_user@example.com",
        "password": "brandnewpassword123"
    }, follow_redirects=True)
    assert login_res.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get("user_email") == "reset_post_user@example.com"


def test_reset_password_post_validation_mismatch_and_short(client, user_service):
    user_service.register_user("reset_err_user@example.com", "oldpassword123")
    token = user_service.request_password_reset("reset_err_user@example.com")

    # Mismatched passwords
    res_mismatch = client.post(f"/reset-password/{token}", data={
        "password": "newpassword123",
        "password_confirm": "different123"
    }, follow_redirects=True)
    assert res_mismatch.status_code == 400
    assert "no coinciden".encode("utf-8") in res_mismatch.data

    # Short password (< 8)
    res_short = client.post(f"/reset-password/{token}", data={
        "password": "short",
        "password_confirm": "short"
    }, follow_redirects=True)
    assert res_short.status_code == 400
    assert "al menos 8 caracteres".encode("utf-8") in res_short.data


def test_reset_password_api_json(client, user_service):
    user_service.register_user("reset_api_user@example.com", "oldpassword123")
    token = user_service.request_password_reset("reset_api_user@example.com")

    # Successful reset via JSON
    res = client.post(f"/reset-password/{token}", json={
        "password": "apipassword123",
        "password_confirm": "apipassword123"
    })
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["status"] == "success"
    assert "Contraseña actualizada exitosamente" in json_data["message"]

    # Second attempt with consumed token must return 400
    res_consumed = client.post(f"/reset-password/{token}", json={
        "password": "anotherpassword123",
        "password_confirm": "anotherpassword123"
    })
    assert res_consumed.status_code == 400
    assert res_consumed.get_json()["status"] == "error"


def test_login_page_contains_forgot_password_link(client):
    res = client.get("/login")
    assert res.status_code == 200
    assert b"/forgot-password" in res.data


def test_forgot_password_delivery_disabled_does_not_issue_or_revoke_token(app, client, user_service):
    # Temporarily disable delivery mechanism in app config
    app.config["ENABLE_CONSOLE_PASSWORD_RESET"] = False
    try:
        user = user_service.register_user("no_delivery_route@example.com", "password123")

        # HTML request
        res_html = client.post("/forgot-password", data={"email": "no_delivery_route@example.com"}, follow_redirects=True)
        assert res_html.status_code == 200
        neutral_msg = "Si la dirección de correo electrónico está registrada en el sistema, se ha enviado un enlace para restablecer la contraseña."
        assert neutral_msg.encode("utf-8") in res_html.data

        # Verify no token was created in the database
        from src.infrastructure.models import PasswordResetTokenORM
        tokens = user_service.session.query(PasswordResetTokenORM).filter_by(user_id=user.id).all()
        assert len(tokens) == 0
    finally:
        app.config["ENABLE_CONSOLE_PASSWORD_RESET"] = True


