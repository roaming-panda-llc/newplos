import pytest

pytestmark = pytest.mark.django_db


def describe_allauth_urls():
    def it_login_page_returns_200(client):
        response = client.get("/accounts/login/")
        assert response.status_code == 200

    def it_signup_page_returns_200(client):
        response = client.get("/accounts/signup/")
        assert response.status_code == 200

    def it_login_page_uses_custom_template(client):
        response = client.get("/accounts/login/")
        template_names = [t.name for t in response.templates]
        assert "account/login.html" in template_names

    def it_signup_page_uses_custom_template(client):
        response = client.get("/accounts/signup/")
        template_names = [t.name for t in response.templates]
        assert "account/signup.html" in template_names
