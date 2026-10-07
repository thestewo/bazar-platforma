from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from .models import Recenzia, Report

admin.site.register(Recenzia)



# ==========================================================================
# --- REPORT ADMIN ---
# ==========================================================================

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_target_user', 'zalobca', 'get_object_type', 'dovod', 'vytvorene', 'vyriesene', 'link_na_web')
    list_filter = ('vyriesene', 'dovod', 'vytvorene', 'obvineny', 'inzerat__autor', 'sprava__odosielatel')
    search_fields = ('obvineny__username', 'zalobca__username', 'inzerat__nazov', 'inzerat__autor__username', 'sprava__text', 'sprava__odosielatel__username')
    ordering = ('vyriesene', 'obvineny', 'inzerat__autor', 'sprava__odosielatel', '-vytvorene')
    readonly_fields = ('vytvorene', 'zalobca', 'obvineny', 'inzerat', 'sprava', 'dovod', 'popis', 'link_na_web')
    
    # PRIDANÉ: Hromadné akcie pre rýchlu správu zoznamu
    actions = ['oznacit_ako_vyriesene', 'zablokovat_obvinenych_pouzivatelov']

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

    # --- AKCIE ---

    @admin.action(description="Označiť vybrané nahlásenia ako VYRIEŠENÉ")
    def oznacit_ako_vyriesene(self, request, queryset):
        pocet = queryset.update(vyriesene=True)
        self.message_user(request, f"{pocet} nahlásení bolo označených ako vyriešené.")

    @admin.action(description="ZABLOKOVAŤ obvinených používateľov a deaktivovať ich inzeráty")
    def zablokovat_obvinenych_pouzivatelov(self, request, queryset):
        zablokovani = 0
        for report in queryset:
            # Určíme obvineného používateľa (priamo, z inzerátu alebo zo správy)
            obvineny = report.obvineny
            if not obvineny and report.inzerat:
                obvineny = report.inzerat.autor
            elif not obvineny and report.sprava:
                obvineny = report.sprava.odosielatel

            if obvineny and not obvineny.is_staff and obvineny.is_active:
                # 1. Zablokujeme prihlásenie
                obvineny.is_active = False
                obvineny.save(update_fields=['is_active'])
                
                # 2. Skryjeme všetky jeho inzeráty
                Inzerat.objects.filter(autor=obvineny).update(
                    je_aktivny=False, 
                    status='Zamietnutý', 
                    dovod_zamietnutia='Zablokovaný adminom na základe nahlásení.'
                )
                zablokovani += 1
                
        # Označíme spracované nahlásenia ako vyriešené
        queryset.update(vyriesene=True)
        self.message_user(request, f"Bolo zablokovaných {zablokovani} používateľov a ich nahlásenia boli vyriešené.")


    # --- ZOBRAZOVACIE METÓDY ---

    def get_target_user(self, obj):
        if obj.sprava:
            return format_html('<b>{}</b> <span style="color:#aaa;">(cez správu)</span>', obj.sprava.odosielatel.username)
        if obj.inzerat:
            return format_html('<b>{}</b> <span style="color:#aaa;">(cez inzerát)</span>', obj.inzerat.autor.username)
        if obj.obvineny:
            return obj.obvineny.username
        return "-"
    get_target_user.short_description = 'Nahlásený používateľ'

    def get_object_type(self, obj):
        if obj.sprava:
            return format_html('<span style="background:#198754; color:#fff; padding:2px 6px; border-radius:3px; font-size:11px;">SPRÁVA</span>')
        if obj.inzerat:
            return format_html('<span style="background:#6c757d; color:#fff; padding:2px 6px; border-radius:3px; font-size:11px;">INZERÁT</span>')
        return format_html('<span style="background:#0d6efd; color:#fff; padding:2px 6px; border-radius:3px; font-size:11px;">PROFIL</span>')
    get_object_type.short_description = 'Typ objektu'

    def link_na_web(self, obj):
        if obj.sprava:
            inzerat_id = obj.sprava.konverzacia.inzerat.pk
            kupujuci_id = obj.sprava.konverzacia.kupujuci.pk
            url = f"{reverse('chat_detail', kwargs={'inzerat_id': inzerat_id})}?kupujuci_id={kupujuci_id}"
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


# ==========================================================================
# --- ROZŠÍRENIE USER ADMINA O MOŽNOSŤ ODBLOKOVANIA ---
# ==========================================================================

# Odregistrujeme základného UserAdmina
admin.site.unregister(User)

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'is_active', 'is_staff', 'last_login')
    list_editable = ('is_active', )
    list_filter = ('is_active', 'is_staff', 'last_login')
    actions = ['odblokovat_pouzivatelov', 'zablokovat_pouzivatelov']

    @admin.action(description="ODBLOKOVAŤ vybraných používateľov")
    def odblokovat_pouzivatelov(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} používateľov bolo úspešne odblokovaných.")

    @admin.action(description="ZABLOKOVAŤ vybraných používateľov")
    def zablokovat_pouzivatelov(self, request, queryset):
        updated = queryset.filter(is_staff=False).update(is_active=False)
        self.message_user(request, f"{updated} používateľov bolo zablokovaných.")