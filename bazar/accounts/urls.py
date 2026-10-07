from django.urls import path, reverse_lazy
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
    path('profil/<int:user_id>/recenzia/', views.pridat_recenziu, name='pridat_recenziu'),
    path('recenzia/zmazat/<int:recenzia_id>/', views.zmazat_recenziu, name='zmazat_recenziu'),
    path('pouzivatel/<int:user_id>/nahlasit/', views.nahlasit_pouzivatela, name='nahlasit_pouzivatela'),
    path('profil/nastavenia/', views.rozsirene_nastavenia, name='rozsirene_nastavenia'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),

    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/password_reset_confirm.html',
             post_reset_login=True,  # Používateľa po zmene hesla automaticky prihlási
             success_url=reverse_lazy('login')  # Po zmene ho presmeruje na prihlásenie (alebo napr. 'profil')
         ), 
         name='password_reset_confirm'),

]