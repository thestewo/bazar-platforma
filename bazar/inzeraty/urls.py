from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
import mimetypes

# Vynútenie MIME typu pre WebP, aby sa nezačali sťahovať (ako sme riešili predtým)
mimetypes.add_type("image/webp", ".webp", True)

urlpatterns = [
    path('pridat/', views.pridat_inzerat, name='pridat_inzerat'),
    path('<int:pk>/', views.detail_inzeratu, name='detail_inzeratu'),
    path('<int:pk>/upravit/', views.upravit_inzerat, name='upravit_inzerat'),
    path('<int:pk>/odstranit/', views.odstranit_inzerat, name='odstranit_inzerat'),
    
    # CHAT LOGIKA
    path('moje-spravy/', views.moje_chaty, name='moje_chaty'),
    
    # Tu je dôležité mať jasne rozlíšené, či ide o začatie chatu alebo detail
    path('chat/zacat/<int:inzerat_id>/', views.zacat_chat, name='zacat_chat'), 
    path('chat/detail/<int:inzerat_id>/', views.chat_detail, name='chat_detail'),
    
    # AKCIE V CHATE
    path('chat/poslat/<int:inzerat_id>/', views.poslat_spravu, name='poslat_spravu'),
    path('chat/nacitat/<int:konverzacia_id>/', views.nacitat_spravy, name='nacitat_spravy'),
    path('chat/sprava/zmazat/<int:sprava_id>/', views.zmazat_spravu, name='zmazat_spravu'),
    path('sprava/upravit/<int:sprava_id>/', views.upravit_spravu, name='upravit_spravu'),
    
    # AI ANALÝZA (AJAX)
    path('<int:pk>/ai-analyza/', views.ai_analyza_ajax, name='ai_analyza_ajax'),

]

# Statické a mediálne súbory (stačí raz na konci)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)