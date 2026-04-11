from .models import Sprava
from django.db.models import Q

def unread_messages_count(request):
    if request.user.is_authenticated:
        # Hľadáme správy, ktoré:
        # 1. Sú v konverzáciách, kde je užívateľ buď kupujúci alebo predajca
        # 2. Užívateľ NIE JE ich odosielateľom
        # 3. Pole precitane je False
        count = Sprava.objects.filter(
            Q(konverzacia__kupujuci=request.user) | Q(konverzacia__predajca=request.user),
            precitane=False
        ).exclude(odosielatel=request.user).distinct().count()
        
        return {'unread_count': count}
    return {'unread_count': 0}