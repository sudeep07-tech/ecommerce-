
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def customer_dashboard(request):
    context = {
        "total_orders": 0,
        "pending_orders": 0,
        "completed_orders": 0,
        "wishlist_count": 0,
        "recent_orders": [],
    }

    return render(
        request,
        "dashboard/customer_dashboard.html",
        context,
    )
