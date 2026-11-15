from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"^ws/owner/?$", consumers.OwnerConsumer.as_asgi()),
    re_path(r"^ws/order/(?P<order_number>[\w-]+)/?$", consumers.CustomerOrderConsumer.as_asgi()),
    # A-51 (RUN8 G3b): platform-admin channel — IsPlatformAdmin-gated in the consumer.
    re_path(r"^ws/admin/?$", consumers.AdminConsumer.as_asgi()),
]
