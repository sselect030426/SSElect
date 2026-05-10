from django.urls import path
from . import views

app_name = "products"  # namespace acts as pointer for all the urls in this page while the page are used ``

urlpatterns = [
    path(
        "", views.ProductListView.as_view(), name="product_list"
    ),  # this make sure  that even when the url chnages i can still reefree this url by the name in the url or any other
    path(
        "category/<slug:category_slug>/",
        views.ProductListView.as_view(),
        name="category_detail",
    ),
    path(
        "product/<slug:slug>/", views.ProductDetailView.as_view(), name="product_detail"
    ),
    path("categories/", views.CategoryListView.as_view(), name="category_list"),
]
