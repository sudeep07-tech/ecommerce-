
from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    # My Orders page
    path(
        "",
        views.my_orders,
        name="my_orders",
    ),

    # Checkout page
    path(
        "checkout/",
        views.checkout,
        name="checkout",
    ),

    # Payment method selection
    path(
        "payment-method/",
        views.payment_method,
        name="payment_method",
    ),

    # Order success page
    path(
        "success/<int:order_id>/",
        views.order_success,
        name="success",
    ),

    # Track order page
    path(
        "track/",
        views.track_order,
        name="track",
    ),

    # Cancel order
    path(
        "cancel/<int:order_id>/",
        views.cancel_order,
        name="cancel_order",
    ),
]
