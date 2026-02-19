"""WSGI config for newplos project."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "newplos.settings")

application = get_wsgi_application()
