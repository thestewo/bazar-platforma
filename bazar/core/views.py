from django.shortcuts import render
from inzeraty.models import Inzerat
from django.http import JsonResponse
from django.http import HttpResponse
import traceback
# Create your views here.

from inzeraty.models import Inzerat, Kategoria, Typ  # Pridaná Kategoria a Typ
from django.db.models import Q                 # Pridané pre vyhľadávanie

def home(request):
    # Základný zoznam aktívnych inzerátov
    inzeraty = Inzerat.objects.filter(je_aktivny=True)
    kategorie = Kategoria.objects.all()
    typy = Typ.objects.all()  # Získanie všetkých typov pre zobrazenie vo formulári

    # Získanie dát z vyhľadávacieho formulára (metóda GET)
    query = request.GET.get('q')
    kat_id = request.GET.get('kategoria')
    t_id = request.GET.get('typ')
    min_cena = request.GET.get('min_cena')
    max_cena = request.GET.get('max_cena')

    # Filtrovanie podľa textu (názov alebo popis)
    if query:
        inzeraty = inzeraty.filter(
            Q(nazov__icontains=query) | Q(popis__icontains=query)
        )
    
    # Filter podľa kategórie
    if kat_id:
        inzeraty = inzeraty.filter(kategoria_id=kat_id)
    
    if t_id:
        inzeraty = inzeraty.filter(typ_id=t_id)

    # Filter podľa ceny (od - do)
    if min_cena:
        inzeraty = inzeraty.filter(cena__gte=min_cena)
    if max_cena:
        inzeraty = inzeraty.filter(cena__lte=max_cena)

    # Zoradenie a finálny render
    inzeraty = inzeraty.order_by('-vytvorene')
    return render(request, 'home.html', {'inzeraty': inzeraty,'kategorie': kategorie, 'typy': typy})