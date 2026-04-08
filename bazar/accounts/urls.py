from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import CustomLoginForm

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.MyLoginView.as_view(template_name='accounts/login.html', authentication_form=CustomLoginForm), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profil/', views.profil, name='profil'),
    path('pouzivatel/<str:username>/', views.verejny_profil, name='verejny_profil'),
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),
]