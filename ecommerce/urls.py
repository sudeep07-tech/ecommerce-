from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from dashboard.views import customer_dashboard

urlpatterns = [
    # Django admin
    path("django-admin/", admin.site.urls),

    # User accounts: Login, Register, and Logout
    path("accounts/", include("accounts.urls")),

    # Customer dashboard
    path(
        "customer-dashboard/",
        customer_dashboard,
        name="customer_dashboard",
    ),

    # Homepage, product listing, and search
    path("", include("products.urls")),

    # Shopping cart
    path("cart/", include("cart.urls")),

    # Checkout and order tracking
    path("orders/", include("orders.urls")),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
