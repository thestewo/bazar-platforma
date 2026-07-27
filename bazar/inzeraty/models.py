from django.db import models
from django.db import transaction
from django.contrib.auth.models import User
from imagekit.models import ProcessedImageField
from imagekit.processors import SmartResize, Transpose, ResizeToFit, ResizeToFill
import os
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from PIL import Image

class Kategoria(models.Model):
    nazov = models.CharField(max_length=100)
    
    def __str__(self):
        return self.nazov
        
    class Meta:
        verbose_name_plural = "Kategórie"

class Typ(models.Model):
    nazov = models.CharField(max_length=10)
    
    def __str__(self):
        return self.nazov
        
    class Meta:
        verbose_name_plural = "Typy"

class Inzerat(models.Model):
    nazov = models.CharField(max_length=50)
    popis = models.TextField()
    cena = models.DecimalField(max_digits=10, decimal_places=2)
    kategoria = models.ForeignKey('Kategoria', on_delete=models.SET_NULL, null=True, blank=True) 
    typ = models.ForeignKey('Typ', on_delete=models.SET_NULL, null=True, blank=True)
    vytvorene = models.DateTimeField(auto_now_add=True)
    autor = models.ForeignKey(User, on_delete=models.CASCADE)
    je_aktivny = models.BooleanField(default=True)
    lokalita = models.CharField(max_length=255, blank=True, null=True)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    kontrola_zlyhala = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default='caka_na_kontrolu')
    dovod_zamietnutia = models.TextField(blank=True, null=True, verbose_name="Dôvod zamietnutia")
    obrazok = ProcessedImageField(
        upload_to='inzeraty/',
        processors=[
            Transpose(), 
            # Zvýšené na 2560px pre zachovanie detailov z 8K zdrojov
            ResizeToFit(2560, 2560, upscale=False) 
        ],
        format='WEBP',
        options={'quality': 95, 'method': 6},
        blank=True,
        null=True
    )
    skryte_tagy = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nazov

class InzeratObrazok(models.Model):
    inzerat = models.ForeignKey(Inzerat, related_name='dodatocne_obrazky', on_delete=models.CASCADE)
    obrazok = ProcessedImageField(
        upload_to='inzeraty/viac/',
        processors=[
            Transpose(), 
            # Zjednotené na rovnakú vysokú kvalitu ako hlavný obrázok
            ResizeToFit(2560, 2560, upscale=False) 
        ],
        format='WEBP',
        options={'quality': 95, 'method': 6},
        blank=True, null=True
    )

    class Meta:
        verbose_name_plural = "Dodatočné obrázky"

class Konverzacia(models.Model):
    inzerat = models.ForeignKey(Inzerat, on_delete=models.CASCADE)
    kupujuci = models.ForeignKey(User, on_delete=models.CASCADE, related_name='nakupy')
    predajca = models.ForeignKey(User, on_delete=models.CASCADE, related_name='predaje')
    vytvorene = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('inzerat', 'kupujuci', 'predajca')

class Sprava(models.Model):
    konverzacia = models.ForeignKey(Konverzacia, on_delete=models.CASCADE, related_name='spravy')
    odosielatel = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField(blank=True, null=True)
    obrazok = models.ImageField(upload_to='chat_fotky/', blank=True, null=True)
    video = models.FileField(upload_to='chat_videa/', blank=True, null=True)
    poslane = models.DateTimeField(auto_now_add=True)
    upravene = models.BooleanField(default=False)
    precitane = models.BooleanField(default=False)

    # OPRAVENÉ: Pridaná textová reprezentácia správy pre prehľadnosť v administrácii
    def __str__(self):
        return self.text if self.text else f"Obrázok/Video (ID: {self.pk})"

class Kontakt(models.Model):
    meno = models.CharField(max_length=100, default="Admin")
    info_1 = models.CharField(max_length=255, verbose_name="Email alebo info 1")
    info_2 = models.CharField(max_length=255, verbose_name="Telefón alebo info 2")

    class Meta:
        verbose_name_plural = "Kontakt"

    def __str__(self):
        return f"Kontaktné údaje: {self.meno}"


# ==========================================================================
# --- SIGNÁLY ---
# ==========================================================================

@receiver(pre_save, sender=Inzerat)
def auto_delete_file_on_change_or_deactivation(sender, instance, **kwargs):
    if not instance.pk:
        return

    try:
        old_instance = Inzerat.objects.get(pk=instance.pk)
    except Inzerat.DoesNotExist:
        return

    stary_obrazok = None

    if old_instance.je_aktivny and not instance.je_aktivny:
        if old_instance.obrazok:
            stary_obrazok = old_instance.obrazok
            
    elif old_instance.obrazok and old_instance.obrazok != instance.obrazok:
        stary_obrazok = old_instance.obrazok

    if stary_obrazok:
        transaction.on_commit(lambda: stary_obrazok.delete(save=False))


@receiver(post_delete, sender=Inzerat)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    if instance.obrazok:
        def safe_delete():
            try:
                instance.obrazok.delete(save=False)
            except Exception as e:
                print(f"Upozornenie: Nepodarilo sa vymazať súbor {instance.obrazok.path}: {e}")
        
        transaction.on_commit(safe_delete)


@receiver(post_delete, sender=InzeratObrazok)
def auto_delete_additional_file_on_delete(sender, instance, **kwargs):
    if instance.obrazok:
        transaction.on_commit(lambda: instance.obrazok.delete(save=False))


@receiver(post_delete, sender=Sprava)
def auto_delete_chat_file_on_delete(sender, instance, **kwargs):
    if instance.obrazok: 
        transaction.on_commit(lambda: instance.obrazok.delete(save=False))
    if instance.video: 
        transaction.on_commit(lambda: instance.video.delete(save=False))