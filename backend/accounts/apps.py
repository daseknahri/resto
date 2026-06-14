from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        # A7: register the deployment system checks (Redis/Celery presence in prod).
        # Importing the module runs its @register(deploy=True) decorators.
        from config import checks  # noqa: F401
