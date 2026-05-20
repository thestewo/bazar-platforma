from django.contrib import admin
from .models import Recenzia, Report
from django.utils.html import format_html
from django.urls import reverse

admin.site.register(Recenzia)
@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'obvineny', 'zalobca', 'dovod', 'vytvorene', 'vyriesene', 'link_na_profil')
    list_filter = ('vyriesene', 'dovod', 'vytvorene')
    search_fields = ('obvineny__username', 'zalobca__username')
    
    list_editable = ('vyriesene',)
    
    readonly_fields = ('vytvorene', 'zalobca', 'obvineny', 'dovod', 'link_na_profil')
    
    fieldsets = (
        ('Detaily nahlásenia', {
            'fields': ('zalobca', 'obvineny', 'dovod', 'link_na_profil', 'vytvorene')
        }),
        ('Riešenie incidentu', {
            'fields': ('vyriesene',),
        }),
    )

    def link_na_profil(self, obj):
        if obj.obvineny:
            url = reverse('verejny_profil', kwargs={'username': obj.obvineny.username})
            return format_html(
                '<a href="{}" target="_blank" class="button" style="padding:3px 10px; background:#0dcaf0; color:#000; font-weight:bold; border-radius:4px; text-decoration:none;">Zobraziť profil</a>', 
                url
            )
        return "-"
    
    link_na_profil.short_description = 'Profil na webe'