from django.contrib import admin
from .models import Recenzia, Report
from django.utils.html import format_html
from django.urls import reverse

admin.site.register(Recenzia)

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    # 1. Zobrazenie v tabuľke (pridaný stĺpec pre cieľ nahlásenia a dynamické linky)
    list_display = ('id', 'get_target_user', 'zalobca', 'get_object_type', 'dovod', 'vytvorene', 'vyriesene', 'link_na_web')
    
    # 2. Inteligentné zoskupovanie a filtrovanie (filtrovanie podľa obvineného užívateľa ALEBO autora nahláseného inzerátu)
    list_filter = ('vyriesene', 'dovod', 'vytvorene', 'obvineny', 'inzerat__autor')
    
    # Rozšírené vyhľadávanie aj o názvy inzerátov a ich autorov
    search_fields = ('obvineny__username', 'zalobca__username', 'inzerat__nazov', 'inzerat__autor__username')
    
    # Možnosť rýchlo odklikať vyriešené nahlásenia priamo zo zoznamu
    list_editable = ('vyriesene',)
    
    # Zoradenie: najprv nevyriešené, potom pod seba zoskupí rovnakých obvinených a autorov inzerátov
    ordering = ('vyriesene', 'obvineny', 'inzerat__autor', '-vytvorene')
    
    # Polia, ktoré v detaile nahlásenia admin nemôže prepisovať
    readonly_fields = ('vytvorene', 'zalobca', 'obvineny', 'inzerat', 'dovod', 'popis', 'link_na_web')
    
    # Prehľadné rozdelenie detailu nahlásenia do sekcií
    fieldsets = (
        ('Detaily incidentu', {
            'fields': ('zalobca', 'obvineny', 'inzerat', 'dovod', 'popis', 'vytvorene')
        }),
        ('Odkazy na web', {
            'fields': ('link_na_web',),
        }),
        ('Riešenie incidentu', {
            'fields': ('vyriesene',),
        }),
    )

    def get_target_user(self, obj):
        """Vráti meno používateľa, na ktorého sa sťažnosť sype (či už priamo, alebo cez inzerat)."""
        if obj.inzerat:
            return format_html('<b>{}</b> <span style="color:#aaa;">(cez inzerát)</span>', obj.inzerat.autor.username)
        if obj.obvineny:
            return obj.obvineny.username
        return "-"
    get_target_user.short_description = 'Nahlásený používateľ'

    def get_object_type(self, obj):
        """Rozlíši v zozname na prvý pohľad, či ide o nahlásenie človeka alebo inzerátu."""
        if obj.inzerat:
            return format_html('<span style="background:#6c757d; color:#fff; padding:2px 6px; border-radius:3px; font-size:11px;">INZERÁT</span>')
        return format_html('<span style="background:#0d6efd; color:#fff; padding:2px 6px; border-radius:3px; font-size:11px;">PROFIL</span>')
    get_object_type.short_description = 'Typ objektu'

    def link_na_web(self, obj):
        """Univerzálne tlačidlo: ak je nahlásený inzerát, hodí odkaz na detail inzerátu. Ak používateľ, hodí odkaz na profil."""
        if obj.inzerat:
            url = reverse('detail_inzeratu', kwargs={'pk': obj.inzerat.pk})
            return format_html(
                '<a href="{}" target="_blank" class="button" style="padding:3px 10px; background:#ffc107; color:#000; font-weight:bold; border-radius:4px; text-decoration:none;">Zobraziť inzerát</a>', 
                url
            )
        elif obj.obvineny:
            url = reverse('verejny_profil', kwargs={'username': obj.obvineny.username})
            return format_html(
                '<a href="{}" target="_blank" class="button" style="padding:3px 10px; background:#0dcaf0; color:#000; font-weight:bold; border-radius:4px; text-decoration:none;">Zobraziť profil</a>', 
                url
            )
        return "-"
    
    link_na_web.short_description = 'Odkaz na web'