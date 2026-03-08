import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from config.sentry import init_sentry

init_sentry()
application = get_asgi_application()
