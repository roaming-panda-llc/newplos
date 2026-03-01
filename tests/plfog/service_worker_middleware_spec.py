"""Tests for ServiceWorkerAllowedMiddleware."""

from django.test import Client

import pytest


def describe_service_worker_allowed_middleware():
    """Test the ServiceWorkerAllowedMiddleware adds correct header."""

    @pytest.fixture
    def client():
        return Client()

    def it_adds_service_worker_allowed_header_for_sw_js(client):
        """Test that requesting /static/js/sw.js adds the Service-Worker-Allowed header."""
        response = client.get("/static/js/sw.js")
        assert response.status_code == 200
        assert response["Service-Worker-Allowed"] == "/"

    def it_does_not_add_header_for_other_paths(client):
        """Test that other paths do not get the Service-Worker-Allowed header."""
        response = client.get("/")
        assert response.status_code == 200
        assert "Service-Worker-Allowed" not in response

    def it_does_not_add_header_for_other_static_files(client):
        """Test that other static files do not get the header."""
        response = client.get("/static/js/other.js")
        # May 404 or 200 depending on static file config, but header should not be set
        assert "Service-Worker-Allowed" not in response
