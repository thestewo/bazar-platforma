from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static




urlpatterns = [
    path('pridat/', views.pridat_inzerat, name='pridat_inzerat'),
    path('<int:pk>/', views.detail_inzeratu, name='detail_inzeratu'),
    path('<int:pk>/upravit/', views.upravit_inzerat, name='upravit_inzerat'),
    path('<int:pk>/odstranit/', views.odstranit_inzerat, name='odstranit_inzerat'),
    path('chat/<int:inzerat_id>/', views.chat_detail, name='zacat_chat'),
    path('chat/<int:konverzacia_id>/', views.chat_detail, name='chat_detail'),
    path('moje-spravy/', views.moje_chaty, name='moje_chaty'),
    path('chat/sprava/zmazat/<int:sprava_id>/', views.zmazat_spravu, name='zmazat_spravu'),
    path('chat/<int:konverzacia_id>/nacitat/', views.nacitat_spravy, name='nacitat_spravy'),
    path('chat/<int:inzerat_id>/poslat/', views.poslat_spravu, name='poslat_spravu'),
    path('sprava/upravit/<int:sprava_id>/', views.upravit_spravu, name='upravit_spravu'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)