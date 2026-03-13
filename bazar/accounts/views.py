from django.shortcuts import render, redirect
from .forms import RegisterForm, UserUpdateForm, ProfileUpdateForm
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from inzeraty.models import Inzerat

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # Automaticky prihlási používateľa po registrácii
            return redirect('home') # Presmeruje na domovskú stránku
    else:
        form = RegisterForm()
    
    return render(request, 'accounts/register.html', {'form': form})

@login_required
def profil(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, instance=request.user.profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            return redirect('profil')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    moje_inzeraty = Inzerat.objects.filter(autor=request.user).order_by('-vytvorene')
    
    context = {
        'u_form': u_form,
        'p_form': p_form,
        'inzeraty': moje_inzeraty
    }
    return render(request, 'accounts/profil.html', context)