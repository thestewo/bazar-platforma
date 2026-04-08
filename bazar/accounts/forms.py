from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate
from django import forms
from .models import Profile
from django.core.exceptions import ValidationError
class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ["username", "email"]

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['telefon', 'mesto']

class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(label="Používateľské meno", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Zadajte meno'}))
    password = forms.CharField(label="Heslo", widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '******'}))
    error_messages = {
        'invalid_login': "Nesprávne používateľské meno alebo heslo. Skúste to znova.",
        'inactive': "Tento účet je neaktívny.",
    }
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            # Pokúsime sa overiť údaje
            self.user_cache = authenticate(self.request, username=username, password=password)
            
            if self.user_cache is None:
                # Ak authenticate zlyhalo (vráti None), pozrieme sa prečo
                user_exists = User.objects.filter(username=username).exists()
                if user_exists:
                    user = User.objects.get(username=username)
                    # Ak heslo sedí, ale účet je neaktívny
                    if user.check_password(password) and not user.is_active:
                        raise ValidationError(
                            "Váš účet ešte nie je aktivovaný. Prosím, kliknite na potvrdzovací link v e-maile.",
                            code='not_activated',
                        )
                
                # Ak je to proste len zlé heslo alebo meno, vrátime štandardnú chybu
                raise ValidationError(
                    self.error_messages['invalid_login'],
                    code='invalid_login',
                    params={'username': self.username_field.verbose_name},
                )
        return self.cleaned_data




