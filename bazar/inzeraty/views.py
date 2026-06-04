import os
import requests
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.core.cache import cache
from .forms import InzeratForm
from .models import Inzerat, Konverzacia, Sprava, InzeratObrazok
from .utils import vygeneruj_skryte_tagy, ziskaj_ai_analyzu
from django.views.decorators.http import require_POST
from accounts.models import Report
from django.utils import timezone
from datetime import timedelta

# ==========================================================================
# --- POMOCNÉ FUNKCIE (Upratané a zjednodušené) ---
# ==========================================================================

def ziskaj_suradnice(mesto_text):
    """Premení názov mesta na lat, lon a vráti aj oficiálny názov mesta s diakritikou."""
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
            lat, lon = float(data[0]['lat']), float(data[0]['lon'])
            addr = data[0].get('address', {})
            pekny_nazov = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('municipality') or addr.get('hamlet')
            return lat, lon, pekny_nazov or data[0].get('display_name', '').split(',')[0]
    except Exception as e:
        print(f"Chyba pri získavaní súradníc: {e}")
    return None, None, None

def zisti_odhad_lokality(request):
    """Získa približnú lokalitu z IP adresy."""
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
    if ip == '127.0.0.1': 
        ip = '178.143.32.253' # Simulácia pre localhost

    try:
        data = requests.get(f'http://ip-api.com/json/{ip}', timeout=2).json()
        if data.get('status') == 'success':
            return f"{data.get('city')}, {data.get('country')}"
    except: pass
    return ""

def _spracuj_lokalitu_a_fotky(request, inzerat, surova_lokalita, obrazky):
    """Zjednotená interná logika pre ukladanie fotiek a polohy použivaná pri Create aj Update."""
    # 1. Geolokácia
    lat, lon, pekny_nazov = ziskaj_suradnice(surova_lokalita)
    if lat and lon:
        inzerat.lat, inzerat.lon, inzerat.lokalita = lat, lon, pekny_nazov
    else:
        inzerat.lokalita = surova_lokalita.split(',')[0].strip()

    # 2. Uloženie obrázkov
    if obrazky:
        inzerat.obrazok = obrazky[0]
        inzerat.save()
        for f in obrazky[1:]:
            InzeratObrazok.objects.create(inzerat=inzerat, obrazok=f)
    else:
        inzerat.save()

def _bezpecne_zmaz_subor(file_field):
    """Bezpečne odstráni súbor z disku ak existuje."""
    try:
        if file_field and os.path.isfile(file_field.path):
            os.remove(file_field.path)
    except: pass


# ==========================================================================
# --- INZERÁTY (Pridanie, Úprava, Mazanie) ---
# ==========================================================================

@login_required
def pridat_inzerat(request):
    if request.method == 'POST':
        user_key = f"spam_check_{request.user.id}"
        if cache.get(user_key):
            return JsonResponse({'error': 'Prosím, počkajte 30 sekúnd.'}, status=429)

        form = InzeratForm(request.POST, request.FILES)
        if form.is_valid():
            inzerat = form.save(commit=False)
            inzerat.autor = request.user
            inzerat.skryte_tagy = vygeneruj_skryte_tagy(inzerat)
            
            _spracuj_lokalitu_a_fotky(
                request, inzerat, 
                request.POST.get('lokalita', ''), 
                request.FILES.getlist('dodatocne_obrazky')
            )
            
            cache.set(user_key, True, 30)
            return HttpResponse(status=200)
        return JsonResponse(form.errors, status=400)
            
    return render(request, 'inzeraty/pridat_inzerat.html', {
        'form': InzeratForm(), 'odhad_lokality': zisti_odhad_lokality(request)
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
            obrazky = request.FILES.getlist('dodatocne_obrazky')

            # Ak nahráva nové fotky, staré kompletne vyčistíme z disku aj DB
            if obrazky:
                _bezpecne_zmaz_subor(inzerat.obrazok)
                for starafoto in inzerat.dodatocne_obrazky.all():
                    _bezpecne_zmaz_subor(starafoto.obrazok)
                inzerat.dodatocne_obrazky.all().delete()

            # Zisťujeme súradnice iba ak sa lokalita reálne zmenila
            lokalita_na_spracovanie = surova_lokalita if surova_lokalita != stara_lokalita else ""
            _spracuj_lokalitu_a_fotky(request, inzerat, lokalita_na_spracovanie or stara_lokalita, obrazky)
            
            return HttpResponse(status=200)
        return JsonResponse(form.errors, status=400)
            
    return render(request, 'inzeraty/pridat_inzerat.html', {'form': InzeratForm(instance=inzerat), 'inzerat': inzerat})

@login_required
def odstranit_inzerat(request, pk):
    inzerat = get_object_or_404(Inzerat, pk=pk)
    if inzerat.autor != request.user:
        return redirect('home')

    if request.method == 'POST':
        _bezpecne_zmaz_subor(inzerat.obrazok)
        for foto in inzerat.dodatocne_obrazky.all():
            _bezpecne_zmaz_subor(foto.obrazok)
        inzerat.delete()
        return redirect('home')

    return render(request, 'inzeraty/potvrdit_zmazanie.html', {'inzerat': inzerat})

def detail_inzeratu(request, pk):
    # Vypočítame hraničný čas (teraz mínus 30 dní)
    hranica_expiracie = timezone.now() - timedelta(days=30)
    
    # Získame inzerát, ktorý musí byť aktívny A zároveň vytvorený po tejto hranici
    inzerat = get_object_or_404(
        Inzerat, 
        pk=pk, 
        je_aktivny=True, 
        vytvorene__gte=hranica_expiracie
    )
    
    return render(request, 'inzeraty/detail.html', {'inzerat': inzerat})

@login_required
def predlzit_inzerat(request, pk):
    if request.method == 'POST':
        # Zabezpečíme, aby používateľ mohol predĺžiť iba SVOJ vlastný inzerát
        inzerat = get_object_or_404(Inzerat, pk=pk, autor=request.user)
        
        # Nastavíme ho ako aktívny a reštartujeme 30-dňovú lehotu na 'teraz'
        inzerat.vytvorene = timezone.now()
        inzerat.je_aktivny = True
        inzerat.save(update_fields=['vytvorene', 'je_aktivny'])
        
        # Presmerujeme ho späť na profil, kde uvidí zmenu
        return redirect('profil')  # <-- Prípadne použi 'accounts:profil' ak máš namespace
        
    return HttpResponse(status=400)



def ai_analyza_ajax(request, pk):
    return JsonResponse({'analyza': ziskaj_ai_analyzu(get_object_or_404(Inzerat, pk=pk))})


# ==========================================================================
# --- CHAT A SPRÁVY ---
# ==========================================================================

@login_required
def zacat_chat(request, inzerat_id):
    inzerat = get_object_or_404(Inzerat, id=inzerat_id)
    if inzerat.autor == request.user:
        return redirect('detail_inzeratu', pk=inzerat.id) 

    Konverzacia.objects.get_or_create(inzerat=inzerat, kupujuci=request.user, predajca=inzerat.autor)
    return redirect('chat_detail', inzerat_id=inzerat.id)

@login_required
def chat_detail(request, inzerat_id):
    inzerat = get_object_or_404(Inzerat, id=inzerat_id)
    konverzacia = Konverzacia.objects.filter(inzerat=inzerat).filter(Q(kupujuci=request.user) | Q(predajca=request.user)).first()

    spravy = []
    if konverzacia:
        konverzacia.spravy.filter(precitane=False).exclude(odosielatel=request.user).update(precitane=True)
        spravy = konverzacia.spravy.all().order_by('poslane')

    return render(request, 'inzeraty/chat_detail.html', {'inzerat': inzerat, 'konverzacia': konverzacia, 'spravy': spravy})

@login_required
def moje_chaty(request):
    chaty = Konverzacia.objects.filter(Q(kupujuci=request.user) | Q(predajca=request.user)).order_by('-vytvorene') 
    return render(request, 'inzeraty/moje_chaty.html', {'chaty': chaty})

@login_required
def poslat_spravu(request, inzerat_id):
    inzerat = get_object_or_404(Inzerat, id=inzerat_id)
    if request.method == 'POST':
        konverzacia = Konverzacia.objects.filter(inzerat=inzerat).filter(Q(kupujuci=request.user) | Q(predajca=request.user)).first()
        if not konverzacia:
            konverzacia = Konverzacia.objects.create(inzerat=inzerat, predajca=inzerat.autor, kupujuci=request.user)
        
        text = request.POST.get('text', '').strip()
        if not text and not request.FILES.get('obrazok') and not request.FILES.get('video'):
            return JsonResponse({'status': 'empty'}, status=400)

        sprava = Sprava.objects.create(
            konverzacia=konverzacia, odosielatel=request.user, text=text,
            obrazok=request.FILES.get('obrazok'), video=request.FILES.get('video')
        )
        return JsonResponse({'status': 'success', 'cas': sprava.poslane.strftime("%H:%M")})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def nacitat_spravy(request, konverzacia_id):
    spravy = Sprava.objects.filter(konverzacia_id=konverzacia_id).order_by('poslane')
    return render(request, 'inzeraty/chat_messages_partial.html', {'spravy': spravy, 'user': request.user})

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




@login_required
@require_POST
def nahlasit_inzerat(request, pk):
    inzerat = get_object_or_404(Inzerat, pk=pk)
    
    # Používateľ nemôže nahlásiť vlastný inzerát
    if inzerat.autor == request.user:
        return JsonResponse({'error': 'Nemôžete nahlásiť vlastný inzerát.'}, status=400)
        
    dovod = request.POST.get('dovod')
    popis = request.POST.get('popis', '')
    
    if not dovod:
        return JsonResponse({'error': 'Musíte vybrať dôvod nahlásenia.'}, status=400)
        
    # Skontrolujeme, či už tento inzerát náhodou nahlásil
    strix = Report.objects.filter(zalobca=request.user, inzerat=inzerat).exists()
    if strix:
        return JsonResponse({'error': 'Tento inzerát ste už nahlásili.'}, status=400)
        
    # Vytvorenie nahlásenia
    Report.objects.create(
        zalobca=request.user,
        inzerat=inzerat,
        dovod=dovod,
        popis=popis
    )
    
    return JsonResponse({'success': 'Inzerát bol úspešne nahlásený. Admini situáciu preveria.'})