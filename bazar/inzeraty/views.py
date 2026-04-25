import os
import requests
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.db.models import Q

from .forms import InzeratForm
from .models import Inzerat, Konverzacia, Sprava, InzeratObrazok
from math import radians, cos, sin, asin, sqrt

# --- POMOCNÉ FUNKCIE ---

def haversine(lon1, lat1, lon2, lat2):
    """Vypočíta vzdialenosť v km medzi dvoma bodmi na zemi."""
    try:
        lon1, lat1, lon2, lat2 = map(radians, [float(lon1), float(lat1), float(lon2), float(lat2)])
        dlon = lon2 - lon1 
        dlat = lat2 - lat1 
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a)) 
        return 6371 * c
    except (ValueError, TypeError):
        return 9999  # V prípade chyby vráti neúspešnú vzdialenosť

def ziskaj_suradnice(mesto_text):
    """Premení názov mesta na lat, lon a vráti aj oficiálny názov mesta s diakritikou."""
    if not mesto_text:
        return None, None, None
    try:
        # PRIDANÉ: countrycodes=sk a featuretype=settlement pre presnosť
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
            
            # Skúsime vytiahnuť čistý názov mesta/obce z detailov adresy
            addr = data[0].get('address', {})
            pekny_nazov = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('municipality') or addr.get('hamlet')
            
            if not pekny_nazov:
                pekny_nazov = data[0].get('display_name', '').split(',')[0]
                
            return lat, lon, pekny_nazov
            
    except Exception as e:
        print(f"Chyba pri získavaní súradníc: {e}")
    
    return None, None, None

def zisti_odhad_lokality(request):
    """Pomocná funkcia na získanie lokality z IP."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    
    # Pre vývoj (localhost) simulujeme reálnu IP
    if ip == '127.0.0.1':
        ip = '178.143.32.253' 

    try:
        response = requests.get(f'http://ip-api.com/json/{ip}', timeout=2)
        data = response.json()
        if data.get('status') == 'success':
            return f"{data.get('city')}, {data.get('country')}"
    except:
        pass
    return ""

# --- INZERÁTY ---

def home(request):
    inzeraty = Inzerat.objects.filter(je_aktivny=True).order_by('-vytvorene')

    q = request.GET.get('q')
    kategoria_id = request.GET.get('kategoria')
    typ_id = request.GET.get('typ')
    min_cena = request.GET.get('min_cena')
    max_cena = request.GET.get('max_cena')

    if q:
        inzeraty = inzeraty.filter(Q(nazov__icontains=q) | Q(popis__icontains=q))
    if kategoria_id:
        inzeraty = inzeraty.filter(kategoria_id=kategoria_id)
    if typ_id:
        inzeraty = inzeraty.filter(typ_id=typ_id)
    if min_cena:
        inzeraty = inzeraty.filter(cena__gte=min_cena)
    if max_cena:
        inzeraty = inzeraty.filter(cena__lte=max_cena)

    # FILTROVANIE PODĽA VZDIALENOSTI
    mesto_hladane = request.GET.get('l')
    okruh = request.GET.get('r')

    if mesto_hladane:
        # OPRAVA: Pridané _ pre tretiu hodnotu, aby nevznikal ValueError
        h_lat, h_lon, _ = ziskaj_suradnice(mesto_hladane)

        if h_lat and h_lon:
            try:
                okruh_val = float(okruh) if okruh else None
                if okruh_val:
                    id_v_okruhu = []
                    vsetky = inzeraty.filter(lat__isnull=False, lon__isnull=False).only('id', 'lat', 'lon')
                    
                    for inz in vsetky:
                        vzdialenost = haversine(h_lon, h_lat, inz.lon, inz.lat)
                        if vzdialenost <= okruh_val:
                            id_v_okruhu.append(inz.id)
                    
                    inzeraty = inzeraty.filter(id__in=id_v_okruhu)
                else:
                    inzeraty = inzeraty.filter(lokalita__icontains=mesto_hladane)
            except ValueError:
                inzeraty = inzeraty.filter(lokalita__icontains=mesto_hladane)
        else:
            inzeraty = inzeraty.filter(lokalita__icontains=mesto_hladane)

    return render(request, 'home.html', {'inzeraty': inzeraty})

@login_required
def pridat_inzerat(request):
    if request.method == 'POST':
        form = InzeratForm(request.POST, request.FILES)
        if form.is_valid():
            inzerat = form.save(commit=False)
            inzerat.autor = request.user
            
            surova_lokalita = request.POST.get('lokalita', '')
            # Získame lat, lon aj oficiálny názov z API
            lat, lon, pekny_nazov = ziskaj_suradnice(surova_lokalita)
            
            if lat and lon:
                inzerat.lat = lat
                inzerat.lon = lon
                inzerat.lokalita = pekny_nazov  # Tu sa "budapest" zmení na "Budapešť"
            else:
                inzerat.lokalita = surova_lokalita.split(',')[0].strip()

            obrazky = request.FILES.getlist('dodatocne_obrazky')
            if obrazky:
                inzerat.obrazok = obrazky[0]
                inzerat.save()
                for f in obrazky[1:]:
                    InzeratObrazok.objects.create(inzerat=inzerat, obrazok=f)
            else:
                inzerat.save()
                
            return HttpResponse(status=200)
        else:
            return JsonResponse(form.errors, status=400)
            
    odhad = zisti_odhad_lokality(request)
    form = InzeratForm()
    return render(request, 'inzeraty/pridat_inzerat.html', {
        'form': form, 
        'odhad_lokality': odhad
    })

@login_required
def upravit_inzerat(request, pk):
    inzerat = get_object_or_404(Inzerat.objects.prefetch_related('dodatocne_obrazky'), pk=pk)
    
    if inzerat.autor != request.user:
        raise PermissionDenied 
    
    if request.method == 'POST':
        stara_lokalita = inzerat.lokalita
        form = InzeratForm(request.POST, request.FILES, instance=inzerat)
        
        if form.is_valid():
            inzerat = form.save(commit=False)
            
            surova_lokalita = request.POST.get('lokalita', '')
            
            # Ak sa text lokality zmenil, skontrolujeme API
            if surova_lokalita != stara_lokalita:
                lat, lon, pekny_nazov = ziskaj_suradnice(surova_lokalita)
                if lat and lon:
                    inzerat.lat = lat
                    inzerat.lon = lon
                    inzerat.lokalita = pekny_nazov
                else:
                    inzerat.lokalita = surova_lokalita.split(',')[0].strip()

            obrazky = request.FILES.getlist('dodatocne_obrazky')
            if obrazky:
                if inzerat.obrazok and os.path.isfile(inzerat.obrazok.path):
                    os.remove(inzerat.obrazok.path)
                
                for starafoto in inzerat.dodatocne_obrazky.all():
                    if starafoto.obrazok and os.path.isfile(starafoto.obrazok.path):
                        os.remove(starafoto.obrazok.path)
                
                inzerat.dodatocne_obrazky.all().delete()
                inzerat.obrazok = obrazky[0]
                inzerat.save()

                for f in obrazky[1:]:
                    InzeratObrazok.objects.create(inzerat=inzerat, obrazok=f)
            else:
                inzerat.save()
            
            return HttpResponse(status=200)
        else:
            return JsonResponse(form.errors, status=400)
            
    form = InzeratForm(instance=inzerat)
    return render(request, 'inzeraty/pridat_inzerat.html', {
        'form': form, 
        'inzerat': inzerat
    })

@login_required
def odstranit_inzerat(request, pk):
    inzerat = get_object_or_404(Inzerat, pk=pk)
    if inzerat.autor != request.user:
        return redirect('home')

    if request.method == 'POST':
        # Pomocná funkcia na bezpečné zmazanie
        def safe_delete(file_field):
            try:
                if file_field and os.path.isfile(file_field.path):
                    os.remove(file_field.path)
            except: pass

        safe_delete(inzerat.obrazok)
        for foto in inzerat.dodatocne_obrazky.all():
            safe_delete(foto.obrazok)
            
        inzerat.delete()
        return redirect('home')

    return render(request, 'inzeraty/potvrdit_zmazanie.html', {'inzerat': inzerat})

def detail_inzeratu(request, pk):
    inzerat = get_object_or_404(Inzerat, pk=pk)
    return render(request, 'inzeraty/detail.html', {'inzerat': inzerat})


# --- CHAT A SPRÁVY ---


@login_required
def zacat_chat(request, inzerat_id):
    inzerat = get_object_or_404(Inzerat, id=inzerat_id)
    if inzerat.autor == request.user:
        return redirect('detail_inzeratu', pk=inzerat.id) 

    konverzacia, created = Konverzacia.objects.get_or_create(
        inzerat=inzerat,
        kupujuci=request.user,
        predajca=inzerat.autor
    )
    return redirect('chat_detail', inzerat_id=inzerat.id)

@login_required
def chat_detail(request, inzerat_id):
    inzerat = get_object_or_404(Inzerat, id=inzerat_id)
    konverzacia = Konverzacia.objects.filter(inzerat=inzerat).filter(
        models.Q(kupujuci=request.user) | models.Q(predajca=request.user)
    ).first()

    spravy = []
    if konverzacia:
        konverzacia.spravy.filter(precitane=False).exclude(odosielatel=request.user).update(precitane=True)
        spravy = konverzacia.spravy.all().order_by('poslane')

    return render(request, 'inzeraty/chat_detail.html', {
        'inzerat': inzerat,
        'konverzacia': konverzacia,
        'spravy': spravy
    })

@login_required
def moje_chaty(request):
    chaty = Konverzacia.objects.filter(
        models.Q(kupujuci=request.user) | models.Q(predajca=request.user)
    ).order_by('-vytvorene') 
    return render(request, 'inzeraty/moje_chaty.html', {'chaty': chaty})

@login_required
def poslat_spravu(request, inzerat_id):
    inzerat = get_object_or_404(Inzerat, id=inzerat_id)
    
    if request.method == 'POST':
        konverzacia = Konverzacia.objects.filter(inzerat=inzerat).filter(
            models.Q(kupujuci=request.user) | models.Q(predajca=request.user)
        ).first()

        if not konverzacia:
             konverzacia = Konverzacia.objects.create(
                inzerat=inzerat,
                predajca=inzerat.autor,
                kupujuci=request.user
            )
        
        text = request.POST.get('text', '').strip()
        obrazok = request.FILES.get('obrazok')
        video = request.FILES.get('video')

        if not text and not obrazok and not video:
            return JsonResponse({'status': 'empty'}, status=400)

        sprava = Sprava.objects.create(
            konverzacia=konverzacia,
            odosielatel=request.user,
            text=text,
            obrazok=obrazok,
            video=video
        )

        return JsonResponse({
            'status': 'success',
            'cas': sprava.poslane.strftime("%H:%M"),
        })
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def nacitat_spravy(request, konverzacia_id):
    konverzacia = get_object_or_404(Konverzacia, id=konverzacia_id)
    spravy = Sprava.objects.filter(konverzacia=konverzacia).order_by('poslane')
    return render(request, 'inzeraty/chat_messages_partial.html', {
        'spravy': spravy,
        'user': request.user
    })

@login_required
def zmazat_spravu(request, sprava_id):
    sprava = get_object_or_404(Sprava, id=sprava_id, odosielatel=request.user)
    if request.method == 'POST':
        konverzacia = sprava.konverzacia
        sprava.delete()
        
        if not konverzacia.spravy.exists():
            konverzacia.delete()
            return JsonResponse({'status': 'conversation_deleted'}, status=200)
            
        return HttpResponse(status=200)
    return HttpResponse(status=400)

@login_required
def upravit_spravu(request, sprava_id):
    sprava = get_object_or_404(Sprava, id=sprava_id, odosielatel=request.user)
    if request.method == 'POST':
        novy_text = request.POST.get('text', '').strip()
        if not novy_text and not sprava.obrazok:
            return HttpResponse("Chyba", status=400)
        sprava.text = novy_text
        sprava.save(update_fields=['text'])
        return HttpResponse(status=200)
    return HttpResponse(status=400)