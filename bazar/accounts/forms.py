from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate
from django import forms
from .models import Profile
from django.core.exceptions import ValidationError
class RegisterForm(UserCreationForm):
    email = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'nieco@gbst.sk'}))
    username = forms.CharField(label="Používateľské meno", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Zadajte meno'}))
    suhlas = forms.BooleanField(
        required=True, 
        label="Súhlasím s obchodnými podmienkami a spracovaním osobných údajov (GDPR)"
    )
    class Meta:
        model = User
        fields = ["username", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Hromadné pridanie Bootstrap triedy pre všetky polia
        for name, field in self.fields.items():
            if name == 'suhlas':
                field.widget.attrs.update({'class': 'form-check-input'})
            else:
                field.widget.attrs.update({'class': 'form-control'})
            
        # 2. Preklad labelov pre heslá
        self.fields['password1'].label = "Heslo"
        self.fields['password2'].label = "Potvrdenie hesla"

        # 3. RUČNÝ PREKLAD NÁPOVEDY (help_text)
        # Tu prepisujeme tie dlhé anglické odseky o heslách
        self.fields['password1'].help_text = (
            "Vaše heslo nesmie byť príliš podobné vašim osobným údajom. "
            "Musí obsahovať aspoň 8 znakov a nesmie byť bežne používané."
        )
        self.fields['password2'].help_text = "Pre potvrdenie zadajte heslo znova."
        
        self.fields['username'].help_text = "Povinné. Maximálne 150 znakov. Iba písmená, číslice a znaky @/./+/-/_."

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