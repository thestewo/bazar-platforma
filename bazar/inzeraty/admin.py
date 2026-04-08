from django.contrib import admin
from .models import Inzerat, Kategoria, Typ

admin.site.register(Kategoria)
admin.site.register(Typ)
admin.site.register(Inzerat)