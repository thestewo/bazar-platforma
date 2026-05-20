from django.contrib import admin
from .models import Ticket

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'typ', 'predmet', 'autor', 'email', 'stav', 'vytvorene')
    list_filter = ('stav', 'typ', 'vytvorene')
    search_fields = ('predmet', 'sprava', 'email', 'autor__username')
    list_editable = ('stav',)
    readonly_fields = ('vytvorene', 'autor', 'email', 'typ', 'predmet', 'sprava')
    fieldsets = (
        ('Informácie od používateľa', {
            'fields': ('autor', 'email', 'typ', 'predmet', 'sprava', 'vytvorene')
        }),
        ('Správa ticketu', {
            'fields': ('stav', 'poznamka_admina'),
        }),
    )