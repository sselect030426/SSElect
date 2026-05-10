from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("confirmation/<int:order_id>/", views.order_confirmation, name="order_confirmation"),
    path("list/", views.order_list, name="order_list"),
    path("order/<int:order_id>/", views.order_detail, name="order_detail"),
]
# i don't know wheter we need the last 2 view at all 
