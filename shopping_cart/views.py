
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from products.models import Product


def cart_detail(request):
    cart = request.session.get("shopping_cart", {})
    items = []
    total = Decimal("0.00")
    cleaned_cart = {}

    for product_id, quantity in cart.items():
        try:
            product = Product.objects.select_related("category").get(
                id=int(product_id),
                is_active=True,
                category__is_active=True,
            )
            quantity = int(quantity)
        except (Product.DoesNotExist, ValueError, TypeError):
            continue

        if quantity < 1 or product.stock < 1:
            continue

        quantity = min(quantity, product.stock)
        subtotal = product.price * quantity

        cleaned_cart[str(product.id)] = quantity

        items.append({
            "product": product,
            "quantity": quantity,
            "subtotal": subtotal,
        })
        total += subtotal

    if cleaned_cart != cart:
        request.session["shopping_cart"] = cleaned_cart
        request.session.modified = True

    return render(request, "shopping_cart/cart_detail.html", {
        "items": items,
        "total": total,
    })


@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(
        Product,
        id=product_id,
        is_active=True,
        category__is_active=True,
    )

    if product.stock > 0:
        cart = request.session.get("shopping_cart", {})
        key = str(product.id)

        current_quantity = int(cart.get(key, 0))
        cart[key] = min(current_quantity + 1, product.stock)

        request.session["shopping_cart"] = cart
        request.session.modified = True

    return redirect("cart:detail")


@require_POST
def update_cart(request, product_id):
    product = get_object_or_404(
        Product,
        id=product_id,
        is_active=True,
        category__is_active=True,
    )

    cart = request.session.get("shopping_cart", {})
    key = str(product.id)

    if key not in cart:
        return redirect("shopping_cart:detail")

    try:
        quantity = int(request.POST.get("quantity", 1))
    except (ValueError, TypeError):
        quantity = 1

    if quantity <= 0 or product.stock <= 0:
        cart.pop(key, None)
    else:
        cart[key] = min(quantity, product.stock)

    request.session["shopping_cart"] = cart
    request.session.modified = True

    return redirect("shopping_cart:detail")


@require_POST
def remove_from_cart(request, product_id):
    cart = request.session.get("shopping_cart", {})
    cart.pop(str(product_id), None)

    request.session["shopping_cart"] = cart
    request.session.modified = True

    return redirect("shopping_cart:detail")