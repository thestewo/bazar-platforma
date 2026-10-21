from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Inzerat, InzeratObrazok, Kategoria, Kontakt, Typ

# Pôvodné jednoduché registrácie
admin.site.register(Kontakt)
admin.site.register(Kategoria)
admin.site.register(Typ)

# ==========================================================================
# --- STAVY KONTROLY ---
# ==========================================================================

STAV_KARANTENA = 'Karanténa'
STAV_SCHVALENY = 'Schválený'
STAV_ZAMIETNUTY = 'Zamietnutý'
STAV_CAKA = 'caka_na_kontrolu'          # starý predvolený stav
NA_KONTROLU = (STAV_KARANTENA, STAV_CAKA)

STAVY = [
    (STAV_KARANTENA, 'Karanténa (čaká na kontrolu)'),
    (STAV_SCHVALENY, 'Schválený'),
    (STAV_ZAMIETNUTY, 'Zamietnutý'),
    (STAV_CAKA, 'Čaká na kontrolu (starý stav)'),
]

FARBY_STAVOV = {
    STAV_SCHVALENY: '#198754',
    STAV_ZAMIETNUTY: '#dc3545',
    STAV_KARANTENA: '#b58100',
    STAV_CAKA: '#6c757d',
}


class StavKontrolyFilter(admin.SimpleListFilter):
    """Rýchly filter: odkaz /admin/inzeraty/inzerat/?stav=karantena = fronta na kontrolu."""
    title = 'stav kontroly'
    parameter_name = 'stav'

    def lookups(self, request, model_admin):
        return [
            ('karantena', 'Na kontrolu (karanténa)'),
            ('schvaleny', 'Schválené'),
            ('zamietnuty', 'Zamietnuté'),
        ]

    def queryset(self, request, queryset):
        hodnota = self.value()
        if hodnota == 'karantena':
            return queryset.filter(status__in=NA_KONTROLU)
        if hodnota == 'schvaleny':
            return queryset.filter(status=STAV_SCHVALENY)
        if hodnota == 'zamietnuty':
            return queryset.filter(status=STAV_ZAMIETNUTY)
        return queryset


class InzeratAdminForm(forms.ModelForm):
    """Stav ako výber z možností. Neznámy stav zo starých dát sa zachová, aby sa pri uložení nezmenil."""

    class Meta:
        model = Inzerat
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        moznosti = list(STAVY)
        aktualny = self.instance.status if self.instance.pk else None
        if aktualny and aktualny not in dict(moznosti):
            moznosti.insert(0, (aktualny, aktualny))
        self.fields['status'] = forms.ChoiceField(choices=moznosti, label='Stav kontroly')


class InzeratObrazokInline(admin.TabularInline):
    """Ďalšie fotky inzerátu. Zlú fotku môže admin zmazať a inzerát potom schváliť."""
    model = InzeratObrazok
    extra = 0
    fields = ('nahlad', 'obrazok')
    readonly_fields = ('nahlad',)

    @admin.display(description='Náhľad')
    def nahlad(self, obj):
        if obj.pk and obj.obrazok:
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" '
                'style="max-height:220px;max-width:320px;border-radius:6px;"></a>',
                obj.obrazok.url,
            )
        return '—'


@admin.register(Inzerat)
class InzeratAdmin(admin.ModelAdmin):
    form = InzeratAdminForm
    inlines = [InzeratObrazokInline]

    list_display = ('nahlad', 'nazov', 'cena_eur', 'autor', 'kategoria', 'lokalita',
                    'stav_badge', 'je_aktivny', 'vytvorene')
    list_display_links = ('nahlad', 'nazov')
    list_filter = (StavKontrolyFilter, 'je_aktivny', 'kontrola_zlyhala', 'kategoria', 'typ')
    search_fields = ('nazov', 'popis', 'lokalita', 'autor__username', 'autor__email')
    ordering = ('-vytvorene',)
    list_per_page = 25
    list_select_related = ('autor', 'kategoria', 'typ')
    raw_id_fields = ('autor',)
    readonly_fields = ('hlavny_nahlad', 'vytvorene')
    actions = ['schvalit', 'zamietnut', 'vratit_do_karanteny']

    fieldsets = (
        ('Kontrola', {'fields': ('status', 'dovod_zamietnutia', 'kontrola_zlyhala', 'je_aktivny')}),
        ('Inzerát', {'fields': ('nazov', 'popis', 'cena', 'kategoria', 'typ', 'autor')}),
        ('Hlavná fotka', {'fields': ('hlavny_nahlad', 'obrazok')}),
        ('Poloha', {'fields': ('lokalita', 'lat', 'lon')}),
        ('Ostatné', {'classes': ('collapse',), 'fields': ('skryte_tagy', 'vytvorene')}),
    )

    # ----- stĺpce v zozname -----

    @admin.display(description='Foto')
    def nahlad(self, obj):
        if obj.obrazok:
            return format_html(
                '<img src="{}" style="width:64px;height:64px;object-fit:cover;border-radius:6px;">',
                obj.obrazok.url,
            )
        return '—'

    @admin.display(description='Cena', ordering='cena')
    def cena_eur(self, obj):
        return f'{obj.cena} €'

    @admin.display(description='Stav kontroly', ordering='status')
    def stav_badge(self, obj):
        farba = FARBY_STAVOV.get(obj.status, '#6c757d')
        return format_html(
            '<b style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;">{}</b>',
            farba, obj.status,
        )

    @admin.display(description='Náhľad hlavnej fotky')
    def hlavny_nahlad(self, obj):
        if obj.pk and obj.obrazok:
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" '
                'style="max-height:320px;max-width:480px;border-radius:6px;"></a>',
                obj.obrazok.url,
            )
        return '—'

    # ----- upozornenie na fronte -----

    def changelist_view(self, request, extra_context=None):
        if request.method == 'GET' and 'stav' not in request.GET:
            pocet = Inzerat.objects.filter(status__in=NA_KONTROLU).count()
            if pocet:
                self.message_user(
                    request,
                    format_html('Na kontrolu čaká <b>{}</b> inzerátov. <a href="?stav=karantena">Zobraziť</a>', pocet),
                    messages.WARNING,
                )
        return super().changelist_view(request, extra_context)

    # ----- zmena stavu vo formulári synchronizuje zverejnenie -----

    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data and 'je_aktivny' not in form.changed_data:
            obj.je_aktivny = (obj.status == STAV_SCHVALENY)
        super().save_model(request, obj, form, change)

    # ----- hromadné akcie (update() obchádza signály, takže sa nemažú fotky) -----

    @admin.action(description='✅ Schváliť vybrané (zverejniť)')
    def schvalit(self, request, queryset):
        pocet = queryset.update(status=STAV_SCHVALENY, je_aktivny=True, kontrola_zlyhala=False)
        self.message_user(request, f'Schválených inzerátov: {pocet}.', messages.SUCCESS)

    @admin.action(description='❌ Zamietnuť vybrané (skryť)')
    def zamietnut(self, request, queryset):
        pocet = queryset.update(status=STAV_ZAMIETNUTY, je_aktivny=False,
                                dovod_zamietnutia='Zamietnuté administrátorom.')
        self.message_user(request, f'Zamietnutých inzerátov: {pocet}.', messages.WARNING)

    @admin.action(description='⏳ Vrátiť do karantény (skryť)')
    def vratit_do_karanteny(self, request, queryset):
        pocet = queryset.update(status=STAV_KARANTENA, je_aktivny=False)
        self.message_user(request, f'Vrátených do karantény: {pocet}.', messages.INFO)