from django import forms
from .models import Inzerat

class InzeratForm(forms.ModelForm):
    class Meta:
        model = Inzerat
        fields = ['nazov', 'popis', 'cena', 'obrazok']