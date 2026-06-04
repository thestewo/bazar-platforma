document.addEventListener('DOMContentLoaded', function() {
    // === 1. LOGIKA GALÉRIE A OVERLAY SYSTÉMU ===
    const thumbs = document.querySelectorAll('.ebay-thumb-container');
    const carousel = document.getElementById('inzeratCarousel');
    const overlay = document.getElementById('photoOverlay');
    const fullImg = document.getElementById('fullImage');

    function openPhotoOverlay(src) {
        if (!overlay || !fullImg) return;
        overlay.classList.remove('d-none');
        overlay.classList.add('d-flex');
        fullImg.src = src;
        document.body.style.overflow = 'hidden';
    }

    function closePhotoOverlay() {
        if (!overlay) return;
        overlay.classList.add('d-none');
        overlay.classList.remove('d-flex');
        document.body.style.overflow = '';
    }

    if (carousel) {
        carousel.addEventListener('slid.bs.carousel', function () {
            const activeSlide = carousel.querySelector('.active');
            if (!activeSlide) return;
            const img = activeSlide.querySelector('img');
            if (!img) return;
            
            let index = img.getAttribute('data-img-index');
            thumbs.forEach(t => t.classList.remove('active'));
            if (thumbs[index]) thumbs[index].classList.add('active');
        });
    }

    document.querySelectorAll('.open-overlay').forEach(img => {
        img.onclick = () => openPhotoOverlay(img.src);
    });

    overlay?.addEventListener('click', function(e) {
        if (e.target !== fullImg) closePhotoOverlay();
    });


    // === 2. LOGIKA AI PORADCU ===
    const btnAi = document.getElementById('btn-ai-start');
    btnAi?.addEventListener('click', function() {
        const content = document.getElementById('ai-content');
        const loading = document.getElementById('ai-loading');
        const url = this.getAttribute('data-url'); // Bezpečné načítanie Django URL z atribútu

        if (!url) return;

        btnAi.classList.add('d-none');
        loading?.classList.remove('d-none');

        fetch(url)
            .then(response => response.json())
            .then(data => {
                loading?.classList.add('d-none');
                if (content && window.marked) {
                    content.classList.remove('d-none');
                    content.innerHTML = window.marked.parse(data.analyza);
                }
            })
            .catch(error => {
                console.error('AI Error:', error);
                loading?.classList.add('d-none');
                btnAi.classList.remove('d-none');
                alert('Chyba pri generovaní analýzy.');
            });
    });
});