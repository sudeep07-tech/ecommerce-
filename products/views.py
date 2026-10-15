
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db.models import Q

from products.models import Product
from categories.models import Category
from reviews.models import Review
from reviews.forms import ReviewForm


# ==========================================
# PRODUCT NAME SEARCH SUGGESTIONS
# ==========================================
def product_name_suggestions(request):
    query = request.GET.get("q", "").strip()

    # Wait until the customer types at least 2 characters
    if len(query) < 2:
        return JsonResponse({"suggestions": []})

    # Return up to 8 matching active product names
    products = (
        Product.objects.filter(
            name__icontains=query,
            is_active=True,
            category__is_active=True,
        )
        .order_by("name")
        .values_list("name", flat=True)
        .distinct()[:8]
    )

    return JsonResponse({
        "suggestions": list(products)
    })


# ==========================================
# PRODUCT LIST
# ==========================================
def product_list(request):
    products = Product.objects.select_related("category").filter(
        is_active=True,
        category__is_active=True,
    )

    categories = Category.objects.filter(is_active=True)

    # Search products by name or description
    search_query = request.GET.get("q", "").strip()

    # Selected category filter
    selected_category = request.GET.get(
        "category", ""
    ).strip()

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
        )

    # Filter by category while preserving search
    if selected_category:
        products = products.filter(
            category__slug=selected_category
        )

    context = {
        "products": products.distinct(),
        "categories": categories,
        "search_query": search_query,
        "selected_category": selected_category,
    }

    return render(
        request,
        "products/product_list.html",
        context,
    )


# ==========================================
# PRODUCT DETAIL
# ==========================================
def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("category"),
        slug=slug,
        is_active=True,
        category__is_active=True,
    )

    reviews = Review.objects.filter(
        product=product
    ).order_by("-id")

    review_form = ReviewForm()

    if request.method == "POST":
        review_form = ReviewForm(request.POST)

        if review_form.is_valid():
            review = review_form.save(commit=False)
            review.product = product
            review.save()

            messages.success(
                request,
                "Your review has been submitted!",
            )

            return redirect(
                "products:detail",
                slug=product.slug,
            )

    average_rating = None

    if reviews.exists():
        average_rating = sum(
            review.rating for review in reviews
        ) / reviews.count()

    context = {
        "product": product,
        "reviews": reviews,
        "review_form": review_form,
        "average_rating": average_rating,
        "review_count": reviews.count(),
    }

    return render(
        request,
        "products/product_detail.html",
        context,
    )


# ==========================================
# BUY NOW
# ==========================================
@require_POST
def buy_now(request, product_id):
    product = get_object_or_404(
        Product,
        pk=product_id,
        is_active=True,
        category__is_active=True,
    )

    try:
        quantity = int(
            request.POST.get("quantity", 1)
        )
    except (ValueError, TypeError):
        quantity = 1

    if quantity < 1:
        messages.error(
            request,
            "Please select a valid quantity.",
        )
        return redirect(
            "products:detail",
            slug=product.slug,
        )

    if quantity > product.stock:
        messages.error(
            request,
            f"Only {product.stock} item(s) are available.",
        )
        return redirect(
            "products:detail",
            slug=product.slug,
        )

    cart = request.session.get(
        "shopping_cart", {}
    )

    cart[str(product.id)] = quantity

    request.session["shopping_cart"] = cart
    request.session.modified = True

    return redirect("orders:checkout")
