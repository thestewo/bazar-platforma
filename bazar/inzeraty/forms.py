from django import forms
from .models import Inzerat

class InzeratForm(forms.ModelForm):

    class Meta:
        model = Inzerat
        fields = ['nazov', 'cena', 'popis', 'kategoria', 'typ', 'lokalita']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Nastavíme, aby 'typ' NEBOL povinný (bude sa správať ako kategória)
        if 'typ' in self.fields:
            self.fields['typ'].required = False  # <--- TÁTO ZMENA TO VYRIEŠI
            if hasattr(self.fields['typ'], 'empty_label'):
                self.fields['typ'].empty_label = "---------"

        # Automatické nastylovanie všetkých polí formulára na Bootstrap vzhľad
        for field_name in ['nazov', 'cena', 'popis', 'kategoria', 'typ', 'lokalita']:
            if field_name in self.fields:
                field = self.fields[field_name]
                
                # Výberové polia (Dropdowns)
                if field_name in ['kategoria', 'typ']:
                    field.widget.attrs.update({'class': 'form-select bg-secondary text-white border-secondary'})
                # Textová oblasť pre popis
                elif field_name == 'popis':
                    field.widget.attrs.update({'class': 'form-control bg-secondary text-white border-secondary', 'rows': '4'})
                # Klasické textové / číselné inputy
                else:
                    field.widget.attrs.update({'class': 'form-control bg-secondary text-white border-secondary'})