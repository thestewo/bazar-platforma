from django import forms
from .models import Inzerat

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
        widgets = {
            'nazov': forms.TextInput(attrs={
                'maxlength': '50',
                'placeholder': 'Stručný názov (max. 50 znakov)'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            existing_classes = field.widget.attrs.get('class', '')
            field.widget.attrs.update({
                'class': f'{existing_classes} form-control bg-dark text-white border-secondary'.strip()
            })