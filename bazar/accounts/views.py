from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash, views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.models import Avg, Case, When
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.encoding import force_bytes, force_str
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from inzeraty.models import Inzerat
from .forms import ProfileUpdateForm, RegisterForm, UserUpdateForm
from .models import Recenzia, Report

LIMIT_NAHLASENI_PRE_BAN = 5


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
            
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
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
    else:
        messages.error(request, 'Aktivačný odkaz je neplatný alebo už bol použitý.')
    return redirect('login')


@login_required
def profil(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, instance=request.user.profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, "Údaje boli aktualizované.")
            return redirect('profil')
        else:
            for form in [u_form, p_form]:
                for errors in form.errors.values():
                    for error in errors:
                        messages.error(request, error)
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    moje_inzeraty = Inzerat.objects.filter(autor=request.user).order_by('-vytvorene')
    sort_type = request.GET.get('sort', 'new')
    vsetky_moje_recenzie = Recenzia.objects.filter(prijimatel=request.user)
    
    priemer = vsetky_moje_recenzie.aggregate(Avg('hviezdicky'))['hviezdicky__avg']
    priemer = round(priemer, 1) if priemer else 0

    if sort_type == 'old':
        recenzie = vsetky_moje_recenzie.order_by('vytvorene')
    elif sort_type == 'best':
        recenzie = vsetky_moje_recenzie.order_by('-hviezdicky', '-vytvorene')
    elif sort_type == 'worst':
        recenzie = vsetky_moje_recenzie.order_by('hviezdicky', '-vytvorene')
    else:
        recenzie = vsetky_moje_recenzie.order_by('-vytvorene')

    context = {
        'u_form': u_form,
        'p_form': p_form,
        'inzeraty': moje_inzeraty,
        'recenzie': recenzie,
        'priemer': priemer,
        'pocet_recenzii': vsetky_moje_recenzie.count(),
        'current_sort': sort_type,
        'je_moj_profil': True,
    }

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'accounts/recenzie_partial.html', context)

    return render(request, 'accounts/profil.html', context)


def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        associated_users = User.objects.filter(email=email)
        
        if associated_users.exists():
            domain = request.get_host()
            for user in associated_users:
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                link = f"http://{domain}/accounts/reset/{uid}/{token}/"
                subject = 'Obnovenie hesla'
                
                html_message = f"""
                <!DOCTYPE html>
                <html>
                <head><meta charset="utf-8"></head>
                <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px;">
                    <div style="max-width: 500px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 8px;">
                        <h2 style="color: #333333; text-align: center;">Obnovenie hesla</h2>
                        <p style="color: #555555;">Ahoj <strong>{user.username}</strong>,</p>
                        <p style="color: #555555;">Pre nastavenie nového hesla klikni na tlačidlo nižšie:</p>
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{link}" style="background-color: #0d6efd; color: #ffffff; text-decoration: none; padding: 12px 25px; border-radius: 5px; font-weight: bold; display: inline-block;">Obnoviť heslo</a>
                        </div>
                        <p style="color: #777777; font-size: 13px;">Odkaz:<br><a href="{link}" style="color: #0d6efd;">{link}</a></p>
                    </div>
                </body>
                </html>
                """
                plain_message = strip_tags(html_message)
                send_mail(
                    subject, 
                    plain_message, 
                    settings.DEFAULT_FROM_EMAIL, 
                    [user.email],
                    html_message=html_message
                )
        
        messages.info(request, 'Ak e-mail v systéme existuje, poslali sme vám pokyny na obnovenie hesla.')
    return redirect('login')


def verejny_profil(request, username):
    pouzivatel = get_object_or_404(User, username=username)
    sort_type = request.GET.get('sort', 'new')
    vsetky_recenzie = Recenzia.objects.filter(prijimatel=pouzivatel)

    priemer_hviezdiciek = vsetky_recenzie.aggregate(Avg('hviezdicky'))['hviezdicky__avg']
    priemer_hviezdiciek = round(priemer_hviezdiciek, 1) if priemer_hviezdiciek else 0

    if sort_type == 'old':
        vsetky_recenzie = vsetky_recenzie.order_by('vytvorene')
    elif sort_type == 'best':
        vsetky_recenzie = vsetky_recenzie.order_by('-hviezdicky', '-vytvorene')
    elif sort_type == 'worst':
        vsetky_recenzie = vsetky_recenzie.order_by('hviezdicky', '-vytvorene')
    else:
        vsetky_recenzie = vsetky_recenzie.order_by('-vytvorene')

    uz_hodnotil = False
    uz_nahlasil = False

    if request.user.is_authenticated:
        vsetky_recenzie = vsetky_recenzie.annotate(
            je_moja=Case(When(autor=request.user, then=0), default=1)
        ).order_by('je_moja', *vsetky_recenzie.query.order_by)

        uz_hodnotil = Recenzia.objects.filter(autor=request.user, prijimatel=pouzivatel).exists()
        uz_nahlasil = Report.objects.filter(zalobca=request.user, obvineny=pouzivatel).exists()

    context = {
        'predajca': pouzivatel,
        'inzeraty': Inzerat.objects.filter(autor=pouzivatel).order_by('-vytvorene'),
        'recenzie': vsetky_recenzie,
        'current_sort': sort_type,
        'uz_hodnotil': uz_hodnotil,
        'priemer': priemer_hviezdiciek,
        'pocet_recenzii': vsetky_recenzie.count(),
        'je_moj_profil': False,
        'uz_nahlasil': uz_nahlasil,
    }

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'accounts/recenzie_partial.html', context)

    return render(request, 'accounts/verejny_profil.html', context)


@login_required
def pridat_recenziu(request, user_id):
    if request.method == 'POST':
        prijimatel = get_object_or_404(User, id=user_id)
        if request.user == prijimatel:
            return HttpResponse("Nemôžete hodnotiť seba", status=400)
            
        hviezdicky = request.POST.get('hviezdicky')
        text = request.POST.get('text')
        
        if hviezdicky and text:
            Recenzia.objects.update_or_create(
                autor=request.user, 
                prijimatel=prijimatel,
                defaults={'hviezdicky': int(hviezdicky), 'text': text}
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


@login_required
def nahlasit_pouzivatela(request, user_id):
    if request.method == 'POST':
        obvineny = get_object_or_404(User, id=user_id)
        if request.user == obvineny:
            return HttpResponse("Nemôžete nahlásiť sami seba.", status=400)

        if Report.objects.filter(zalobca=request.user, obvineny=obvineny).exists():
            return HttpResponse("Tohto používateľa ste už nahlásili.", status=400)
            
        dovod = request.POST.get('dovod')
        popis = request.POST.get('popis', '')
        
        if dovod:
            Report.objects.create(
                zalobca=request.user,
                obvineny=obvineny,
                dovod=dovod,
                popis=popis
            )
            _skontroluj_a_zablokuj_pouzivatela_ak_treba(obvineny)
            return HttpResponse(status=200)
            
    return HttpResponse("Neplatná požiadavka", status=400)


@login_required
def rozsirene_nastavenia(request):
    if request.method == 'POST':
        akcia = request.POST.get('akcia')
        
        if akcia == 'zmena_emailu':
            novy_email = request.POST.get('email', '').strip()
            if novy_email:
                if User.objects.exclude(pk=request.user.pk).filter(email=novy_email).exists():
                    messages.error(request, "Tento e-mail už používa iný účet.")
                else:
                    request.user.email = novy_email
                    request.user.save(update_fields=['email'])
                    messages.success(request, "E-mailová adresa bola úspešne zmenená.")
            else:
                messages.error(request, "E-mail nemôže byť prázdny.")
            return redirect('rozsirene_nastavenia')

        elif akcia == 'zmena_hesla':
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Vaše heslo bolo úspešne zmenené.")
                return redirect('rozsirene_nastavenia')
            else:
                messages.error(request, "Opravte chyby vo formulári zmeny hesla.")
                return render(request, 'accounts/rozsirene_nastavenia.html', {'password_form': password_form})

        elif akcia == 'zmazat_ucet':
            user = request.user
            user.delete()
            messages.success(request, "Váš účet bol permanentne odstránený.")
            return redirect('login')

    password_form = PasswordChangeForm(request.user)
    return render(request, 'accounts/rozsirene_nastavenia.html', {'password_form': password_form})


def _skontroluj_a_zablokuj_pouzivatela_ak_treba(obvineny_user):
    if not obvineny_user or obvineny_user.is_staff:
        return

    try:
        pocet_nahlaseni = Report.objects.filter(obvineny=obvineny_user).values('zalobca').distinct().count()
        if pocet_nahlaseni >= LIMIT_NAHLASENI_PRE_BAN:
            obvineny_user.is_active = False
            obvineny_user.save(update_fields=['is_active'])
            Inzerat.objects.filter(autor=obvineny_user).update(
                je_aktivny=False, 
                status='Zamietnutý', 
                dovod_zamietnutia='Automatický ban za vysoký počet nahlásení.'
            )
    except Exception:
        pass