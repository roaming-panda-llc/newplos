from unittest.mock import patch

from django.apps import apps

from core.apps import CoreConfig


def describe_core_config():
    def it_has_correct_app_name():
        assert CoreConfig.name == "core"

    def it_has_correct_default_auto_field():
        assert CoreConfig.default_auto_field == "django.db.models.BigAutoField"

    def describe_ready():
        def it_calls_register_all_models():
            with patch("newplos.auto_admin.register_all_models") as mock_register:
                config = apps.get_app_config("core")
                config.ready()
                mock_register.assert_called_once()
