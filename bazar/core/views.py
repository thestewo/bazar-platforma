from datetime import timedelta

from django.shortcuts import render
from inzeraty.models import Inzerat, Kategoria, Typ
from django.db.models import Q
import requests
from math import radians, cos, sin, asin, sqrt
from django.core.paginator import Paginator, EmptyPage
from django.http import HttpResponse
from django.utils import timezone
# 1. Pomocné funkcie
def haversine(lon1, lat1, lon2, lat2):
    try:
        lon1, lat1, lon2, lat2 = map(radians, [float(lon1), float(lat1), float(lon2), float(lat2)])
        dlon = lon2 - lon1 
        dlat = lat2 - lat1 
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a)) 
        return 6371 * c
    except:
        return 9999

def ziskaj_suradnice(mesto_text):
    """Premení názov mesta na lat, lon a vráti oficiálny názov s diakritikou."""
    if not mesto_text:
        return None, None, None
    try:
        url = (
            f"https://nominatim.openstreetmap.org/search?"
            f"format=json&q={mesto_text}&limit=1&addressdetails=1"
            f"&accept-language=sk&countrycodes=sk&featuretype=settlement"
        )
        
        response = requests.get(url, headers={'User-Agent': 'NOVU_App_Educational'}, timeout=5)
        data = response.json()
        
        if data:
            lat = float(data[0]['lat'])
            lon = float(data[0]['lon'])
            
            addr = data[0].get('address', {})
            pekny_nazov = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('municipality')
            
            if not pekny_nazov:
                pekny_nazov = data[0].get('display_name', '').split(',')[0]
                
            return lat, lon, pekny_nazov
            
    except Exception as e:
        print(f"Chyba pri získavaní súradníc: {e}")
    
    return None, None, None

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

    if q:
        inzeraty = inzeraty.filter(
            Q(nazov__icontains=q) | 
            Q(popis__icontains=q) | 
            Q(skryte_tagy__icontains=q)
        ).distinct()
    if kat_id:
        inzeraty = inzeraty.filter(kategoria_id=kat_id)
    if t_id:
        inzeraty = inzeraty.filter(typ_id=t_id)
    if min_cena:
        inzeraty = inzeraty.filter(cena__gte=min_cena)
    if max_cena:
        inzeraty = inzeraty.filter(cena__lte=max_cena)

    if mesto_hladane:
        h_lat, h_lon, _ = ziskaj_suradnice(mesto_hladane)
        
        if h_lat and h_lon:
            if okruh and okruh.strip():
                try:
                    okruh_val = float(okruh)
                    id_v_okruhu = []
                    vsetky_so_suradnicami = inzeraty.filter(lat__isnull=False, lon__isnull=False)
                    
                    for inz in vsetky_so_suradnicami:
                        vzdialenost = haversine(h_lon, h_lat, inz.lon, inz.lat)
                        if vzdialenost <= okruh_val:
                            id_v_okruhu.append(inz.id)
                    
                    inzeraty = inzeraty.filter(id__in=id_v_okruhu)
                except ValueError:
                    inzeraty = inzeraty.filter(lokalita__icontains=mesto_hladane)
            else:
                inzeraty = inzeraty.filter(lokalita__icontains=mesto_hladane)
        else:
            inzeraty = inzeraty.filter(lokalita__icontains=mesto_hladane)

    inzeraty = inzeraty.order_by('-vytvorene')
    
    # Paginácia na 16 kusov
    paginator = Paginator(inzeraty, 16)
    page_number = request.GET.get('page', 1)
    
    # --- OPRAVA DUPLIKOVANIA POMOCOU TRY-EXCEPT ---
    try:
        page_obj = paginator.get_page(page_number)
        
        # Ak si cez AJAX pýtame stranu, ktorá je väčšia ako skutočný počet strán,
        # get_page by vrátil poslednú stranu. My ale chceme vyvolať EmptyPage, aby sme ju zachytili.
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' and int(page_number) > paginator.num_pages:
            raise EmptyPage
            
    except EmptyPage:
        # Ak už ďalšia strana neexistuje a ide o AJAX, vrátime úplne prázdny HTML dopyt
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return HttpResponse('')
        # Pre klasické načítanie (ak by niekto ručne prepísal URL na blbosť) vrátime poslednú stranu
        page_obj = paginator.get_page(paginator.num_pages)

    # AK JE TO AJAX POŽIADAVKA A STRANA EXISTUJE
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        response = render(request, 'inzeraty/inzeraty_list_partial.html', {'inzeraty': page_obj})
        response['X-Has-Next'] = 'true' if page_obj.has_next() else 'false'
        return response
    
    # KLASICKÉ NAČÍTANIE STRÁNKY
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
        
    return HttpResponse(status=400) # GET požiadavky na túto URL ignorujeme
