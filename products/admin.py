from django import forms
from django.contrib import admin
from .models import Product, ProductImage, Category, Tag
from .widgets import KeyValueWidget


class ProductAdminForm(
    forms.ModelForm
):  # it for creating the forms inside the admim  panel
    """Custom admin form that replaces the raw JSON textarea for
    specifications with a user-friendly key-value table widget."""

    class Meta:  # how does it even used here and i don't understand the inside working of this thing
        model = Product
        fields = "__all__"
        widgets = {
            "specifications": KeyValueWidget(),
        }


@admin.register(Category)  # what are these things do
class CategoryAdmin(
    admin.ModelAdmin
):  # this inheri define the following what are the how the data most look like in the admin panel
    list_display = [
        "name",
        "slug",
        "parent",
        "display_order",
        "is_active",
        "created_at",
    ]  # what is this ooh these arethe tlist display in the main screen
    prepopulated_fields = {"slug": ("name",)}  # prepopulated_field based thename
    search_fields = ["name", "description"]  # what is this search_field
    list_filter = ["is_active", "parent"]  # what does this do ?
    list_editable = ["display_order", "is_active"]  # what s ts
    ordering = ["display_order", "name"]  # order by the bame od the product


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "created_at"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name", "description"]
    list_filter = ["is_active"]


class ProductImageInline(admin.TabularInline):  # what is this even do
    """Inline image uploader — add/remove/reorder gallery images directly on the Product page."""

    model = ProductImage  # then how come those are stored inside the profuct
    extra = 3  # Show 3 blank upload slots by default
    fields = ["image", "order"]
    ordering = ["order"]
    show_change_link = False

    def get_extra(self, request, obj=None, **kwargs):
        # Don't show blank rows when editing an existing product with many images
        if obj and obj.gallery_images.count() >= 10:
            return 0
        return self.extra


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm  # how does this form know  whete to  show up i really don't understand this at all
    inlines = [
        ProductImageInline
    ]  # what sis this inline even means . it let me edit or view other model inside the current model . if i want this to wok i should add the
    list_display = [
        "name",
        "brand",
        "sku",
        "category",
        "price",
        "original_price",
        "stock_quantity",
        "availability_status",
        "average_rating",
        "review_count",
        "is_active",
        "created_at",
    ]
    list_filter = [
        "category",
        "availability_status",
        "is_active",
        "brand",
        "created_at",
    ]  # so tat means  i cn filter usesing the above ines inly
    list_editable = [
        "price",
        "stock_quantity",
        "is_active",
    ]  # these things are the only things hat editable when im in the list view
    prepopulated_fields = {"slug": ("name",)}  # same
    search_fields = [
        "name",
        "brand",
        "sku",
        "model_number",
        "short_description",
    ]  # what is this even do
    raw_id_fields = ["category"]  # raw id fields
    filter_horizontal = ["tags"]  # what is this even means
    readonly_fields = ["average_rating", "review_count", "created_at", "updated_at"]
    fieldsets = (  # mapping of each od the fields with thier respective
        (
            "Identity",
            {
                "fields": (
                    "name",
                    "slug",
                    "sku",
                    "brand",
                    "model_number",
                    "category",
                    "tags",
                )
            },
        ),
        ("Description", {"fields": ("short_description", "long_description")}),
        ("Pricing", {"fields": ("price", "original_price", "currency")}),
        (
            "Stock & Availability",
            {
                "description": "Set stock_quantity. availability_status auto-syncs: 0 → Out of Stock, >0 → In Stock. Set Pre-Order or Discontinued manually to bypass auto-sync.",
                "fields": ("stock_quantity", "availability_status", "is_active"),
            },
        ),
        (
            "Media",
            {
                "description": "Upload the main product image below. Use the 'Product Images' section further down to upload gallery images from your device.",
                "fields": ("image", "video_url"),
            },
        ),
        ("Specifications", {"fields": ("specifications",)}),
        (
            "Ratings (Read Only)",
            {"fields": ("average_rating", "review_count"), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
