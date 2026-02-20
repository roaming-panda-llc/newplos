"""Custom allauth adapters for auto-admin domain privileges."""

import logging

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.http import HttpRequest

logger = logging.getLogger(__name__)


class AutoAdminSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Grant admin privileges to users whose email domain is in ADMIN_DOMAINS.

    On social login, if the user's email domain matches any domain in the
    ADMIN_DOMAINS setting (case-insensitive), the user gets is_staff=True
    and is_superuser=True.

    Users with non-matching domains are not modified — existing admin users
    who log in from a non-listed domain keep whatever privileges they had.
    """

    def save_user(self, request: HttpRequest, sociallogin: object, form: object = None) -> object:
        """Save user and grant admin privileges if email domain matches."""
        user = super().save_user(request, sociallogin, form=form)
        self._maybe_grant_admin(user)
        return user

    def _maybe_grant_admin(self, user: object) -> None:
        """Check user's email domain and grant admin if it matches ADMIN_DOMAINS."""
        admin_domains: list[str] = getattr(settings, "ADMIN_DOMAINS", [])
        if not admin_domains:
            return

        email: str = getattr(user, "email", "") or ""
        if not email or "@" not in email:
            return

        domain = email.rsplit("@", 1)[1].lower()
        if domain in admin_domains:
            user.is_staff = True  # type: ignore[attr-defined]
            user.is_superuser = True  # type: ignore[attr-defined]
            user.save(update_fields=["is_staff", "is_superuser"])  # type: ignore[attr-defined]
            logger.info("Auto-admin granted to %s (domain: %s)", email, domain)
