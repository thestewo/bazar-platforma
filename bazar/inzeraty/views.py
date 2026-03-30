from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .forms import InzeratForm
from .models import Inzerat
from django.contrib.auth.decorators import login_required
from .models import Konverzacia, Sprava
from django.db import models
from django.http import HttpResponse
import traceback


###check
def detail_inzeratu(request, pk):
    inzerat = get_object_or_404(Inzerat, pk=pk)
    return render(request, 'inzeraty/detail.html', {'inzerat': inzerat})
###check
@login_required # Zabezpečí, že inzerát pridá len prihlásený

def pridat_inzerat(request):
    if request.method == 'POST':
        form = InzeratForm(request.POST, request.FILES) # request.FILES je nutné pre obrázky!
        if form.is_valid():
            inzerat = form.save(commit=False)
            inzerat.autor = request.user
            inzerat.save()
            return redirect('home')
    else:
        form = InzeratForm()
    return render(request, 'inzeraty/pridat_inzerat.html', {'form': form})


def upravit_inzerat(request, pk):
    inzerat = get_object_or_404(Inzerat, pk=pk)
    
    
    if inzerat.autor != request.user:
        raise PermissionDenied 
    
    if request.method == 'POST':
        form = InzeratForm(request.POST, request.FILES, instance=inzerat)
        if form.is_valid():
            form.save()
            return redirect('detail_inzeratu', pk=inzerat.pk)
    else:
        form = InzeratForm(instance=inzerat)
        
    return render(request, 'inzeraty/pridat_inzerat.html', {'form': form, 'inzerat': inzerat})

def odstranit_inzerat(request, pk):
    inzerat = get_object_or_404(Inzerat, pk=pk)

    # Kontrola, či je to autor
    if inzerat.autor != request.user:
        return redirect('home')

    if request.method == 'POST':
        # TOTO SA STANE AŽ PO KLIKNUTÍ NA TLAČIDLO VO FORMULÁRI
        inzerat.je_aktivny = False
        inzerat.save()
        return redirect('home')

    # TOTO SA STANE, KEĎ PRVÝKRÁT KLIKNEŠ NA "ZMAZAŤ" (Zobrazí šablónu)
    return render(request, 'inzeraty/potvrdit_zmazanie.html', {'inzerat': inzerat})

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
    return redirect('chat_detail', konverzacia_id=konverzacia.id)

@login_required
def chat_detail(request, inzerat_id):
    inzerat = get_object_or_404(Inzerat, id=inzerat_id)
    konverzacia = Konverzacia.objects.filter(inzerat=inzerat).filter(
        models.Q(kupujuci=request.user) | models.Q(predajca=request.user)
    ).first()

    if konverzacia:
        # Označíme správy od druhého používateľa za prečítané
        konverzacia.spravy.filter(precitane=False).exclude(odosielatel=request.user).update(precitane=True)
        spravy = konverzacia.spravy.all().order_by('poslane')
    else:
        spravy = []

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
def zmazat_spravu(request, sprava_id):
    sprava = get_object_or_404(Sprava, id=sprava_id, odosielatel=request.user)
    if request.method == 'POST':
        sprava.delete()
        return HttpResponse(status=200) # Dôležité pre AJAX
    return HttpResponse(status=400)


@login_required
def upravit_spravu(request, sprava_id):
    # Získame správu, ktorú vlastní prihlásený používateľ
    sprava = get_object_or_404(Sprava, id=sprava_id, odosielatel=request.user)
    
    if request.method == 'POST':
        novy_text = request.POST.get('text', '').strip()
        
        # Ak je text prázdny a správa nemá ani obrázok, nedovolíme to (voliteľné)
        if not novy_text and not sprava.obrazok:
            return HttpResponse("Správa nemôže byť úplne prázdna", status=400)

        # AKTUALIZUJEME IBA TEXT
        sprava.text = novy_text
        sprava.save(update_fields=['text']) # update_fields zaručí, že siahne len na stĺpec 'text'
        
        return HttpResponse(status=200)
        
    return HttpResponse(status=400)

    
def home(request):
    inzeraty = Inzerat.objects.filter(je_aktivny=True).order_by('-vytvorene')
    return render(request, 'home.html', {'inzeraty': inzeraty})


def profil(request):
    moje_inzeraty = Inzerat.objects.filter(autor=request.user)


# inzeraty/views.py
# inzeraty/views.py
def nacitat_spravy(request, konverzacia_id):
    konverzacia = get_object_or_404(Konverzacia, id=konverzacia_id)
    spravy = Sprava.objects.filter(konverzacia=konverzacia).order_by('poslane')
    
    return render(request, 'inzeraty/chat_messages_partial.html', {
        'spravy': spravy,
        'user': request.user  # TOTO TU MUSÍ BYŤ!
    })


@login_required
def poslat_spravu(request, inzerat_id):
    if request.method == 'POST':
        inzerat = get_object_or_404(Inzerat, id=inzerat_id)
        
        # MUSÍME zistiť, či v tomto chate figuruješ ako kupujúci alebo predajca
        # Hľadáme konverzáciu, kde si buď kupujúci alebo predajca pre TENTO inzerát
        konverzacia = Konverzacia.objects.filter(inzerat=inzerat).filter(
            models.Q(kupujuci=request.user) | models.Q(predajca=request.user)
        ).first()

        # Ak konverzacia neexistuje (prvá správa), vytvoríme ju
        if not konverzacia:
            konverzacia = Konverzacia.objects.create(
                inzerat=inzerat,
                kupujuci=request.user,
                predajca=inzerat.autor
            )

        text_spravy = request.POST.get('text', '').strip()
        obrazok_spravy = request.FILES.get('obrazok')

        if text_spravy or obrazok_spravy:
            Sprava.objects.create(
                konverzacia=konverzacia,
                odosielatel=request.user,
                text=text_spravy,
                obrazok=obrazok_spravy
            )
            return HttpResponse(status=200)
    return HttpResponse(status=400)