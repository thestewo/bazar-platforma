from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('podmienky/', views.vop_view, name='vop'),
    path('gdpr/', views.gdpr_view, name='gdpr'),
    path('ticket/novy/', views.vytvor_ticket, name='vytvor_ticket'),
]