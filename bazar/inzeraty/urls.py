from django.urls import path
from . import views

urlpatterns = [
    path('pridat/', views.pridat_inzerat, name='pridat_inzerat'),
    path('<int:pk>/', views.detail_inzeratu, name='detail_inzeratu'),
    path('<int:pk>/upravit/', views.upravit_inzerat, name='upravit_inzerat'),
    path('<int:pk>/odstranit/', views.odstranit_inzerat, name='odstranit_inzerat'),
]