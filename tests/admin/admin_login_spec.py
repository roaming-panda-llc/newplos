import pytest

pytestmark = pytest.mark.django_db


def describe_admin_login_page():
    def it_returns_200(client):
        response = client.get("/admin/login/")
        assert response.status_code == 200

    def it_contains_google_sign_in_link(client):
        response = client.get("/admin/login/")
        content = response.content.decode()
        assert "/accounts/google/login/?process=login" in content
        assert "next=/admin/" in content

    def it_contains_sign_in_with_google_text(client):
        response = client.get("/admin/login/")
        assert b"Sign in with Google" in response.content

    def it_contains_password_form(client):
        response = client.get("/admin/login/")
        content = response.content.decode()
        assert 'id="login-form"' in content
        assert 'type="password"' in content
