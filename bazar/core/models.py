from django.db import models
from django.conf import settings

class Ticket(models.Model):
    TYP_CHOICES = [
        ('navrh', 'Návrh / Vylepšenie'),
        ('chyba', 'Nahlásenie chyby'),
        ('otazka', 'Všeobecná otázka'),
    ]
    
    STAV_CHOICES = [
        ('novy', 'Nový'),
        ('riesi_se', 'Rieši sa'),
        ('vyriesene', 'Vyriešené'),
        ('zamietnute', 'Zamietnuté'),
    ]

    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    # Ak píše neprihlásený používateľ, zadá email manuálne
    email = models.EmailField(blank=True, null=True) 
    typ = models.CharField(max_length=20, choices=TYP_CHOICES, default='navrh')
    predmet = models.CharField(max_length=150)
    sprava = models.TextField()
    stav = models.CharField(max_length=20, choices=STAV_CHOICES, default='novy')
    vytvorene = models.DateTimeField(auto_now_add=True)
    poznamka_admina = models.TextField(blank=True, null=True, help_text="Tvoja interná poznámka k riešeniu.")

    class Meta:
        ordering = ['-vytvorene']
        verbose_name = "Ticket / Návrh"
        verbose_name_plural = "Tickety a Návrhy"

    def __str__(self):
        return f"{self.get_typ_display()} - {self.predmet} ({self.get_stav_display()})"