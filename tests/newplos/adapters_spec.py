"""BDD-style tests for newplos.adapters module — auto-admin on social login."""

import logging
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User

pytestmark = pytest.mark.django_db


def _make_social_login(email: str) -> MagicMock:
    """Create a mock sociallogin object with the given email."""
    mock_sociallogin = MagicMock()
    mock_sociallogin.user = User(email=email, username=email.split("@")[0])
    mock_sociallogin.account = MagicMock()
    mock_sociallogin.email_addresses = []
    mock_sociallogin.token = MagicMock()
    return mock_sociallogin


def _patch_super_save_user(email: str, username: str):
    """Return a context manager that patches DefaultSocialAccountAdapter.save_user."""
    from newplos.adapters import AutoAdminSocialAccountAdapter

    mock_user = User(email=email, username=username)
    mock_user.pk = 1
    mock_user.save = MagicMock()
    return patch.object(
        AutoAdminSocialAccountAdapter.__bases__[0],
        "save_user",
        return_value=mock_user,
    )


def describe_save_user_with_empty_admin_domains():
    def it_does_not_grant_admin(rf, settings):
        from newplos.adapters import AutoAdminSocialAccountAdapter

        settings.ADMIN_DOMAINS = []
        adapter = AutoAdminSocialAccountAdapter()
        request = rf.get("/")

        with _patch_super_save_user("user@example.com", "user"):
            user = adapter.save_user(request, _make_social_login("user@example.com"))

        assert user.is_staff is False
        assert user.is_superuser is False


def describe_save_user_with_matching_domain():
    def it_grants_admin_privileges(rf, settings):
        from newplos.adapters import AutoAdminSocialAccountAdapter

        settings.ADMIN_DOMAINS = ["example.com"]
        adapter = AutoAdminSocialAccountAdapter()
        request = rf.get("/")

        with _patch_super_save_user("user@example.com", "user"):
            user = adapter.save_user(request, _make_social_login("user@example.com"))

        assert user.is_staff is True
        assert user.is_superuser is True
        user.save.assert_called_once_with(update_fields=["is_staff", "is_superuser"])

    def it_does_not_grant_admin_when_domain_does_not_match(rf, settings):
        from newplos.adapters import AutoAdminSocialAccountAdapter

        settings.ADMIN_DOMAINS = ["example.com"]
        adapter = AutoAdminSocialAccountAdapter()
        request = rf.get("/")

        with _patch_super_save_user("user@other.com", "user"):
            user = adapter.save_user(request, _make_social_login("user@other.com"))

        assert user.is_staff is False
        assert user.is_superuser is False


def describe_save_user_with_multiple_domains():
    def it_grants_admin_for_any_matching_domain(rf, settings):
        from newplos.adapters import AutoAdminSocialAccountAdapter

        settings.ADMIN_DOMAINS = ["pastlives.space", "roaming-panda.com"]
        adapter = AutoAdminSocialAccountAdapter()
        request = rf.get("/")

        with _patch_super_save_user("mark@roaming-panda.com", "mark"):
            user = adapter.save_user(request, _make_social_login("mark@roaming-panda.com"))

        assert user.is_staff is True
        assert user.is_superuser is True


def describe_save_user_case_insensitivity():
    def it_matches_uppercase_email_domain(rf, settings):
        from newplos.adapters import AutoAdminSocialAccountAdapter

        settings.ADMIN_DOMAINS = ["pastlives.space"]
        adapter = AutoAdminSocialAccountAdapter()
        request = rf.get("/")

        with _patch_super_save_user("User@PASTLIVES.SPACE", "User"):
            user = adapter.save_user(request, _make_social_login("User@PASTLIVES.SPACE"))

        assert user.is_staff is True
        assert user.is_superuser is True


def describe_maybe_grant_admin_edge_cases():
    def it_skips_user_with_empty_email(settings):
        from newplos.adapters import AutoAdminSocialAccountAdapter

        settings.ADMIN_DOMAINS = ["example.com"]
        adapter = AutoAdminSocialAccountAdapter()

        user = MagicMock()
        user.email = ""
        adapter._maybe_grant_admin(user)

        user.save.assert_not_called()

    def it_skips_user_with_email_without_at_sign(settings):
        from newplos.adapters import AutoAdminSocialAccountAdapter

        settings.ADMIN_DOMAINS = ["example.com"]
        adapter = AutoAdminSocialAccountAdapter()

        user = MagicMock()
        user.email = "noemail"
        adapter._maybe_grant_admin(user)

        user.save.assert_not_called()

    def it_skips_user_with_none_email(settings):
        from newplos.adapters import AutoAdminSocialAccountAdapter

        settings.ADMIN_DOMAINS = ["example.com"]
        adapter = AutoAdminSocialAccountAdapter()

        user = MagicMock()
        user.email = None
        adapter._maybe_grant_admin(user)

        user.save.assert_not_called()

    def it_skips_when_admin_domains_not_configured(settings):
        from newplos.adapters import AutoAdminSocialAccountAdapter

        if hasattr(settings, "ADMIN_DOMAINS"):
            delattr(settings, "ADMIN_DOMAINS")
        adapter = AutoAdminSocialAccountAdapter()

        user = MagicMock()
        user.email = "user@example.com"
        adapter._maybe_grant_admin(user)

        user.save.assert_not_called()


def describe_maybe_grant_admin_matching():
    def it_sets_is_staff_and_is_superuser(settings):
        from newplos.adapters import AutoAdminSocialAccountAdapter

        settings.ADMIN_DOMAINS = ["example.com"]
        adapter = AutoAdminSocialAccountAdapter()

        user = MagicMock()
        user.email = "admin@example.com"
        adapter._maybe_grant_admin(user)

        assert user.is_staff is True
        assert user.is_superuser is True
        user.save.assert_called_once_with(update_fields=["is_staff", "is_superuser"])

    def it_does_not_match_subdomains(settings):
        from newplos.adapters import AutoAdminSocialAccountAdapter

        settings.ADMIN_DOMAINS = ["example.com"]
        adapter = AutoAdminSocialAccountAdapter()

        user = MagicMock()
        user.email = "user@sub.example.com"
        adapter._maybe_grant_admin(user)

        user.save.assert_not_called()


def describe_maybe_grant_admin_logging():
    def it_logs_when_admin_is_granted(settings, caplog):
        from newplos.adapters import AutoAdminSocialAccountAdapter

        settings.ADMIN_DOMAINS = ["example.com"]
        adapter = AutoAdminSocialAccountAdapter()

        user = MagicMock()
        user.email = "admin@example.com"

        with caplog.at_level(logging.INFO, logger="newplos.adapters"):
            adapter._maybe_grant_admin(user)

        assert "Auto-admin granted to admin@example.com" in caplog.text
        assert "domain: example.com" in caplog.text
