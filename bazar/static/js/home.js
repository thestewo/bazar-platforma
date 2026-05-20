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