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
