/**
 * Zistí GPS polohu používateľa a premení ju na názov mesta pre filter
 */
async function zistitPolohuFiltra(event) {
    const input = document.getElementById('filter-lokalita');
    const btn = event.currentTarget;
    const form = document.getElementById('filterForm');

    if (!navigator.geolocation) return;

    const povodnyObsah = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    
    navigator.geolocation.getCurrentPosition(async (pos) => {
        try {
            const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${pos.coords.latitude}&lon=${pos.coords.longitude}`);
            const data = await response.json();
            const a = data.address;
            const mesto = a.city || a.town || a.village || a.hamlet || a.municipality || "";
            
            input.value = mesto;
            form.submit(); 
        } catch (e) {
            console.error("Chyba pri získavaní polohy:", e);
            btn.innerHTML = povodnyObsah;
        }
    }, (error) => {
        alert("Nepodarilo sa získať GPS polohu. Skontrolujte povolenia v prehliadači.");
        btn.innerHTML = povodnyObsah;
    });
}
async function nacitatDalsieInzeraty() {
    const btn = document.getElementById('nacitat-viac-btn');
    const kontajner = document.getElementById('inzeraty-kontajner');
    const currentPage = btn.getAttribute('data-page');
    
    const povodnyObsah = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Načítavam...';

    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('page', currentPage);

    try {
        const response = await fetch(`${window.location.pathname}?${urlParams.toString()}`, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        if (response.ok) {
            const htmlRiadky = await response.text();
            
            if (htmlRiadky.trim() === '') {
                btn.style.display = 'none';
            } else {
                // Prilepíme nové inzeráty
                kontajner.insertAdjacentHTML('beforeend', htmlRiadky);
                
                // SKONTROLUJEME HLAVIČKU ZO SERVERA, ČI EŠTE SÚ ĎALŠIE STRANY
                const hasNext = response.headers.get('X-Has-Next');
                
                if (hasNext === 'false') {
                    // Ak už ďalšia strana neexistuje, tlačidlo hneď schováme
                    btn.style.display = 'none';
                } else {
                    // Ak ďalšia strana existuje, pripravíme tlačidlo na ďalšie kliknutie
                    btn.setAttribute('data-page', parseInt(currentPage) + 1);
                    btn.disabled = false;
                    btn.innerHTML = povodnyObsah;
                }
            }
        } else {
            btn.style.display = 'none';
        }
    } catch (error) {
        console.error("Chyba pri získavaní ďalších inzerátov:", error);
        btn.disabled = false;
        btn.innerHTML = povodnyObsah;
    }
}