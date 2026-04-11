from django import forms
from .models import Inzerat

# Hľadaj v inzeraty/forms.py
class InzeratForm(forms.ModelForm):
    class Meta:
        model = Inzerat
        fields = ['nazov', 'popis', 'cena', 'kategoria', 'typ', 'obrazok']
        labels = {
            'nazov': 'Názov inzerátu',
            'popis': 'Podrobný popis',
            'cena': 'Cena (€)',
            'kategoria': 'Kategória',
            'typ': 'Typ inzerátu',
            'obrazok': 'Fotografia produktu',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control bg-dark text-white border-secondary'})