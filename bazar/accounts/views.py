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
from accounts.models import Recenzia
from django.http import HttpResponse
from django.db.models import Avg
class MyLoginView(auth_views.LoginView):
    def form_valid(self, form):
        messages.success(self.request, f"Vitajte späť, {form.get_user().username}!")
        return super().form_valid(form)

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            domain = request.get_host()
            link = f"http://{domain}/accounts/activate/{uid}/{token}/"
            
            subject = 'Aktivujte svoj účet'
            message = f'Ahoj {user.username}, klikni na tento link pre aktiváciu účtu: {link}'
            
            send_mail(subject, message, 'noreply@tvojweb.sk', [user.email])

            messages.info(request, 'Registrácia úspešná. Skontroluj si e-mail pre aktiváciu účtu.')
            return redirect('login')
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
    # 1. Spracovanie formulárov pre aktualizáciu údajov
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, instance=request.user.profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, "Údaje boli aktualizované.")
            return redirect('profil')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    # 2. Logika pre Moje inzeráty
    moje_inzeraty = Inzerat.objects.filter(autor=request.user).order_by('-vytvorene')
    
    # 3. Logika pre Moje recenzie (Zoraďovanie)
    sort_type = request.GET.get('sort', 'new')
    vsetky_moje_recenzie = Recenzia.objects.filter(prijimatel=request.user)
    
    # Výpočet priemeru a počtu (pre zobrazenie v karte)
    priemer = vsetky_moje_recenzie.aggregate(Avg('hviezdicky'))['hviezdicky__avg']
    priemer = round(priemer, 1) if priemer else 0
    pocet_recenzii = vsetky_moje_recenzie.count()

    # Filtrovanie pre zoznam
    if sort_type == 'old':
        recenzie = vsetky_moje_recenzie.order_by('vytvorene')
    elif sort_type == 'best':
        recenzie = vsetky_moje_recenzie.order_by('-hviezdicky', '-vytvorene')
    elif sort_type == 'worst':
        recenzie = vsetky_moje_recenzie.order_by('hviezdicky', '-vytvorene')
    else:
        recenzie = vsetky_moje_recenzie.order_by('-vytvorene')

    # 4. Príprava jednotného kontextu
    context = {
        'u_form': u_form,
        'p_form': p_form,
        'inzeraty': moje_inzeraty,
        'recenzie': recenzie,
        'priemer': priemer,
        'pocet_recenzii': pocet_recenzii,
        'current_sort': sort_type,
        'je_moj_profil': True,

    }

    # 5. ROZHODOVANIE (AJAX vs. Celá stránka)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'accounts/recenzie_partial.html', context)

    return render(request, 'accounts/profil.html', context)

def verejny_profil(request, username):
    pouzivatel = get_object_or_404(User, username=username)
    sort_type = request.GET.get('sort', 'new')
    vsetky_recenzie = Recenzia.objects.filter(prijimatel=pouzivatel)
    uz_hodnotil = Recenzia.objects.filter(autor=request.user, prijimatel=pouzivatel).exists() if request.user.is_authenticated else False

     # Výpočet priemeru
    priemer_hviezdiciek = Recenzia.objects.filter(prijimatel=pouzivatel).aggregate(Avg('hviezdicky'))['hviezdicky__avg']
    # Ak nemá žiadne recenzie, priemer bude None, tak ho nastavíme na 0
    priemer_hviezdiciek = round(priemer_hviezdiciek, 1) if priemer_hviezdiciek else 0

    # Logika pre posunutie vlastnej recenzie na začiatok
    vsetky_recenzie = Recenzia.objects.filter(prijimatel=pouzivatel)


    if sort_type == 'old':
        vsetky_recenzie = vsetky_recenzie.order_by('vytvorene')
    elif sort_type == 'best':
        vsetky_recenzie = vsetky_recenzie.order_by('-hviezdicky', '-vytvorene')
    elif sort_type == 'worst':
        vsetky_recenzie = vsetky_recenzie.order_by('hviezdicky', '-vytvorene')
    else:
        vsetky_recenzie = vsetky_recenzie.order_by('-vytvorene')

    if request.user.is_authenticated:
        from django.db.models import Case, When
        vsetky_recenzie = vsetky_recenzie.annotate(
            je_moja=Case(
                When(autor=request.user, then=0),
                default=1,
            )
        ).order_by('je_moja', *vsetky_recenzie.query.order_by)

    uz_hodnotil = False
    if request.user.is_authenticated:
        uz_hodnotil = Recenzia.objects.filter(autor=request.user, prijimatel=pouzivatel).exists()

    context = {
        'predajca': pouzivatel,
        'inzeraty': Inzerat.objects.filter(autor=pouzivatel).order_by('-vytvorene'),
        'recenzie': vsetky_recenzie,
        'current_sort': sort_type,
        'uz_hodnotil': uz_hodnotil,
        'priemer': priemer_hviezdiciek,
        'pocet_recenzii': vsetky_recenzie.count(),
        'je_moj_profil': False,
    }

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'accounts/recenzie_partial.html', context)

    return render(request, 'accounts/verejny_profil.html', context)

@login_required
def pridat_recenziu(request, user_id):
    if request.method == 'POST':
        prijimatel = get_object_or_404(User, id=user_id)
        
        # Ochrana: nemôžeš hodnotiť sám seba
        if request.user == prijimatel:
            return HttpResponse("Nemôžete hodnotiť seba", status=400)
            
        hviezdicky = request.POST.get('hviezdicky')
        text = request.POST.get('text')
        
        if hviezdicky and text:
            # POUŽIJEME update_or_create - to je kľúč k úprave
            Recenzia.objects.update_or_create(
                autor=request.user, 
                prijimatel=prijimatel,
                defaults={
                    'hviezdicky': int(hviezdicky),
                    'text': text
                }
            )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return HttpResponse(status=200)
            
            return redirect('verejny_profil', username=prijimatel.username)
            
    return HttpResponse("Neplatná požiadavka", status=400)
    


@login_required
def zmazat_recenziu(request, recenzia_id):
    recenzia = get_object_or_404(Recenzia, id=recenzia_id, autor=request.user)
    username = recenzia.prijimatel.username
    recenzia.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return HttpResponse(status=200)
        
    return redirect('verejny_profil', username=username)