from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"^ws/owner/?$", consumers.OwnerConsumer.as_asgi()),
    re_path(r"^ws/order/(?P<order_number>[\w-]+)/?$", consumers.CustomerOrderConsumer.as_asgi()),
]
