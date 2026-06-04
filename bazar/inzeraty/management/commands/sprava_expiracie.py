import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from inzeraty.models import Inzerat

class Command(BaseCommand):
    help = 'Deaktivuje inzeráty staršie ako 30 dní a maže inzeráty neaktívne viac ako 30 dní.'

    def handle(self, *args, **options) -> None:
        teraz = timezone.now()
        hranica_deaktivacie = teraz - timedelta(days=30)
        
        # 1. FAZA: Deaktivácia inzerátov (Aktívne -> Neaktívne)
        # Hľadáme tie, ktoré sú aktívne, ale ich posledná aktualizácia/vytvorenie je staršia ako 30 dní
        expirovane_na_deaktivaciu = Inzerat.objects.filter(
            je_aktivny=True,
            vytvorene__lte=hranica_deaktivacie
        )
        
        pocet_deaktivovanych = expirovane_na_deaktivaciu.count()
        
        # Použijeme update_fields na zmenu dátumu na 'teraz', čím zaznamenáme 
        # moment DEAKTIVÁCIE (od neho budeme odpočítavať ďalších 30 dní do zmazania)
        for inz in expirovane_na_deaktivaciu:
            inz.je_aktivny = False
            inz.vytvorene = teraz  # Dátum teraz slúži ako časový odtlačok deaktivácie
            inz.save(update_fields=['je_aktivny', 'vytvorene'])

        # 2. FÁZA: Úplné zmazanie z DB (Neaktívne dlhšie ako 30 dní)
        # Keďže sme pri deaktivácii posunuli 'vytvorene' na vtedajší aktuálny čas,
        # ak od tej doby prešlo ďalších 30 dní, znamená to, že inzerát je neaktívny už mesiac.
        na_zmazanie = Inzerat.objects.filter(
            je_aktivny=False,
            vytvorene__lte=hranica_deaktivacie
        )
        
        pocet_zmazanych = na_zmazanie.count()
        
        # Pri mazaní musíme vyčistiť aj súbory z disku (využijeme logiku, ktorú už máš vo views)
        for inz in na_zmazanie:
            try:
                if inz.obrazok and os.path.isfile(inz.obrazok.path):
                    os.remove(inz.obrazok.path)
                for foto in inz.dodatocne_obrazky.all():
                    if foto.obrazok and os.path.isfile(foto.obrazok.path):
                        os.remove(foto.obrazok.path)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Chyba pri mazaní súborov inzerátu {inz.id}: {e}"))
            
            # Kompletné zmazanie z databázy
            inz.delete()

        # Výpis do konzoly pre kontrolu
        self.stdout.write(self.style.SUCCESS(
            f"Úspešne deaktivovaných: {pocet_deaktivovanych} inzerátov. "
            f"Úspešne zmazaných z DB: {pocet_zmazanych} inzerátov."
        ))