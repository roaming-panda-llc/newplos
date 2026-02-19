def describe_home_page():
    def it_returns_200(client):
        response = client.get("/")
        assert response.status_code == 200

    def it_uses_home_template(client):
        response = client.get("/")
        assert "home.html" in [t.name for t in response.templates]

    def it_uses_base_template(client):
        response = client.get("/")
        assert "base.html" in [t.name for t in response.templates]

    def it_contains_past_lives_text(client):
        response = client.get("/")
        assert b"Past Lives Makerspace" in response.content
