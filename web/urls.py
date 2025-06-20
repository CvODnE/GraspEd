from django.urls import path
from . import views


app_name = "web"

urlpatterns = [
    path("", views.index, name="index"),
    path("signup/", views.signup_view, name="signup"),
    path("delete_account/", views.delete_account_view, name="delete_account"),
]