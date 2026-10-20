
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from products.models import Product
from .models import Order, OrderItem


# Delivery and payment settings
FREE_DELIVERY_THRESHOLD = Decimal("20000.00")
DELIVERY_CHARGE = Decimal("200.00")
COD_CHARGE = Decimal("20.00")


# Order tracking progress
TRACKING_STEPS = [
    ("pending", "Order placed", "We've received your order."),
    ("processing", "Processing", "Your order is being prepared."),
    ("shipped", "Shipped", "Your order is on its way."),
    ("delivered", "Delivered", "Your order has arrived."),
]


# ==========================================
# HELPER: BUILD AND VALIDATE CART
# ==========================================
def _get_cart_items(request):
    cart = request.session.get("shopping_cart", {})

    if not cart:
        messages.error(request, "Your shopping cart is empty.")
        return None

    items = []
    subtotal = Decimal("0.00")

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
            return None

        if quantity < 1 or quantity > product.stock:
            messages.error(
                request,
                f"Please check the quantity for {product.name}.",
            )
            return None

        line_total = product.price * quantity

        items.append({
            "product": product,
            "quantity": quantity,
            "subtotal": line_total,
        })

        subtotal += line_total

    return items, subtotal


def _checkout_totals(subtotal, payment_method="khalti"):
    """
    Calculate delivery and payment totals.

    The COD charge is added only for Cash on Delivery.
    Free delivery is determined by the product subtotal.
    """
    free_delivery = subtotal >= FREE_DELIVERY_THRESHOLD

    delivery_charge = (
        Decimal("0.00")
        if free_delivery
        else DELIVERY_CHARGE
    )

    cod_charge = (
        COD_CHARGE
        if payment_method == "cod"
        else Decimal("0.00")
    )

    return {
        "free_delivery": free_delivery,
        "delivery_charge": delivery_charge,
        "cod_charge": cod_charge,
        "total": subtotal + delivery_charge + cod_charge,
    }


# ==========================================
# CHECKOUT: CUSTOMER AND DELIVERY DETAILS
# ==========================================
def checkout(request):
    result = _get_cart_items(request)

    if result is None:
        return redirect("cart:detail")

    items, subtotal = result
    totals = _checkout_totals(subtotal)

    context = {
        "items": items,
        "subtotal": subtotal,
        **totals,
        "shipping": totals["delivery_charge"],
        "free_delivery_threshold": FREE_DELIVERY_THRESHOLD,
    }

    if request.method == "POST":
        customer_details = {
            "customer_name": request.POST.get(
                "customer_name", ""
            ).strip(),
            "email": request.POST.get("email", "").strip(),
            "phone": request.POST.get("phone", "").strip(),
            "address": request.POST.get("address", "").strip(),
            "city": request.POST.get("city", "").strip(),
            "postal_code": request.POST.get(
                "postal_code", ""
            ).strip(),
        }

        if not all(customer_details.values()):
            messages.error(
                request,
                "Please fill in all required delivery details.",
            )
            return render(
                request,
                "orders/checkout.html",
                context,
            )

        request.session["checkout_details"] = customer_details
        request.session.modified = True

        return redirect("orders:payment_method")

    return render(request, "orders/checkout.html", context)


# ==========================================
# PAYMENT METHOD: COD OR KHALTI DEMO
# ==========================================
def payment_method(request):
    customer_details = request.session.get("checkout_details")

    if not customer_details:
        messages.error(
            request,
            "Please enter your delivery details first.",
        )
        return redirect("orders:checkout")

    result = _get_cart_items(request)

    if result is None:
        request.session.pop("checkout_details", None)
        request.session.modified = True
        return redirect("cart:detail")

    items, subtotal = result

    # Default display: no COD charge until COD is selected.
    selected_method = request.POST.get(
        "payment_method", "khalti"
    ).strip()

    if selected_method not in ("cod", "khalti"):
        selected_method = "khalti"

    totals = _checkout_totals(subtotal, selected_method)

    context = {
        "items": items,
        "subtotal": subtotal,
        **totals,
        "selected_method": selected_method,
    }

    if request.method != "POST":
        # Initial page: show the base total.
        context.update(_checkout_totals(subtotal, "khalti"))
        context["selected_method"] = "khalti"

        return render(
            request,
            "orders/payment_method.html",
            context,
        )

    selected_method = request.POST.get(
        "payment_method", ""
    ).strip()

    if selected_method not in ("cod", "khalti"):
        messages.error(
            request,
            "Please select Cash on Delivery or Khalti.",
        )
        context["selected_method"] = "khalti"
        context.update(_checkout_totals(subtotal, "khalti"))

        return render(
            request,
            "orders/payment_method.html",
            context,
        )

    # Khalti is display/demo only. No gateway is contacted.
    if selected_method == "khalti":
        messages.warning(
            request,
            "Khalti is not connected. No online payment "
            "will be processed or verified.",
        )

    try:
        with transaction.atomic():
            verified_subtotal = Decimal("0.00")
            verified_items = []

            # Recheck stock and prices inside the transaction.
            cart = request.session.get("shopping_cart", {})

            if not cart:
                raise ValueError("Your shopping cart is empty.")

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

            # Recalculate all charges using verified prices.
            verified_delivery = (
                Decimal("0.00")
                if verified_subtotal >= FREE_DELIVERY_THRESHOLD
                else DELIVERY_CHARGE
            )

            verified_cod_charge = (
                COD_CHARGE
                if selected_method == "cod"
                else Decimal("0.00")
            )

            final_total = (
                verified_subtotal
                + verified_delivery
                + verified_cod_charge
            )

            order = Order.objects.create(
                customer_name=customer_details["customer_name"],
                email=customer_details["email"],
                phone=customer_details["phone"],
                address=customer_details["address"],
                city=customer_details["city"],
                postal_code=customer_details["postal_code"],
                status="pending",
                total_amount=final_total,
            )

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

    # Clear session data only after the order is saved.
    request.session["shopping_cart"] = {}
    request.session.pop("checkout_details", None)
    request.session.modified = True

    if selected_method == "cod":
        messages.success(
            request,
            "Your Cash on Delivery order has been placed "
            "successfully. The NPR 20 COD charge is included.",
        )
    else:
        messages.warning(
            request,
            "Demo order created successfully. No Khalti "
            "payment was made or verified.",
        )

    return redirect("orders:success", order_id=order.pk)


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

    # Difference includes delivery and any COD charge.
    additional_charges = order.total_amount - subtotal

    return render(
        request,
        "orders/order_success.html",
        {
            "order": order,
            "subtotal": subtotal,
            "delivery_charge": additional_charges,
            "additional_charges": additional_charges,
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

        email = request.POST.get("email", "").strip()

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
                error_message = "Please enter a valid order number."

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
    tracking_order_id = request.session.get("tracking_order_id")
    tracking_email = request.session.get("tracking_email")

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
                "This order cannot be cancelled because it "
                "has already been delivered.",
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
