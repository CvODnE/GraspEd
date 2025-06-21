from django.urls import path
from . import views


app_name = "web"

urlpatterns = [
    path("", views.index, name="index"),
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("student/dashboard/", views.student_dashboard_view, name="student_dashboard"),
    path("teacher/dashboard/", views.teacher_dashboard_view, name="teacher_dashboard"),
    path("delete_account/", views.delete_account_view, name="delete_account"),
]