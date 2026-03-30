from django.shortcuts import render
from inzeraty.models import Inzerat
from django.http import JsonResponse
from django.http import HttpResponse
import traceback
# Create your views here.
def home(request):
    # Dôležitý je ten filter(je_aktivny=True)
    inzeraty = Inzerat.objects.filter(je_aktivny=True).order_by('-vytvorene')
    return render(request, 'home.html', {'inzeraty': inzeraty})

# inzeraty/views.py

def upravit_inzerat(request, pk):
    inzerat = get_object_or_404(Inzerat, pk=pk)
    
    # KONTROLA: Ak inzerát nie je aktívny, autor ho už nemôže upravovať
    if not inzerat.je_aktivny:
        # Môžeš ho buď presmerovať domov, alebo vypísať správu
        return redirect('home') 

    # Kontrola, či je to naozaj autor (to už tam asi máš)
    if inzerat.autor != request.user:
        return redirect('home')

    # ... tvoj pôvodný kód pre spracovanie formulára (if request.method == 'POST'...)

def poslat_spravu(request, inzerat_id):
    if request.method == 'POST':
        try:
            inzerat = get_object_or_404(Inzerat, id=inzerat_id)
            text = request.POST.get('text', '').strip()
            obrazok = request.FILES.get('obrazok')

            print(f"DEBUG: Text={text}, Obrazok={obrazok}") # Uvidíš v termináli

            if not text and not obrazok:
                return HttpResponse("Prázdna správa", status=400)

            # Vytvorenie správy
            nova_sprava = Sprava.objects.create(
                inzerat=inzerat,
                odosielatel=request.user,
                text=text,
                obrazok=obrazok
            )
            print(f"DEBUG: Správa uložená s ID {nova_sprava.id}")
            return HttpResponse(status=200)

        except Exception as e:
            # TOTO vypíše celú chybu do terminálu, aj s číslom riadku!
            print("--- CHYBA NA SERVERI ---")
            traceback.print_exc() 
            print("------------------------")
            return HttpResponse(str(e), status=500)

    return HttpResponse(status=405)
