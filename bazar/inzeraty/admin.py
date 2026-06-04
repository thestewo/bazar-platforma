from django.contrib import admin
from .models import Inzerat, Kategoria, Typ
from django.contrib import admin
from .models import Kontakt


admin.site.register(Kontakt)
admin.site.register(Kategoria)
admin.site.register(Typ)
admin.site.register(Inzerat)