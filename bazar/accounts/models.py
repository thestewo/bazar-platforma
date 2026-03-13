from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    telefon = models.CharField(max_length=20, blank=True)
    mesto = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f'Profil používateľa {self.user.username}'

# Tieto funkcie automaticky vytvoria profil, keď sa zaregistruje nový User
@receiver(post_save, sender=User)
def vytvor_profil(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def uloz_profil(sender, instance, **kwargs):
    instance.profile.save()