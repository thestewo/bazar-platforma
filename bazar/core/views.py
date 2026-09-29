import unicodedata
from datetime import timedelta
from math import radians, cos, sin, asin, sqrt

import math
import requests
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from inzeraty.models import Inzerat, Kategoria, Typ

# 1. Pomocné funkcie


def odstran_diakritiku(text):
    if not text:
        return ''
    text = unicodedata.normalize('NFD', text)
    return ''.join(c for c in text if unicodedata.category(c) != 'Mn')

def ziskaj_suradnice(mesto_text):
    if not mesto_text or not mesto_text.strip():
        return None, None, None
    try:
        url = (
            f"https://nominatim.openstreetmap.org/search?"
            f"format=json&q={requests.utils.quote(mesto_text.strip())}&limit=1&addressdetails=1"
            f"&accept-language=sk&countrycodes=sk"
        )
        response = requests.get(url, headers={'User-Agent': 'NOVU_App_Educational'}, timeout=5)
        data = response.json()
        
        if data and len(data) > 0:
            lat, lon = float(data[0]['lat']), float(data[0]['lon'])
            addr = data[0].get('address', {})
            
            pekny_nazov = (
                addr.get('city') or 
                addr.get('town') or 
                addr.get('village') or 
                addr.get('municipality') or 
                addr.get('hamlet') or 
                addr.get('county') or
                data[0].get('display_name', '').split(',')[0].strip()
            )
            return lat, lon, pekny_nazov
    except Exception as e:
        print(f"Chyba pri získavaní súradníc pre '{mesto_text}': {e}")
        
    return None, None, None

def haversine(lon1, lat1, lon2, lat2):
    """Vypočíta vzdušnú vzdialenosť dvoch bodov na Zemi v kilometroch."""
    R = 6371.0  # Polomer Zeme v km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def home(request):
    inzeraty = Inzerat.objects.filter(je_aktivny=True)
    
    kategorie = Kategoria.objects.all()
    typy = Typ.objects.all()

    q = request.GET.get('q')
    kat_id = request.GET.get('kategoria')
    t_id = request.GET.get('typ')
    min_cena = request.GET.get('min_cena')
    max_cena = request.GET.get('max_cena')
    
    mesto_hladane = request.GET.get('l') 
    okruh = request.GET.get('r')         
    zoradenie = request.GET.get('zoradenie')

    # 1. Textové vyhľadávanie
    if q and q.strip():
        q_clean = q.strip()
        inzeraty = inzeraty.filter(
            Q(nazov__icontains=q_clean) | 
            Q(popis__icontains=q_clean) | 
            Q(skryte_tagy__icontains=q_clean)
        ).distinct()

    # 2. Kategória a typ
    if kat_id:
        inzeraty = inzeraty.filter(kategoria_id=kat_id)
        
    if t_id:
        inzeraty = inzeraty.filter(typ=t_id)
        
    # 3. Filtrovanie podľa ceny
    if min_cena and min_cena.strip():
        try:
            val_min = float(min_cena.strip().replace(',', '.'))
            inzeraty = inzeraty.filter(cena__gte=val_min)
        except ValueError:
            pass

    if max_cena and max_cena.strip():
        try:
            val_max = float(max_cena.strip().replace(',', '.'))
            inzeraty = inzeraty.filter(cena__lte=val_max)
        except ValueError:
            pass

    # 4. LOKALITA A OKOLIE (OPRAVENÝ ALGORITMUS)
    if mesto_hladane and mesto_hladane.strip():
        mesto_hladane_clean = mesto_hladane.strip()
        h_lat, h_lon, pekny_nazov_hladany = ziskaj_suradnice(mesto_hladane_clean)
        
        # Ak sme našli súradnice vyhľadávaného mesta a bol zadaný okruh km
        if h_lat and h_lon and okruh and okruh.strip():
            try:
                okruh_val = float(okruh)
                id_v_okruhu = []
                
                # Prejdeme všetky inzeráty
                vsetky_aktualne_inzeraty = list(inzeraty)
                
                for inz in vsetky_aktualne_inzeraty:
                    inz_lat = inz.lat
                    inz_lon = inz.lon
                    
                    # AK INZERÁT NEMÁ SÚRADNICE: Získame ich a uložíme do DB
                    if (inz_lat is None or inz_lon is None) and inz.lokalita:
                        inz_lat, inz_lon, _ = ziskaj_suradnice(inz.lokalita)
                        if inz_lat and inz_lon:
                            Inzerat.objects.filter(id=inz.id).update(lat=inz_lat, lon=inz_lon)

                    # Prepočet vzdialenosti
                    if inz_lat is not None and inz_lon is not None:
                        vzdialenost = haversine(h_lon, h_lat, inz_lon, inz_lat)
                        if vzdialenost <= okruh_val:
                            id_v_okruhu.append(inz.id)

                # Vyfiltrujeme len tie inzeráty, ktoré spadajú do okruhu km
                inzeraty = inzeraty.filter(id__in=id_v_okruhu)
                
            except ValueError:
                inzeraty = inzeraty.filter(lokalita__icontains=mesto_hladane_clean)
        else:
            # Ak nebol zadaný okruh km, hľadáme len podľa názvu
            inzeraty = inzeraty.filter(lokalita__icontains=mesto_hladane_clean)

    # 5. ZORADENIE
    if zoradenie == 'cena_asc':
        inzeraty = inzeraty.order_by('cena')
    elif zoradenie == 'cena_desc':
        inzeraty = inzeraty.order_by('-cena')
    else:
        inzeraty = inzeraty.order_by('-vytvorene')

    # Paginácia na 16 kusov
    paginator = Paginator(inzeraty, 16)
    page_number = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.get_page(page_number)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' and int(page_number) > paginator.num_pages:
            raise EmptyPage
    except EmptyPage:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return HttpResponse('')
        page_obj = paginator.get_page(paginator.num_pages)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        response = render(request, 'inzeraty/inzeraty_list_partial.html', {'inzeraty': page_obj})
        response['X-Has-Next'] = 'true' if page_obj.has_next() else 'false'
        return response
    
    return render(request, 'home.html', {
        'inzeraty': page_obj,
        'kategorie': kategorie,
        'typy': typy,
        'ma_dalsiu_stranu': page_obj.has_next()
    })
def vop_view(request):
    return render(request, 'vop.html')

def gdpr_view(request):
    return render(request, 'gdpr.html')

from django.http import HttpResponse, JsonResponse
from .models import Ticket

def vytvor_ticket(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        if request.user.is_authenticated:
            email = request.user.email

        ticket = Ticket.objects.create(
            autor=request.user if request.user.is_authenticated else None,
            email=email,
            typ=request.POST.get('typ', 'navrh'),
            predmet=request.POST.get('predmet'),
            sprava=request.POST.get('sprava')
        )
        return HttpResponse(status=200)
        
    return HttpResponse(status=400)