from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView
from django.db.models import Q, Count
from django.core.cache import cache
from .models import Product, Category, Tag
from reviews.models import Review

# i really don't know wow these thing even fucntion
class ProductListView(ListView):
    model = Product
    template_name = "products/product_list.html"
    context_object_name = "products"
    paginate_by = 12

    
    def get_queryset(self):
        # Detect if any filters/search are active
        has_filters = any([
            self.kwargs.get("category_slug"),
            self.request.GET.get("category"),
            self.request.GET.get("tag"),
            self.request.GET.get("brand"),
            self.request.GET.get("q"),
            self.request.GET.get("sort") not in (None, "", "newest"),
        ])

        if not has_filters:
            # ── Cache the default unfiltered list (most common page view) ──
            # This is the /products/ page with no filters — cache for 5 min.
            # Saves ~1.5s Supabase round-trip on every repeat visitor.
            cached = cache.get("default_product_list")
            if cached is not None:
                return cached
            queryset = (
                Product.objects.filter(is_active=True)
                .select_related("category")
                .order_by("-created_at")
                .distinct()
            )
            result = list(queryset)
            cache.set("default_product_list", result, timeout=300)  # 5 min
            return result

        # ── Filtered/searched: always hit DB for correct results ──
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

        # ── Cached: categories (rarely change, safe to cache 10 min) ──
        categories = cache.get("active_categories")
        if categories is None:
            categories = list(Category.objects.filter(is_active=True))
            cache.set("active_categories", categories, timeout=600)
        context["categories"] = categories

        # ── Cached: tags ──
        all_tags = cache.get("active_tags")
        if all_tags is None:
            all_tags = list(Tag.objects.filter(is_active=True))
            cache.set("active_tags", all_tags, timeout=600)
        context["all_tags"] = all_tags

        # ── Cached: brand list ──
        brands = cache.get("active_brands")
        if brands is None:
            brands = list(
                Product.objects.filter(is_active=True)
                .exclude(brand="")
                .values_list("brand", flat=True)
                .distinct()
                .order_by("brand")
            )
            cache.set("active_brands", brands, timeout=600)
        context["brands"] = brands

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

        # ── Cached: reviews for this product (cache per product pk) ──
        cache_key = f"product_reviews_{product.pk}"
        review_data = cache.get(cache_key)
        if review_data is None:
            reviews = list(Review.objects.filter(product=product, is_approved=True))
            review_count = len(reviews)
            star_breakdown = {}
            for star in range(5, 0, -1):
                count = sum(1 for r in reviews if r.rating == star)
                pct = (count / review_count * 100) if review_count else 0
                star_breakdown[star] = {"count": count, "percentage": round(pct)}
            review_data = {
                "reviews": reviews,
                "review_count": review_count,
                "star_breakdown": star_breakdown,
            }
            cache.set(cache_key, review_data, timeout=300)  # 5 min
        context.update(review_data)

        # User's own review (never cache — user-specific)
        if self.request.user.is_authenticated:
            context["user_review"] = Review.objects.filter(
                product=product, user=self.request.user
            ).first()

        # ── Cached: related products (cache per product pk) ──
        related_key = f"related_products_{product.pk}"
        related = cache.get(related_key)
        if related is None:
            product_tags = product.tags.all()
            related = list(
                Product.objects.filter(is_active=True)
                .exclude(pk=product.pk)
                .filter(Q(category=product.category) | Q(tags__in=product_tags))
                .annotate(shared_tags=Count("tags", filter=Q(tags__in=product_tags)))
                .order_by("-shared_tags", "-average_rating")
                .distinct()[:4]
            )
            cache.set(related_key, related, timeout=300)
        context["related_products"] = related

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
