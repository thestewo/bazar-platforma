from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .forms import InzeratForm
from .models import Inzerat



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
    
    # Skontrolujeme, či je prihlásený používateľ autorom inzerátu
    if inzerat.autor != request.user:
        raise PermissionDenied # Vyhodí chybu 403, ak sa o to pokúsi niekto iný
        
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
    
    # Skontrolujeme, či je prihlásený používateľ autorom
    if inzerat.autor != request.user:
        raise PermissionDenied
        
    if request.method == 'POST':
        inzerat.delete()
        return redirect('home')
        
    return render(request, 'inzeraty/potvrdit_zmazanie.html', {'inzerat': inzerat})
