from decimal import Decimal
from django.conf import settings
from products.models import Product


class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(settings.CART_SESSION_ID)
        if not cart:
            cart = self.session[settings.CART_SESSION_ID] = {}
        self.cart = cart

    def add(self, product, quantity=1):
        product_id = str(product.id)
        if product_id not in self.cart:
            self.cart[product_id] = {
                "quantity": 0,
                "price": str(product.price),
            }
        self.cart[product_id]["quantity"] += quantity
        self.save()

    def update(self, product_id, quantity):
        product_id = str(product_id)
        if product_id in self.cart:
            self.cart[product_id]["quantity"] = quantity
            self.save()

    def remove(self, product_id):
        product_id = str(product_id)
        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    def clear(self):
        self.session[settings.CART_SESSION_ID] = {}
        self.save()

    def __iter__(self):
        product_ids = list(self.cart.keys())
        products = Product.objects.filter(id__in=product_ids)

        # Auto-clean orphan items (product deleted from DB) from the session
        valid_ids = {str(p.id) for p in products}
        orphan_ids = set(product_ids) - valid_ids
        if orphan_ids:
            for orphan_id in orphan_ids:
                del self.cart[orphan_id]
            self.save()

        # ── KEY FIX ──────────────────────────────────────────────────────────
        # Work on a COPY of each session item, not the item itself.
        # The session dict (self.cart) must only ever contain JSON-safe types
        # (str, int, float, list, dict). If we write Decimal back into it,
        # Django's signed_cookies session backend crashes when it tries to
        # JSON-serialise the session on response.
        # ─────────────────────────────────────────────────────────────────────
        product_map = {str(p.id): p for p in products}
        for product_id, session_item in self.cart.items():
            product = product_map.get(product_id)
            if product is None:
                continue
            # Shallow copy keeps session_item untouched
            item = session_item.copy()
            item["product"]     = product
            item["price"]       = Decimal(item["price"])        # Decimal for math
            item["total_price"] = item["price"] * item["quantity"]
            yield item

    def __len__(self):
        return sum(item["quantity"] for item in self.cart.values())

    def get_total_price(self):
        return sum(
            Decimal(item["price"]) * item["quantity"]
            for item in self.cart.values()
        )

    def save(self):
        self.session.modified = True


def cart_context(request):
    return {"cart": Cart(request)}
