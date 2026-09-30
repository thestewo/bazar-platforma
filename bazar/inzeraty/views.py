import traceback, gc, requests
from datetime import timedelta
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.core.cache import cache
from django.views.decorators.http import require_POST
from django.utils import timezone
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

def _bezpecne_zmaz_subor(file_field):
    """Okamžité bezpečné vymazanie súboru z disku a vyčistenie streamov."""
    if file_field:
        try:
            gc.collect()
            file_field.delete(save=False)
        except Exception as e:
            print(f"Chyba pri mazaní súboru z disku: {e}")

@csrf_protect
def vymazat_fotku_ajax(request, fotka_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Neplatná metóda'}, status=400)
    fotka = get_object_or_404(InzeratObrazok, id=fotka_id)
    if fotka.inzerat.autor != request.user:
        return JsonResponse({'success': False, 'error': 'Nemáš právo na túto akciu'}, status=403)
    _bezpecne_zmaz_subor(fotka.obrazok)
    fotka.delete()
    return JsonResponse({'success': True})

def ziskaj_suradnice(mesto_text):
    if not mesto_text or not mesto_text.strip():
        return None, None, None
    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={requests.utils.quote(mesto_text.strip())}&limit=1&addressdetails=1&accept-language=sk&countrycodes=sk"
        data = requests.get(url, headers={'User-Agent': 'NOVU_App_Educational'}, timeout=5).json()
        if data:
            addr = data[0].get('address', {})
            pekny_nazov = (
                addr.get('city') or addr.get('town') or addr.get('village') or 
                addr.get('municipality') or addr.get('hamlet') or addr.get('county') or 
                data[0].get('display_name', '').split(',')[0].strip()
            )
            return float(data[0]['lat']), float(data[0]['lon']), pekny_nazov
    except Exception as e:
        print(f"Chyba pri získavaní súradníc pre '{mesto_text}': {e}")
    return None, None, None

def zisti_odhad_lokality(request):
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
    if ip == '127.0.0.1': 
        ip = '178.143.32.253'
    try:
        data = requests.get(f'http://ip-api.com/json/{ip}', timeout=2).json()
        return data.get('city', '') if data.get('status') == 'success' else ""
    except Exception:
        return ""

def _vyhodnot_ai_kontrolu(form, hlavna_foto, vedlajsie_fotky):
    nazov = form.cleaned_data.get('nazov', '')
    popis = form.cleaned_data.get('popis', '')
    skumany_text = f"Názov: {nazov}\nPopis: {popis if popis else 'Bez popisu'}"
    
    fotky_pre_ai = []
    # Zozbieranie hlavnej aj vedľajších fotiek
    vsetky_fotky = [hlavna_foto] + (vedlajsie_fotky or [])
    
    for f in vsetky_fotky:
        if f:
            try:
                f.seek(0)  # Reset kurzoru súboru, aby ho PIL Image správne prečítal
                fotky_pre_ai.append(f)
            except Exception as e:
                print(f"Chyba pri príprave fotky pre AI: {e}")

    try:
        vysledok = hlavna_kontrola_obsahu(skumany_text, fotky_pre_ai)
        return vysledok.get('status', 'Schválený'), vysledok.get('dovod', ''), False
    except Exception as ai_error:
        return 'Karanténa', f"AI zlyhalo: {str(ai_error)}", True

def _ulozi_inzerat_s_lokalitou_a_fotkami(inzerat, form, surova_lokalita, hlavna_foto, vedlajsie_fotky, stara_lokalita=None):
    """Pomocná funkcia na uloženie inzerátu, geolokácie a obrázkov."""
    inzerat = form.save(commit=False)
    
    if surova_lokalita and surova_lokalita.strip() and (surova_lokalita.strip() != stara_lokalita or inzerat.lat is None):
        lat, lon, pekny_nazov = ziskaj_suradnice(surova_lokalita.strip())
        if lat and lon and pekny_nazov:
            inzerat.lat, inzerat.lon, inzerat.lokalita = lat, lon, pekny_nazov
        else:
            inzerat.lokalita = surova_lokalita.strip().split(',')[0].strip()
    else:
        inzerat.lokalita = surova_lokalita

    if hlavna_foto:
        inzerat.obrazok = hlavna_foto

    inzerat.save()

    if vedlajsie_fotky:
        for f in vedlajsie_fotky:
            try: f.seek(0)
            except Exception: pass
            InzeratObrazok.objects.create(inzerat=inzerat, obrazok=f)

    if 'vygeneruj_skryte_tagy' in globals():
        inzerat.skryte_tagy = vygeneruj_skryte_tagy(inzerat)
        inzerat.save()
    return inzerat

# ==========================================================================
# --- INZERÁTY (Pridanie, Úprava, Mazanie) ---
# ==========================================================================

@login_required
def pridat_inzerat(request):
    if request.method == 'POST':
        if cache.get(f"spam_check_{request.user.id}"):
            return JsonResponse({'error': 'Prosím, počkajte 30 sekúnd.'}, status=429)

        form = InzeratForm(request.POST, request.FILES)
        if form.is_valid():
            hlavna_foto = request.FILES.get('obrazok')
            vedlajsie_fotky = request.FILES.getlist('fotky')

            status, dovod, kontrola_zlyhala = _vyhodnot_ai_kontrolu(form, hlavna_foto, vedlajsie_fotky)
            if status == "Zamietnutý":
                return JsonResponse({'error': f"Inzerát bol zamietnutý cenzúrou: {dovod}"}, status=400)

            try:
                with transaction.atomic():
                    inzerat = form.save(commit=False)
                    inzerat.autor = request.user
                    inzerat.status, inzerat.dovod_zamietnutia, inzerat.kontrola_zlyhala = status, dovod, kontrola_zlyhala
                    
                    inzerat = _ulozi_inzerat_s_lokalitou_a_fotkami(
                        inzerat, form, request.POST.get('lokalita', ''), hlavna_foto, vedlajsie_fotky
                    )

                return JsonResponse({'status': 'success', 'success': True, 'redirect_url': reverse('detail_inzeratu', kwargs={'pk': inzerat.id})})
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
        stara_lokalita, stara_hlavna_fotka = inzerat.lokalita, inzerat.obrazok
        hlavna_foto = request.FILES.get('obrazok')
        vedlajsie_fotky = request.FILES.getlist('fotky')
        form = InzeratForm(request.POST, request.FILES, instance=inzerat)
        
        if form.is_valid():
            vyzaduje_ai = bool(hlavna_foto or vedlajsie_fotky or form.has_changed())
            status, dovod, kontrola_zlyhala = inzerat.status, inzerat.dovod_zamietnutia, inzerat.kontrola_zlyhala

            if vyzaduje_ai:
                status, dovod, kontrola_zlyhala = _vyhodnot_ai_kontrolu(form, hlavna_foto, vedlajsie_fotky)

            if status == "Zamietnutý":
                return JsonResponse({'error': f"Inzerát bol po úprave zamietnutý cenzúrou: {dovod}"}, status=400)

            stare_fotky_na_zmazanie = []
            try:
                with transaction.atomic():
                    inzerat.status, inzerat.dovod_zamietnutia, inzerat.kontrola_zlyhala = status, dovod, kontrola_zlyhala
                    if hlavna_foto and stara_hlavna_fotka:
                        stare_fotky_na_zmazanie.append(stara_hlavna_fotka)

                    if vedlajsie_fotky:
                        stare_fotky_na_zmazanie.extend([f.obrazok for f in inzerat.dodatocne_obrazky.all() if f.obrazok])
                        inzerat.dodatocne_obrazky.all().delete()

                    inzerat = _ulozi_inzerat_s_lokalitou_a_fotkami(
                        inzerat, form, request.POST.get('lokalita', ''), hlavna_foto, vedlajsie_fotky, stara_lokalita
                    )

                for f in stare_fotky_na_zmazanie:
                    _bezpecne_zmaz_subor(f)

                return JsonResponse({'status': 'success', 'success': True, 'redirect_url': reverse('detail_inzeratu', kwargs={'pk': inzerat.id})})
            except Exception as celkova_chyba:
                traceback.print_exc()
                return JsonResponse({'error': f'Systémová chyba pri úprave: {str(celkova_chyba)}'}, status=500)
                
        return JsonResponse({'error': 'Formulár obsahuje neplatné údaje.', 'errors': form.errors}, status=400)
            
    return render(request, 'inzeraty/pridat_inzerat.html', {'form': InzeratForm(instance=inzerat), 'inzerat': inzerat})


def odstranit_inzerat(request, pk):
    inzerat = get_object_or_404(Inzerat, pk=pk)
    if request.method == 'POST':
        try:
            _bezpecne_zmaz_subor(inzerat.obrazok)
            for foto in getattr(inzerat, 'dodatocne_obrazky', inzerat.inzeratobrazok_set).all():
                _bezpecne_zmaz_subor(foto.obrazok)
        except Exception as e:
            print(f"Upozornenie pri mazaní súboru: {e}")

        inzerat.delete() 
        return redirect('/')  

    return render(request, 'inzeraty/potvrdit_zmazanie.html', {'inzerat': inzerat})


def detail_inzeratu(request, pk):
    hranica = timezone.now() - timedelta(days=30)
    return render(request, 'inzeraty/detail.html', {
        'inzerat': get_object_or_404(Inzerat, pk=pk, je_aktivny=True, vytvorene__gte=hranica)
    })

@login_required
def predlzit_inzerat(request, pk):
    if request.method == 'POST':
        inzerat = get_object_or_404(Inzerat, pk=pk, autor=request.user)
        inzerat.vytvorene, inzerat.je_aktivny = timezone.now(), True
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
    return redirect('detail_inzeratu' if inzerat.autor == request.user else 'chat_detail', pk=inzerat.id if inzerat.autor == request.user else inzerat.id)

@login_required
def chat_detail(request, inzerat_id):
    inzerat = get_object_or_404(Inzerat, id=inzerat_id) 
    kupujuci_id = request.GET.get('kupujuci_id')
    
    konverzacia_qs = Konverzacia.objects.filter(inzerat=inzerat)
    konverzacia = konverzacia_qs.filter(kupujuci_id=kupujuci_id).first() if kupujuci_id else konverzacia_qs.filter(Q(kupujuci=request.user) | Q(predajca=request.user)).first()
        
    spravy = []
    if konverzacia:
        if not request.user.is_staff:
            konverzacia.spravy.filter(precitane=False).exclude(odosielatel=request.user).update(precitane=True)
        spravy = konverzacia.spravy.all().order_by('poslane')
    
    unread_count = Sprava.objects.filter(
        Q(konverzacia__kupujuci=request.user) | Q(konverzacia__predajca=request.user),
        precitane=False
    ).exclude(odosielatel=request.user).distinct().count()

    return render(request, 'inzeraty/chat_detail.html', {
        'inzerat': inzerat, 'konverzacia': konverzacia, 'spravy': spravy, 'unread_count': unread_count
    })

@login_required
def moje_chaty(request):
    chaty = Konverzacia.objects.filter(Q(kupujuci=request.user) | Q(predajca=request.user)).filter(spravy__isnull=False).distinct().order_by('-vytvorene') 
    return render(request, 'inzeraty/moje_chaty.html', {'chaty': chaty})

@login_required
def poslat_spravu(request, inzerat_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=400)

    inzerat = get_object_or_404(Inzerat, id=inzerat_id)
    konverzacia_id = request.POST.get('konverzacia_id')
    
    konverzacia = Konverzacia.objects.filter(id=konverzacia_id, inzerat=inzerat).filter(Q(kupujuci=request.user) | Q(predajca=request.user)).first() if konverzacia_id else Konverzacia.objects.filter(inzerat=inzerat, kupujuci=request.user).first()

    text, obrazok, video = request.POST.get('text', '').strip(), request.FILES.get('obrazok'), request.FILES.get('video')
    if not any([text, obrazok, video]):
        return JsonResponse({'status': 'empty'}, status=400)

    if obrazok or video:
        cache_key = f"attachment_limit_{request.user.id}"
        if cache.get(cache_key, 0) >= 5:
            return JsonResponse({'error': 'Poslali ste príliš veľa príloh. Počkajte minútu.'}, status=429)
        cache.set(cache_key, cache.get(cache_key, 0) + 1, timeout=60)

    if not konverzacia:
        if request.user == inzerat.autor:
            return JsonResponse({'error': 'Predajca nemôže začať konverzáciu sám so sebou.'}, status=400)
        konverzacia = Konverzacia.objects.create(inzerat=inzerat, predajca=inzerat.autor, kupujuci=request.user)

    sprava = Sprava.objects.create(konverzacia=konverzacia, odosielatel=request.user, text=text, obrazok=obrazok, video=video)
    return JsonResponse({'status': 'success', 'cas': sprava.poslane.strftime("%H:%M"), 'konverzacia_id': konverzacia.id})


@login_required
def nacitat_spravy(request, konverzacia_id):
    konverzacia = get_object_or_404(Konverzacia, id=konverzacia_id)
    if not request.user.is_staff and request.user in [konverzacia.kupujuci, konverzacia.predajca]:
        konverzacia.spravy.filter(precitane=False).exclude(odosielatel=request.user).update(precitane=True)

    unread_count = Sprava.objects.filter(
        Q(konverzacia__kupujuci=request.user) | Q(konverzacia__predajca=request.user),
        precitane=False
    ).exclude(odosielatel=request.user).distinct().count()

    response = render(request, 'inzeraty/chat_messages_partial.html', {'spravy': konverzacia.spravy.all().order_by('poslane'), 'user': request.user})
    response['X-Unread-Count'] = str(unread_count)
    return response

@login_required
def zmazat_spravu(request, sprava_id):
    if request.method != 'POST':
        return HttpResponse(status=400)
    
    sprava = get_object_or_404(Sprava, id=sprava_id, odosielatel=request.user)
    konverzacia = sprava.konverzacia
    sprava.delete()
    
    if not konverzacia.spravy.exists():
        konverzacia.delete()
        return JsonResponse({'status': 'conversation_deleted'}, status=200)
        
    if not request.user.is_staff:
        konverzacia.spravy.filter(precitane=False).exclude(odosielatel=request.user).update(precitane=True)
        
    return HttpResponse(status=200)

@login_required
def upravit_spravu(request, sprava_id):
    if request.method != 'POST':
        return HttpResponse(status=400)
    sprava = get_object_or_404(Sprava, id=sprava_id, odosielatel=request.user)
    novy_text = request.POST.get('text', '').strip()
    if not novy_text and not sprava.obrazok:
        return HttpResponse("Chyba", status=400)
    sprava.text = novy_text
    sprava.save(update_fields=['text'])
    return HttpResponse(status=200)

@login_required
@require_POST
def nahlasit_spravu(request, sprava_id):
    sprava = get_object_or_404(Sprava, id=sprava_id)
    if sprava.odosielatel == request.user:
        return JsonResponse({'error': 'Nemôžete nahlásiť vlastnú správu.'}, status=400)
        
    dovod, popis = request.POST.get('dovod'), request.POST.get('popis', '').strip()
    if not dovod:
        return JsonResponse({'error': 'Musíte vybrať dôvod nahlásenia.'}, status=400)
    if Report.objects.filter(zalobca=request.user, sprava=sprava).exists():
        return JsonResponse({'error': 'Túto správu ste už nahlásili.'}, status=400)

    Report.objects.create(
        zalobca=request.user, obvineny=sprava.odosielatel,
        inzerat=sprava.konverzacia.inzerat, sprava=sprava, 
        dovod=dovod, popis=popis or f"Nahlásený text správy: {sprava.text or '[Súbor/Príloha]'}"
    )
    return JsonResponse({'success': 'Správa bola úspešne nahlásená. Admini situáciu preveria.'})

@login_required
@require_POST
def nahlasit_inzerat(request, pk):
    inzerat = get_object_or_404(Inzerat, pk=pk)
    if inzerat.autor == request.user:
        return JsonResponse({'error': 'Nemôžete nahlásiť vlastný inzerát.'}, status=400)
    
    dovod, popis = request.POST.get('dovod'), request.POST.get('popis', '')
    if not dovod:
        return JsonResponse({'error': 'Musíte vybrať dôvod nahlásenia.'}, status=400)
    if Report.objects.filter(zalobca=request.user, inzerat=inzerat).exists():
        return JsonResponse({'error': 'Tento inzerát ste už nahlásili.'}, status=400)
        
    Report.objects.create(zalobca=request.user, inzerat=inzerat, dovod=dovod, popis=popis)
    return JsonResponse({'success': 'Inzerát bol úspešne nahlásený. Admini situáciu preveria.'})