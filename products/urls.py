
from django.urls import path
from . import views

app_name = "products"

urlpatterns = [
    # Homepage and product search
    path(
        "",
        views.product_list,
        name="list",
    ),

    # Live product-name suggestions
    path(
        "suggestions/",
        views.product_name_suggestions,
        name="product_suggestions",
    ),

    # Product details
    path(
        "product/<slug:slug>/",
        views.product_detail,
        name="detail",
    ),

    # Buy Now
    path(
        "buy/<int:product_id>/",
        views.buy_now,
        name="buy_now",
    ),
]
