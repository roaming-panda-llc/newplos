"""Middleware to add Service-Worker-Allowed header for PWA support."""

from django.http import HttpRequest, HttpResponseBase


class ServiceWorkerAllowedMiddleware:
    """
    Add Service-Worker-Allowed header for service worker requests.

    This allows the service worker at /static/js/sw.js to control the entire
    application (scope '/') rather than just /static/js/* paths.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        response = self.get_response(request)

        # Add header for service worker file to allow root scope
        if request.path == "/static/js/sw.js":
            response["Service-Worker-Allowed"] = "/"

        return response
