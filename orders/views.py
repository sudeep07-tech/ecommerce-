
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from products.models import Product
from .models import Order, OrderItem


# Delivery settings
FREE_DELIVERY_THRESHOLD = Decimal("20000.00")
DELIVERY_CHARGE = Decimal("200.00")


# Order tracking progress
TRACKING_STEPS = [
    ("pending", "Order placed", "We've received your order."),
    ("processing", "Processing", "Your order is being prepared."),
    ("shipped", "Shipped", "Your order is on its way."),
    ("delivered", "Delivered", "Your order has arrived."),
]


# ==========================================
# CHECKOUT
# ==========================================
def checkout(request):
    cart = request.session.get("shopping_cart", {})

    if not cart:
        messages.error(request, "Your shopping cart is empty.")
        return redirect("cart:detail")

    items = []
    subtotal = Decimal("0.00")

    # Get cart products
    for product_id, quantity in cart.items():
        try:
            product = Product.objects.get(
                pk=int(product_id),
                is_active=True,
                category__is_active=True,
            )
            quantity = int(quantity)

        except (Product.DoesNotExist, ValueError, TypeError):
            messages.error(
                request,
                "A product in your cart is no longer available.",
            )
            return redirect("cart:detail")

        if quantity < 1 or quantity > product.stock:
            messages.error(
                request,
                f"Please check the quantity for {product.name}.",
            )
            return redirect("cart:detail")

        item_subtotal = product.price * quantity

        items.append({
            "product": product,
            "quantity": quantity,
            "subtotal": item_subtotal,
        })

        subtotal += item_subtotal

    # Calculate delivery charges
    free_delivery = subtotal >= FREE_DELIVERY_THRESHOLD

    delivery_charge = (
        Decimal("0.00")
        if free_delivery
        else DELIVERY_CHARGE
    )

    total = subtotal + delivery_charge

    context = {
        "items": items,
        "subtotal": subtotal,
        "delivery_charge": delivery_charge,
        "shipping": delivery_charge,
        "free_delivery": free_delivery,
        "free_delivery_threshold": FREE_DELIVERY_THRESHOLD,
        "total": total,
    }

    # Process checkout form
    if request.method == "POST":
        customer_name = request.POST.get(
            "customer_name", ""
        ).strip()

        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        address = request.POST.get("address", "").strip()
        city = request.POST.get("city", "").strip()
        postal_code = request.POST.get("postal_code", "").strip()

        if not all([
            customer_name,
            email,
            phone,
            address,
            city,
        ]):
            messages.error(
                request,
                "Please fill in all required delivery details.",
            )
            return render(
                request,
                "orders/checkout.html",
                context,
            )

        try:
            with transaction.atomic():
                verified_subtotal = Decimal("0.00")
                verified_items = []

                # Recheck product prices and stock
                for product_id, quantity in cart.items():
                    product = Product.objects.select_for_update().get(
                        pk=int(product_id),
                        is_active=True,
                        category__is_active=True,
                    )

                    quantity = int(quantity)

                    if quantity < 1 or quantity > product.stock:
                        raise ValueError(
                            f"Not enough stock for {product.name}."
                        )

                    line_total = product.price * quantity
                    verified_subtotal += line_total

                    verified_items.append({
                        "product": product,
                        "quantity": quantity,
                        "subtotal": line_total,
                    })

                # Recalculate delivery using verified prices
                verified_free_delivery = (
                    verified_subtotal >= FREE_DELIVERY_THRESHOLD
                )

                verified_delivery = (
                    Decimal("0.00")
                    if verified_free_delivery
                    else DELIVERY_CHARGE
                )

                verified_total = (
                    verified_subtotal + verified_delivery
                )

                # Create order
                order = Order.objects.create(
                    customer_name=customer_name,
                    email=email,
                    phone=phone,
                    address=address,
                    city=city,
                    postal_code=postal_code,
                    status="pending",
                    total_amount=verified_total,
                )

                # Save order items and reduce stock
                for item in verified_items:
                    product = item["product"]
                    quantity = item["quantity"]

                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        product_name=product.name,
                        unit_price=product.price,
                        quantity=quantity,
                        subtotal=item["subtotal"],
                    )

                    product.stock -= quantity
                    product.save(update_fields=["stock"])

        except (
            Product.DoesNotExist,
            ValueError,
            TypeError,
        ) as exc:
            messages.error(
                request,
                str(exc) or "Unable to place your order.",
            )
            return redirect("cart:detail")

        # Empty the cart after a successful order
        request.session["shopping_cart"] = {}
        request.session.modified = True

        return redirect(
            "orders:success",
            order_id=order.id,
        )

    return render(
        request,
        "orders/checkout.html",
        context,
    )


# ==========================================
# ORDER SUCCESS
# ==========================================
def order_success(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items"),
        pk=order_id,
    )

    subtotal = sum(
        (item.subtotal for item in order.items.all()),
        Decimal("0.00"),
    )

    delivery_charge = order.total_amount - subtotal

    return render(
        request,
        "orders/order_success.html",
        {
            "order": order,
            "subtotal": subtotal,
            "delivery_charge": delivery_charge,
        },
    )


# ==========================================
# TRACK ORDER
# ==========================================
def track_order(request):
    order = None
    error_message = None
    current_step = 0

    if request.method == "POST":
        order_number = request.POST.get(
            "order_number", ""
        ).strip()

        email = request.POST.get(
            "email", ""
        ).strip()

        if not order_number or not email:
            error_message = (
                "Please enter both your order number "
                "and email address."
            )

        else:
            try:
                order_id = int(order_number)

                order = (
                    Order.objects
                    .prefetch_related("items")
                    .filter(
                        pk=order_id,
                        email__iexact=email,
                    )
                    .first()
                )

                if order is None:
                    error_message = (
                        "We couldn't find an order matching "
                        "those details. Please check your "
                        "order number and email."
                    )

                else:
                    # Store the verified order and email
                    # for the cancellation view.
                    request.session["tracking_order_id"] = order.pk
                    request.session["tracking_email"] = order.email
                    request.session.modified = True

                    if order.status != "cancelled":
                        status_order = [
                            "pending",
                            "processing",
                            "shipped",
                            "delivered",
                        ]

                        if order.status in status_order:
                            current_step = status_order.index(
                                order.status
                            )

            except (ValueError, TypeError):
                error_message = (
                    "Please enter a valid order number."
                )

    return render(
        request,
        "orders/track_order.html",
        {
            "order": order,
            "error_message": error_message,
            "tracking_steps": TRACKING_STEPS,
            "current_step": current_step,
        },
    )


# ==========================================
# CANCEL ORDER
# ==========================================
@require_POST
def cancel_order(request, order_id):
    # Ensure the customer has verified this exact order
    tracking_order_id = request.session.get(
        "tracking_order_id"
    )
    tracking_email = request.session.get(
        "tracking_email"
    )

    if tracking_order_id != order_id or not tracking_email:
        messages.error(
            request,
            "Please verify your order number and email "
            "on the tracking page first.",
        )
        return redirect("orders:track")

    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=order_id,
            email__iexact=tracking_email,
        )

        if order.status == "delivered":
            messages.error(
                request,
                "This order cannot be cancelled because "
                "it has already been delivered.",
            )

        elif order.status == "cancelled":
            messages.info(
                request,
                "This order has already been cancelled.",
            )

        else:
            order.status = "cancelled"
            order.save(update_fields=["status"])

            messages.success(
                request,
                "Your order has been cancelled successfully.",
            )

    return redirect("orders:track")
