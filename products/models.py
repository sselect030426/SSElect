from django.db import models
from django.urls import reverse
from django.utils.text import slugify
import uuid


class ProductImage(models.Model): # what is this model  inside as aparam 
    """An uploaded gallery image attached to a product."""

    product = models.ForeignKey(
        "Product",  
        on_delete=models.CASCADE, ## what does cascade even means 
        related_name="gallery_images",
    )
    image = models.ImageField(upload_to="products/gallery/") # what does ine do i don't understad  
    order = models.PositiveIntegerField(default=0, help_text="Lower number = shown first") # what dies this means 

    class Meta:
        ordering = ["order", "id"] # what are we een talking here 

    def __str__(self):
        return f"Image #{self.pk} for {self.product.name}"


class Category(models.Model):
    """Hierarchical product category (e.g. Electronics > Mobiles)."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey( # what parenet are we talking and eehwt awoird this look like wen i see this int he real world
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    image_url = models.URLField(max_length=500, blank=True) # why do i store the url fo the image 
    display_order = models.IntegerField(default=0) # what display_order are we talking ehere 
    is_active = models.BooleanField(default=True) 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta: #wat si the purpise of the mta class in the fie 
        verbose_name = "Category" 
        verbose_name_plural = "Categories" 
        ordering = ["display_order", "name"] 

    def __str__(self):  # this si the tosting functio in think 
        return self.name 

    def save(self, *args, **kwargs):  # what does it save  or is it used to update the Product
        if not self.slug: 
            self.slug = slugify(self.name) 
        super().save(*args, **kwargs) 

    def get_absolute_url(self): 
        return reverse("products:category_detail", kwargs={"category_slug": self.slug}) # ooh we can get the get_absolute_url using this things also what is : do in the  python  


class Tag(models.Model): # how does this is differnt for mthe category we have 
    """Short keyword labels for products (e.g. 5G, OLED, Gaming).""" 
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    description = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta: # yeah right if the ordeing is set here then what is the ordering  that is in the admin.py 
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(models.Model):
    """
    Full-featured product model for an electronics-style shop.
    Includes brand, SKU, specifications JSON, image gallery, and pricing.
    """

    AVAILABILITY_CHOICES = [ # i need to remoev the unnessry ones from this 
        ("In Stock", "In Stock"), # why is yhere 2 valus of tuple 
        ("Out of Stock", "Out of Stock"),
        ("Pre-Order", "Pre-Order"),
        ("Discontinued", "Discontinued"),
    ]

    # Identity
    sku = models.CharField(max_length=50, unique=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    brand = models.CharField(max_length=100, blank=True)
    model_number = models.CharField(max_length=100, blank=True)

    # Description
    short_description = models.CharField(max_length=500, blank=True)
    long_description = models.TextField(blank=True)

    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="INR")

    # Stock & Availability
    stock_quantity = models.PositiveIntegerField(default=0)
    availability_status = models.CharField(
        max_length=20, choices=AVAILABILITY_CHOICES, default="In Stock"
    )

    # Relations
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="products"
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="products")

    # Media
    image = models.ImageField(upload_to="products/", blank=True, help_text="Main display image")
    video_url = models.URLField(max_length=500, blank=True)
    # Gallery images are managed via the ProductImage related model (gallery_images)

    # Specifications (flexible JSON for electronics)
    specifications = models.JSONField(
        default=dict,
        blank=True,
        help_text="Key-value pairs of product specs e.g. {RAM: 8GB, Display: 6.1 inch}",
    )

    # Aggregated Review Stats (updated when reviews are saved)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    review_count = models.IntegerField(default=0)

    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.sku:
            self.sku = str(uuid.uuid4())[:8].upper()
        # Auto-sync availability_status with stock_quantity
        # Only manage In Stock / Out of Stock — leave Pre-Order and Discontinued alone
        if self.availability_status in ("In Stock", "Out of Stock"):
            if self.stock_quantity <= 0:
                self.availability_status = "Out of Stock"
            else:
                self.availability_status = "In Stock"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("products:product_detail", kwargs={"slug": self.slug})

    def get_add_to_cart_url(self):
        return reverse("cart:add_to_cart", kwargs={"slug": self.slug})

    def get_remove_from_cart_url(self):
        return reverse("cart:remove_from_cart", kwargs={"slug": self.slug})

    @property # what does thisproperty are even do 
    def is_on_sale(self):
        return self.original_price is not None and self.original_price > self.price

    @property
    def discount_percentage(self):
        if self.is_on_sale:
            return round((1 - self.price / self.original_price) * 100)
        return 0

    @property
    def is_available(self):
        """True only when the product is actively In Stock."""
        return self.availability_status == "In Stock"

    def update_rating(self):
        """Recalculate and save average_rating and review_count from approved reviews."""
        from reviews.models import Review
        approved = Review.objects.filter(product=self, is_approved=True)
        count = approved.count()
        avg = approved.aggregate(models.Avg("rating"))["rating__avg"] or 0.00
        Product.objects.filter(pk=self.pk).update(
            average_rating=round(avg, 2),
            review_count=count,
        )
