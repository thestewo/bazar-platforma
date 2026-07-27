from django.contrib import admin
from .models import Recenzia, Report
from django.utils.html import format_html
from django.urls import reverse

admin.site.register(Recenzia)

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    # 1. Zobrazenie v tabuľke (pridaný stĺpec pre cieľ nahlásenia a dynamické linky)
    list_display = ('id', 'get_target_user', 'zalobca', 'get_object_type', 'dovod', 'vytvorene', 'vyriesene', 'link_na_web')
    
    # 2. Inteligentné zoskupovanie a filtrovanie (rozšírené o odosielateľa správy)
    list_filter = ('vyriesene', 'dovod', 'vytvorene', 'obvineny', 'inzerat__autor', 'sprava__odosielatel')
    
    # Rozšírené vyhľadávanie aj o názvy inzerátov, texty správ a ich autorov
    search_fields = ('obvineny__username', 'zalobca__username', 'inzerat__nazov', 'inzerat__autor__username', 'sprava__text', 'sprava__odosielatel__username')
    
    # Možnosť rýchlo odklikať vyriešené nahlásenia priamo zo zoznamu
    list_editable = ('vyriesene',)
    
    # Zoradenie: najprv nevyriešené, potom pod seba zoskupí podľa cieľov incidentu
    ordering = ('vyriesene', 'obvineny', 'inzerat__autor', 'sprava__odosielatel', '-vytvorene')
    
    # Polia, ktoré v detaile nahlásenia admin nemôže prepisovať (PRIDANÁ 'sprava')
    readonly_fields = ('vytvorene', 'zalobca', 'obvineny', 'inzerat', 'sprava', 'dovod', 'popis', 'link_na_web')
    
    # Prehľadné rozdelenie detailu nahlásenia do sekcií (PRIDANÁ 'sprava' do prvého bloku)
    fieldsets = (
        ('Detaily incidentu', {
            'fields': ('zalobca', 'obvineny', 'inzerat', 'sprava', 'dovod', 'popis', 'vytvorene')
        }),
        ('Odkazy na web', {
            'fields': ('link_na_web',),
        }),
        ('Riešenie incidentu', {
            'fields': ('vyriesene',),
        }),
    )

    def get_target_user(self, obj):
        """Vráti meno používateľa, na ktorého sa sťažnosť sype (či už priamo, cez inzerát, alebo cez správu)."""
        if obj.sprava:
            return format_html('<b>{}</b> <span style="color:#aaa;">(cez správu)</span>', obj.sprava.odosielatel.username)
        if obj.inzerat:
            return format_html('<b>{}</b> <span style="color:#aaa;">(cez inzerát)</span>', obj.inzerat.autor.username)
        if obj.obvineny:
            return obj.obvineny.username
        return "-"
    get_target_user.short_description = 'Nahlásený používateľ'

    def get_object_type(self, obj):
        """Rozlíši v zozname na prvý pohľad, či ide o nahlásenie človeka, inzerátu alebo správy."""
        if obj.sprava:
            return format_html('<span style="background:#198754; color:#fff; padding:2px 6px; border-radius:3px; font-size:11px;">SPRÁVA</span>')
        if obj.inzerat:
            return format_html('<span style="background:#6c757d; color:#fff; padding:2px 6px; border-radius:3px; font-size:11px;">INZERÁT</span>')
        return format_html('<span style="background:#0d6efd; color:#fff; padding:2px 6px; border-radius:3px; font-size:11px;">PROFIL</span>')
    get_object_type.short_description = 'Typ objektu'

    def link_na_web(self, obj):
        """Univerzálne tlačidlo: presmeruje admina na detail inzerátu, profilu alebo priamo do chatu."""
        if obj.sprava:
            url = reverse('chat_detail', kwargs={'inzerat_id': obj.sprava.konverzacia.inzerat.pk})
            return format_html(
                '<a href="{}" target="_blank" class="button" style="padding:3px 10px; background:#a370f7; color:#fff; font-weight:bold; border-radius:4px; text-decoration:none;">Zobraziť chat</a>', 
                url
            )
        elif obj.inzerat:
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