from django.db.models import Q
from .models import Sprava, Kontakt

def unread_messages_count_for_user(user):
    if user.is_authenticated:
        return Sprava.objects.filter(
            Q(konverzacia__kupujuci=user) | Q(konverzacia__predajca=user),
            precitane=False
        ).exclude(odosielatel=user).distinct().count()
    return 0

def unread_messages_count(request):
    return {'unread_count': unread_messages_count_for_user(request.user)}

def kontakt_info(request):
    return {'kontakt': Kontakt.objects.first()}