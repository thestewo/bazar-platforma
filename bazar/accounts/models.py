from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from inzeraty.models import Inzerat

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    telefon = models.CharField(max_length=20, blank=True)
    mesto = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f'Profil používateľa {self.user.username}'

    # --- PRIDANÁ FUNKCIA PRE KONTROLU NAHLÁSENÍ ---
    @property
    def je_rizikovy(self):
        """Vráti True, ak má používateľ dokopy 3 alebo viac nahlásení (profil + inzeráty)"""
        # Keďže nemôžeme importovať Report hore kvôli cyklickému importu, importujeme ho priamo tu
        from .models import Report
        
        pocet_nahlaseni_profilu = Report.objects.filter(obvineny=self.user).count()
        pocet_nahlaseni_inzeratov = Report.objects.filter(inzerat__autor=self.user).count()
        
        celkovo = pocet_nahlaseni_profilu + pocet_nahlaseni_inzeratov
        return celkovo >= 3 


# Tieto funkcie automaticky vytvoria profil, keď sa zaregistruje nový User
@receiver(post_save, sender=User)
def vytvor_profil(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def uloz_profil(sender, instance, **kwargs):
    instance.profile.save()

class Recenzia(models.Model):
    autor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vytvorene_recenzie')
    prijimatel = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recenzie')
    hviezdicky = models.IntegerField(default=5)
    text = models.TextField()
    vytvorene = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-vytvorene'] # Predvolene najnovšie

class Report(models.Model):
    DOVOD_CHOICES = [
        ('podvod', 'Podvodný inzerát / Neodoslaný tovar'),
        ('vulgarnost', 'Vulgárne správanie'),
        ('spam', 'Spam / Reklama'),
        ('ine', 'Iný dôvod'),
    ]

    zalobca = models.ForeignKey(User, on_delete=models.CASCADE, related_name='podane_hlasenia')
    obvineny = models.ForeignKey(User, on_delete=models.CASCADE, related_name='nahlasenia', null=True, blank=True)
    inzerat = models.ForeignKey(Inzerat, on_delete=models.CASCADE, related_name='nahlasenia', null=True, blank=True)
    
    dovod = models.CharField(max_length=20, choices=DOVOD_CHOICES)
    popis = models.TextField(blank=True)
    vytvorene = models.DateTimeField(auto_now_add=True)
    vyriesene = models.BooleanField(default=False)

    def __str__(self):
        if self.inzerat:
            return f"{self.zalobca} nahlásil inzerát: {self.inzerat.nazov} - {self.get_dovod_display()}"
        return f"{self.zalobca} nahlásil používateľa: {self.obvineny} - {self.get_dovod_display()}"
    
    class Meta:
        verbose_name = "Nahlásenie"
        verbose_name_plural = "Nahlásenia"
        # UPRAVENÉ: unikátnosť riešime kombináciou, buď nahlásil osobu alebo konkrétny inzerát
        unique_together = [('zalobca', 'obvineny'), ('zalobca', 'inzerat')]