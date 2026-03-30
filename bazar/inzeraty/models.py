from django.db import models
from django.contrib.auth.models import User
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill

class Inzerat(models.Model):
    nazov = models.CharField(max_length=200)
    popis = models.TextField()
    cena = models.CharField(max_length=10)
    vytvorene = models.DateTimeField(auto_now_add=True)
    autor = models.ForeignKey(User, on_delete=models.CASCADE)
    je_aktivny = models.BooleanField(default=True)
    obrazok = ProcessedImageField(
        upload_to='inzeraty/',
        processors=[ResizeToFill(400, 400)], # Oreže a zmenší na 400x400
        format='JPEG',
        options={'quality': 80}, # Kvalita 80% je ideálna pre web
        blank=True,
        null=True
    )
    def __str__(self):
        return self.nazov

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
    text = models.TextField(blank=True, null=True) # Text už nie je povinný, ak posielaš len fotku
    obrazok = models.ImageField(upload_to='chat_fotky/', blank=True, null=True)
    poslane = models.DateTimeField(auto_now_add=True)
    text = models.TextField(blank=True, null=True)
    upravene = models.BooleanField(default=False)
    precitane = models.BooleanField(default=False)