
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def wishlist_view(request):
    return render(request, "wishlist/wishlist.html")
