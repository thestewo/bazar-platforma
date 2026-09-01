import os
import requests
import traceback
import gc  # Uvoľnenie pamäte (odomknutie súborov pred mazaním)
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.core.cache import cache
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.views.decorators.csrf import csrf_protect
from django.urls import reverse

from .forms import InzeratForm
from .models import Inzerat, Konverzacia, Sprava, InzeratObrazok
from .utils import vygeneruj_skryte_tagy, ziskaj_ai_analyzu, hlavna_kontrola_obsahu
from accounts.models import Report

# ==========================================================================
# --- POMOCNÉ FUNKCIE ---
# ==========================================================================

@csrf_protect
def vymazat_fotku_ajax(request, fotka_id):
    if request.method == 'POST':
        fotka = get_object_or_404(InzeratObrazok, id=fotka_id)
        if fotka.inzerat.autor != request.user:
            return JsonResponse({'success': False, 'error': 'Nemáš právo na túto akciu'}, status=403)
        if fotka.obrazok: 
            _bezpecne_zmaz_subor(fotka.obrazok)
        fotka.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Neplatná metóda'}, status=400)

def _bezpecne_zmaz_subor(file_field):
    """Pomocná funkcia na okamžité bezpečné vymazanie súboru a vyčistenie ImageKit cache"""
    if file_field:
        try:
            gc.collect()  # Vynútime Python, aby zatvoril všetky streamy k súboru
            file_field.delete(save=False)
        except Exception as e:
            print(f"Chyba pri mazaní súboru z disku: {e}")

def ziskaj_suradnice(mesto_text):
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
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
    if ip == '127.0.0.1': 
        ip = '178.143.32.253'
    try:
        data = requests.get(f'http://ip-api.com/json/{ip}', timeout=2).json()
        if data.get('status') == 'success':
            return data.get('city', '') 
    except: pass
    return ""


# ==========================================================================
# --- INZERÁTY (Pridanie, Úprava, Mazanie) ---
# ==========================================================================

@login_required
def pridat_inzerat(request):
    if request.method == 'POST':
        user_key = f"spam_check_{request.user.id}"
        if cache.get(user_key):
            return JsonResponse({'error': 'Prosím, počkajte 30 sekúnd.'}, status=429)

        hlavna_fotka_subor = request.FILES.get('obrazok')
        list_vedlajsich_fotiek = request.FILES.getlist('fotky')
        form = InzeratForm(request.POST, request.FILES)
        
        if form.is_valid():
            # 1. Pripravíme text a surové fotky z pamäte pre AI kontrolu
            nazov = form.cleaned_data.get('nazov', '')
            popis = form.cleaned_data.get('popis', '')
            skumany_text = f"Názov: {nazov}\nPopis: {popis}"
            
            pripravene_fotky_pre_ai = []
            if hlavna_fotka_subor:
                try: hlavna_fotka_subor.seek(0)
                except: pass
                pripravene_fotky_pre_ai.append(hlavna_fotka_subor)
            
            if list_vedlajsich_fotiek:
                for f in list_vedlajsich_fotiek:
                    try: f.seek(0)
                    except: pass
                    pripravene_fotky_pre_ai.append(f)

            # 2. Spustíme AI analýzu PRED akýmkoľvek uložením na disk
            try:
                vysledok_kontroly = hlavna_kontrola_obsahu(skumany_text, pripravene_fotky_pre_ai)
                status = vysledok_kontroly.get('status', 'Schválený')
                dovod_zamietnutia = vysledok_kontroly.get('dovod', '')
                kontrola_zlyhala = False
            except Exception as ai_error:
                status = 'Schválený'
                dovod_zamietnutia = f"AI zlyhalo: {str(ai_error)}"
                kontrola_zlyhala = True

            # Ak AI inzerát zamietne, hneď končíme. Na disk sa nič neuložilo.
            if status == "Zamietnutý":
                return JsonResponse({'error': f"Inzerát bol zamietnutý cenzúrou: {dovod_zamietnutia}"}, status=400)

            # 3. Ak prešiel, bezpečne ho zapíšeme do DB a na disk
            try:
                with transaction.atomic():
                    inzerat = form.save(commit=False)
                    inzerat.autor = request.user
                    inzerat.lokalita = request.POST.get('lokalita', '')
                    inzerat.status = status
                    inzerat.dovod_zamietnutia = dovod_zamietnutia
                    inzerat.kontrola_zlyhala = kontrola_zlyhala
                    
                    if hlavna_fotka_subor:
                        inzerat.obrazok = hlavna_fotka_subor

                    inzerat.save()

                    if list_vedlajsich_fotiek:
                        for f in list_vedlajsich_fotiek:
                            try: f.seek(0)
                            except: pass
                            InzeratObrazok.objects.create(inzerat=inzerat, obrazok=f)

                    if 'vygeneruj_skryte_tagy' in globals():
                        inzerat.skryte_tagy = vygeneruj_skryte_tagy(inzerat)
                    
                    inzerat.save()
                        
                return JsonResponse({
                    'status': 'success',
                    'success': True,
                    'redirect_url': reverse('detail_inzeratu', kwargs={'pk': inzerat.id})
                }, status=200)

            except Exception as celkova_chyba:
                return JsonResponse({'error': f'Systémová chyba pri ukladaní: {str(celkova_chyba)}'}, status=500)
                
        return JsonResponse({'error': 'Formulár obsahuje neplatné údaje.', 'errors': form.errors}, status=400)
            
    return render(request, 'inzeraty/pridat_inzerat.html', {'form': InzeratForm(), 'odhad_lokality': zisti_odhad_lokality(request)})


@login_required
def upravit_inzerat(request, pk):
    inzerat = get_object_or_404(Inzerat.objects.prefetch_related('dodatocne_obrazky'), pk=pk)
    if inzerat.autor != request.user:
        return JsonResponse({'error': 'Nemáte oprávnenie na úpravu tohto inzerátu.'}, status=403)
    
    if request.method == 'POST':
        stara_lokalita = inzerat.lokalita
        hlavna_fotka_subor = request.FILES.get('obrazok')
        list_vedlajsich_fotiek = request.FILES.getlist('fotky')
        stara_hlavna_fotka = inzerat.obrazok

        form = InzeratForm(request.POST, request.FILES, instance=inzerat)
        
        if form.is_valid():
            # 1. Zistíme, či úprava vyžaduje opätovnú AI kontrolu
            vyzaduje_ai_kontrolu = bool(hlavna_fotka_subor or list_vedlajsich_fotiek or form.has_changed())
            
            status = inzerat.status
            dovod_zamietnutia = inzerat.dovod_zamietnutia
            kontrola_zlyhala = inzerat.kontrola_zlyhala

            if vyzaduje_ai_kontrolu:
                # Pripravíme budúci stav textu z formulára
                nazov = form.cleaned_data.get('nazov', '')
                popis = form.cleaned_data.get('popis', '')
                skumany_text = f"Názov: {nazov}\nPopis: {popis}"
                
                # OPRAVA: Posielame na AI kontrolu výhradne IBA nové fotky z requestu, staré netreba znova skenovať
                ai_list_fotiek = []
                
                if hlavna_fotka_subor:
                    try: hlavna_fotka_subor.seek(0)
                    except: pass
                    ai_list_fotiek.append(hlavna_fotka_subor)
                    
                if list_vedlajsich_fotiek:
                    for f in list_vedlajsich_fotiek:
                        try: f.seek(0)
                        except: pass
                        ai_list_fotiek.append(f)

                # Spustíme kontrolu v pamäti PRED uložením zmien
                try:
                    vysledok_kontroly = hlavna_kontrola_obsahu(skumany_text, ai_list_fotiek)
                    status = vysledok_kontroly.get('status', 'Schválený')
                    dovod_zamietnutia = vysledok_kontroly.get('dovod', '')
                    kontrola_zlyhala = False
                except Exception as e:
                    status = 'Schválený'
                    dovod_zamietnutia = "AI nedostupné počas úpravy"
                    kontrola_zlyhala = True

            # Ak AI úpravu zamietne, ihneď ju zrušíme. V databáze aj na disku zostáva starý inzerát nedotknutý.
            if status == "Zamietnutý":
                return JsonResponse({'error': f"Inzerát bol po úprave zamietnutý cenzúrou: {dovod_zamietnutia}"}, status=400)

            # 2. Ak úprava prešla, až teraz prepíšeme dáta v DB a uložíme nové súbory
            stare_fotky_na_zmazanie_po_commite = []
            try:
                with transaction.atomic():
                    inzerat = form.save(commit=False)
                    surova_lokalita = request.POST.get('lokalita', '')
                    inzerat.status = status
                    inzerat.dovod_zamietnutia = dovod_zamietnutia
                    inzerat.kontrola_zlyhala = kontrola_zlyhala
                    
                    if hlavna_fotka_subor:
                        if stara_hlavna_fotka:
                            stare_fotky_na_zmazanie_po_commite.append(stara_hlavna_fotka)
                        inzerat.obrazok = hlavna_fotka_subor

                    inzerat.save()

                    if list_vedlajsich_fotiek:
                        # Odložíme staré vedľajšie fotky na zmazanie z disku
                        for stara_foto in inzerat.dodatocne_obrazky.all():
                            if stara_foto.obrazok:
                                stare_fotky_na_zmazanie_po_commite.append(stara_foto.obrazok)
                        inzerat.dodatocne_obrazky.all().delete()

                        # Zapíšeme nové
                        for f in list_vedlajsich_fotiek:
                            try: f.seek(0)
                            except: pass
                            InzeratObrazok.objects.create(inzerat=inzerat, obrazok=f)

                    # Spracovanie lokality
                    if surova_lokalita and surova_lokalita != stara_lokalita:
                        lat, lon, pekny_nazov = ziskaj_suradnice(surova_lokalita)
                        if lat and lon:
                            inzerat.lat, inzerat.lon, inzerat.lokalita = lat, lon, pekny_nazov
                        else:
                            inzerat.lokalita = surova_lokalita.split(',')[0].strip()
                    
                    if 'vygeneruj_skryte_tagy' in globals():
                        inzerat.skryte_tagy = vygeneruj_skryte_tagy(inzerat)
                    
                    inzerat.save()

                # --- ZÓNA ÚSPECHU ---
                # Až keď celý zápis úspešne zbehol (commit), bezpečne vymažeme staré prepísané fotky
                gc.collect()
                for stara_f in stare_fotky_na_zmazanie_po_commite:
                    _bezpecne_zmaz_subor(stara_f)

                return JsonResponse({
                    'status': 'success',
                    'success': True,
                    'redirect_url': reverse('detail_inzeratu', kwargs={'pk': inzerat.id})
                }, status=200)

            except Exception as celkova_chyba:
                traceback.print_exc()
                return JsonResponse({'error': f'Systémová chyba pri úprave: {str(celkova_chyba)}'}, status=500)
                
        return JsonResponse({'error': 'Formulár obsahuje neplatné údaje.', 'errors': form.errors}, status=400)
            
    return render(request, 'inzeraty/pridat_inzerat.html', {'form': InzeratForm(instance=inzerat), 'inzerat': inzerat})


def odstranit_inzerat(request, pk):
    inzerat = get_object_or_404(Inzerat, pk=pk)
    
    if request.method == 'POST':
        try:
            gc.collect()  
            if inzerat.obrazok:
                inzerat.obrazok.delete(save=False)
            
            if hasattr(inzerat, 'dodatocne_obrazky'):
                for foto in inzerat.dodatocne_obrazky.all(): 
                    if foto.obrazok:
                        foto.obrazok.delete(save=False)
            elif hasattr(inzerat, 'inzeratobrazok_set'):
                for foto in inzerat.inzeratobrazok_set.all():
                    if foto.obrazok:
                        foto.obrazok.delete(save=False)
        except Exception as e:
            print(f"Upozornenie pri mazaní súboru z disku: {e}")

        inzerat.delete() 
        return redirect('/')  

    return render(request, 'inzeraty/potvrdit_zmazanie.html', {'inzerat': inzerat})


def detail_inzeratu(request, pk):
    hranica_expiracie = timezone.now() - timedelta(days=30)
    inzerat = get_object_or_404(Inzerat, pk=pk, je_aktivny=True, vytvorene__gte=hranica_expiracie)
    return render(request, 'inzeraty/detail.html', {'inzerat': inzerat})

@login_required
def predlzit_inzerat(request, pk):
    if request.method == 'POST':
        inzerat = get_object_or_404(Inzerat, pk=pk, autor=request.user)
        inzerat.vytvorene = timezone.now()
        inzerat.je_aktivny = True
        inzerat.save(update_fields=['vytvorene', 'je_aktivny'])
        return redirect('profil')
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
    return redirect('chat_detail', inzerat_id=inzerat.id)

@login_required
def chat_detail(request, inzerat_id):
    inzerat = get_object_or_404(Inzerat, id=inzerat_id) 
    kupujuci_id = request.GET.get('kupujuci_id')
    
    # Ak je používateľ admin a v URL posielame ID kupujúceho:
    if request.user.is_staff and kupujuci_id:
        konverzacia = Konverzacia.objects.filter(
            inzerat=inzerat, 
            kupujuci_id=kupujuci_id
        ).first()
    else:
        # Štandardná logika pre normálnych používateľov
        konverzacia = Konverzacia.objects.filter(
            inzerat=inzerat
        ).filter(
            Q(kupujuci=request.user) | Q(predajca=request.user)
        ).first()
        
    spravy = []
    if konverzacia:
        # Označiť správy ako prečítané len vtedy, ak si chat pozerá bežný účastník (nie admin pri kontrole)
        if not request.user.is_staff:
            konverzacia.spravy.filter(precitane=False).exclude(odosielatel=request.user).update(precitane=True)
            
        spravy = konverzacia.spravy.all().order_by('poslane')
        
    return render(request, 'inzeraty/chat_detail.html', {
        'inzerat': inzerat, 
        'konverzacia': konverzacia, 
        'spravy': spravy
    })

@login_required
def moje_chaty(request):
    chaty = Konverzacia.objects.filter(Q(kupujuci=request.user) | Q(predajca=request.user)).filter(spravy__isnull=False).distinct().order_by('-vytvorene') 
    return render(request, 'inzeraty/moje_chaty.html', {'chaty': chaty})

@login_required
def poslat_spravu(request, inzerat_id):
    inzerat = get_object_or_404(Inzerat, id=inzerat_id)
    if request.method == 'POST':
        konverzacia = Konverzacia.objects.filter(inzerat=inzerat).filter(Q(kupujuci=request.user) | Q(predajca=request.user)).first()
        text = request.POST.get('text', '').strip()
        if not text and not request.FILES.get('obrazok') and not request.FILES.get('video'):
            return JsonResponse({'status': 'empty'}, status=400)
        if not konverzacia:
            konverzacia = Konverzacia.objects.create(inzerat=inzerat, predajca=inzerat.autor, kupujuci=request.user)
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
def nahlasit_spravu(request, sprava_id):
    sprava = get_object_or_404(Sprava, id=sprava_id)
    
    # Používateľ nemôže nahlásiť svoju vlastnú správu
    if sprava.odosielatel == request.user:
        return JsonResponse({'error': 'Nemôžete nahlásiť vlastnú správu.'}, status=400)
        
    dovod = request.POST.get('dovod')
    popis = request.POST.get('popis', '')
    
    if not dovod:
        return JsonResponse({'error': 'Musíte vybrať dôvod nahlásenia.'}, status=400)
        
    # Kontrola, či už tento používateľ danú správu nenahlásil
    if Report.objects.filter(zalobca=request.user, sprava=sprava).exists():
        return JsonResponse({'error': 'Túto správu ste už nahlásili.'}, status=400)
        
    # OPRAVENÉ: Ak adminovi chýba textový popis, predvyplníme ho samotným textom správy
    if not popis.strip():
        popis = f"Nahlásený text správy: {sprava.text if sprava.text else '[Súbor/Príloha]'}"

    # Vytvorenie reportu v databáze (PRIDANÝ obvineny A inzerat)
    Report.objects.create(
        zalobca=request.user, 
        obvineny=sprava.odosielatel,
        inzerat=sprava.konverzacia.inzerat,
        sprava=sprava, 
        dovod=dovod, 
        popis=popis
    )
    
    return JsonResponse({'success': 'Správa bola úspešne nahlásená. Admini situáciu preveria.'})

@login_required
@require_POST
def nahlasit_inzerat(request, pk):
    inzerat = get_object_or_404(Inzerat, pk=pk)
    if inzerat.autor == request.user:
        return JsonResponse({'error': 'Nemôžete nahlásiť vlastný inzerát.'}, status=400)
    dovod = request.POST.get('dovod')
    popis = request.POST.get('popis', '')
    if not dovod:
        return JsonResponse({'error': 'Musíte vybrať dôvod nahlásenia.'}, status=400)
    if Report.objects.filter(zalobca=request.user, inzerat=inzerat).exists():
        return JsonResponse({'error': 'Tento inzerát ste už nahlásili.'}, status=400)
    Report.objects.create(zalobca=request.user, inzerat=inzerat, dovod=dovod, popis=popis)
    return JsonResponse({'success': 'Inzerát bol úspešne nahlásený. Admini situáciu preveria.'})