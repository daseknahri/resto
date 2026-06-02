from django.apps import AppConfig


class MenuConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "menu"

    def ready(self):
        # Register signal handlers (order → public-schema order index mirror).
        from . import signals  # noqa: F401
