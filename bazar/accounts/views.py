from django.shortcuts import render, redirect, get_object_or_404
from .forms import RegisterForm, UserUpdateForm, ProfileUpdateForm
from django.contrib.auth.decorators import login_required
from inzeraty.models import Inzerat
from django.contrib.auth.models import User
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.contrib import messages
from django.contrib.auth import views as auth_views


class MyLoginView(auth_views.LoginView):
    def form_valid(self, form):
        messages.success(self.request, f"Vitajte späť, {form.get_user().username}!")
        return super().form_valid(form)


def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # Používateľ sa ešte nemôže prihlásiť
            user.save()

            # --- Logika pre overovací mail ---
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            domain = request.get_host()
            link = f"http://{domain}/accounts/activate/{uid}/{token}/"
            
            subject = 'Aktivujte svoj účet'
            message = f'Ahoj {user.username}, klikni na tento link pre aktiváciu účtu: {link}'
            
            send_mail(subject, message, 'noreply@tvojweb.sk', [user.email])
            # ---------------------------------

            messages.info(request, 'Registrácia úspešná. Skontroluj si e-mail pre aktiváciu účtu.')
            return redirect('login') # Presmerujeme na login, kde mu vypíše správu
    else:
        form = RegisterForm()
    
    return render(request, 'accounts/register.html', {'form': form})

def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Váš účet bol úspešne aktivovaný! Teraz sa môžete prihlásiť.')
        return redirect('login')
    else:
        return render(request, 'accounts/activation_invalid.html')

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

def verejny_profil(request, username):
    # Nájdeme používateľa podľa mena v URL
    pouzivatel = get_object_or_404(User, username=username)
    # Získame jeho inzeráty
    inzeraty = Inzerat.objects.filter(autor=pouzivatel).order_by('-vytvorene')
    
    return render(request, 'accounts/verejny_profil.html', {
        'predajca': pouzivatel,
        'inzeraty': inzeraty
    })