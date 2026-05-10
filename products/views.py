from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView
from django.db.models import Q, Count
from .models import Product, Category, Tag
from reviews.models import Review

# i really don't know wow these thing even fucntion
class ProductListView(ListView):
    model = Product
    template_name = "products/product_list.html"
    context_object_name = "products"
    paginate_by = 12

    
    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True)

        # Category filter (support both path kwargs and query params for multi-select)
        category_slugs = []
        path_category = self.kwargs.get("category_slug")
        if path_category:
            category_slugs.append(path_category)

        param_categories = self.request.GET.getlist("category")
        if param_categories:
            category_slugs.extend(param_categories)

        if category_slugs:
            queryset = queryset.filter(
                Q(category__slug__in=category_slugs)
                | Q(category__parent__slug__in=category_slugs)
            )

        # Tag filter
        tag_slug = self.request.GET.get("tag")
        if tag_slug:
            queryset = queryset.filter(tags__slug=tag_slug)

        # Brand filter
        brand = self.request.GET.get("brand")
        if brand:
            queryset = queryset.filter(brand__iexact=brand)

        # Search
        search_query = self.request.GET.get("q")
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(brand__icontains=search_query)
                | Q(short_description__icontains=search_query)
                | Q(long_description__icontains=search_query)
                | Q(model_number__icontains=search_query)
            )

        # Sorting
        sort = self.request.GET.get("sort", "-created_at")
        sort_map = {
            "price_asc": "price",
            "price_desc": "-price",
            "rating": "-average_rating",
            "newest": "-created_at",
        }
        queryset = queryset.order_by(sort_map.get(sort, "-created_at"))

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.filter(is_active=True)
        context["all_tags"] = Tag.objects.filter(is_active=True)
        context["brands"] = (
            Product.objects.filter(is_active=True)
            .exclude(brand="")
            .values_list("brand", flat=True)
            .distinct()
            .order_by("brand")
        )

        category_slug = self.kwargs.get("category_slug")
        if category_slug:
            context["current_category"] = get_object_or_404(
                Category, slug=category_slug
            )

        category_slugs = []
        if category_slug:
            category_slugs.append(category_slug)
        category_slugs.extend(self.request.GET.getlist("category"))
        context["selected_category_slugs"] = category_slugs

        context["current_tag"] = self.request.GET.get("tag", "")
        context["current_brand"] = self.request.GET.get("brand", "")
        context["current_sort"] = self.request.GET.get("sort", "newest")
        context["search_query"] = self.request.GET.get("q", "")
        return context


class ProductDetailView(DetailView):
    model = Product
    template_name = "products/product_detail.html"
    context_object_name = "product"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object

        # All approved reviews
        context["reviews"] = Review.objects.filter(product=product, is_approved=True)
        context["review_count"] = context["reviews"].count()

        # Per-star breakdown
        star_breakdown = {}
        for star in range(5, 0, -1):
            count = context["reviews"].filter(rating=star).count()
            pct = (
                (count / context["review_count"] * 100)
                if context["review_count"]
                else 0
            )
            star_breakdown[star] = {"count": count, "percentage": round(pct)}
        context["star_breakdown"] = star_breakdown

        # User's own review
        if self.request.user.is_authenticated:
            context["user_review"] = Review.objects.filter(
                product=product, user=self.request.user
            ).first()

        # Related products: same category OR shared tags, ranked by tag overlap then rating
        product_tags = product.tags.all()
        context["related_products"] = (
            Product.objects.filter(is_active=True)
            .exclude(pk=product.pk)
            .filter(Q(category=product.category) | Q(tags__in=product_tags))
            .annotate(shared_tags=Count("tags", filter=Q(tags__in=product_tags)))
            .order_by("-shared_tags", "-average_rating")
            .distinct()[:4]
        )

        # Specs as a list of (key, value) tuples for template iteration
        context["spec_items"] = (
            list(product.specifications.items()) if product.specifications else []
        )

        return context


class CategoryListView(ListView):
    model = Category
    template_name = "products/category_list.html"
    context_object_name = "categories"

    def get_queryset(self):
        return Category.objects.filter(is_active=True, parent=None)
