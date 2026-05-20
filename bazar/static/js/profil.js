
document.addEventListener('DOMContentLoaded', function () {
    // 1. GLOBÁLNA POMOCNÁ FUNKCIA PRE FETCH (Ušetrí opakovanie kódu)
    const djangoFetch = (url, options = {}) => {
        options.headers = {
            ...options.headers,
            'X-Requested-With': 'XMLHttpRequest'
        };
        return fetch(url, options);
    };

    // 2. RECOVÁNIE RECENZIÍ (Zoradenie a Zmazanie)
    window.nacitajRecenzie = (sortType) => {
        const url = `${window.location.pathname}?sort=${sortType}`;
        djangoFetch(url)
            .then(res => res.text())
            .then(html => {
                document.getElementById('recenzie-list').innerHTML = html;
                window.history.pushState({}, '', url);
            });
    };

    window.zmazatRecenziu = (id) => {
        djangoFetch(`/accounts/recenzia/zmazat/${id}/`)
            .then(res => res.ok && window.location.reload());
    };

    // 3. MODAL: PRÍPRAVA ÚPRAVY RECENZIE
    window.pripravUpravu = (hviezdicky, text) => {
        const modalEl = document.getElementById('reviewModal');
        const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
        
        const form = document.getElementById('addReviewForm');
        form.querySelector('textarea[name="text"]').value = text;
        form.querySelector(`input[name="hviezdicky"][value="${hviezdicky}"]`).checked = true;
        
        document.getElementById('modalTitle').innerText = 'Upraviť moju recenziu';
        modal.show();
    };

    // Reset titulku recenzie po zatvorení
    document.getElementById('reviewModal')?.addEventListener('hidden.bs.modal', () => {
        document.getElementById('modalTitle').innerText = 'Pridať recenziu';
    });

    // 4. SUBMIT FORMULÁRA PRE RECENZIU
    document.getElementById('addReviewForm')?.addEventListener('submit', function(e) {
        e.preventDefault();
        djangoFetch(this.action, { method: 'POST', body: new FormData(this) })
            .then(res => res.ok ? window.location.reload() : alert("Chyba pri ukladaní."));
    });

    // 5. SUBMIT FORMULÁRA PRE NAHLÁSENIE (Riešenie B)
    const reportForm = document.getElementById('reportForm');
    reportForm?.addEventListener('submit', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const bootstrapModal = bootstrap.Modal.getInstance(document.getElementById('reportModal'));
        const formData = new FormData(this);
        
        djangoFetch(this.action, {
            method: 'POST',
            body: formData,
            headers: { 'X-CSRFToken': formData.get('csrfmiddlewaretoken') }
        })
        .then(res => {
            if (!res.ok) throw new Error();
            
            this.reset();
            bootstrapModal?.hide();

            const alertHtml = `
                <div class="alert alert-success alert-dismissible fade show" role="alert">
                    Ďakujeme za nahlásenie. Vaše upozornenie sme prijali a administrátori ho preveria.
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            `;
            
            const container = document.querySelector('.content-wrapper');
            if (container) {
                container.insertAdjacentHTML('afterbegin', alertHtml);
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        })
        .catch(() => alert("Chyba pri spracovaní nahlásenia na serveri."));
    });

    // Reset report formulára po zatvorení modalu
    document.getElementById('reportModal')?.addEventListener('hidden.bs.modal', () => reportForm?.reset());
});
