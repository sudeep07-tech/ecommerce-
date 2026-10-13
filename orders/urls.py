
from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    # Checkout page
    path("checkout/", views.checkout, name="checkout"),

    # Order success page
    path(
        "success/<int:order_id>/",
        views.order_success,
        name="success",
    ),

    # Track order page
    path("track/", views.track_order, name="track"),
]