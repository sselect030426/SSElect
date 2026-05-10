from django.db import models
from django.conf import settings
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver
from products.models import Product


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    PAYMENT_CHOICES = [
        ("upi_qr", "UPI QR"),
    ]

    payment_method = models.CharField(
        max_length=50, choices=PAYMENT_CHOICES, default="upi_qr"
    )
    is_paid = models.BooleanField(default=False)
    # Prevents stock from being deducted more than once per order
    stock_deducted = models.BooleanField(default=False)
    utr_number = models.CharField(max_length=100, blank=True, null=True)
    payment_screenshot = models.ImageField(
        upload_to="payment_proofs/", blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        username = self.user.username if self.user else "Guest"
        return f"Order #{self.id} - {username}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    @property
    def get_total(self):
        return self.price * self.quantity


@receiver(post_save, sender=Order)  # what is this and how does this work
def deduct_stock_on_confirmation(sender, instance, **kwargs):
    """
    Fires after an Order is saved.
    When status reaches 'confirmed' or 'delivered' for the first time,
    deduct each product's stock_quantity by the ordered quantity.
    The stock_deducted flag prevents double-deductions if the admin
    updates the order again later.
    """
    DEDUCT_STATUSES = {"confirmed", "delivered"}
    if instance.status in DEDUCT_STATUSES and not instance.stock_deducted:
        for item in instance.items.select_related("product").all():
            # Atomic decrement — safe for concurrent requests
            Product.objects.filter(pk=item.product.pk).update(
                stock_quantity=F("stock_quantity") - item.quantity
            )
            # Re-fetch, clamp at 0, and save so Product.save() syncs availability_status
            product = Product.objects.get(pk=item.product.pk)
            if product.stock_quantity < 0:
                product.stock_quantity = 0
            product.save()

        # Mark as deducted — use update() to avoid re-triggering this signal
        Order.objects.filter(pk=instance.pk).update(stock_deducted=True)
