// Globálne funkcie dostupné aj pre inline atribúty (napr. onclick v HTML)
window.spresnitPolohu = function() {
    const statusText = document.getElementById('status-polohy');
    const inputPoloha = document.getElementById('lokalita-input');

    if (!navigator.geolocation) {
        alert("Váš prehliadač nepodporuje geolokalizáciu.");
        return;
    }

    statusText.innerText = "Zisťujem polohu...";

    navigator.geolocation.getCurrentPosition(
        async (position) => {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;

            try {
                const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`);
                const data = await res.json();
                const mesto = data.address.city || data.address.town || data.address.village || "";
                inputPoloha.value = mesto;
                statusText.innerText = "Poloha spresnená.";
            } catch (e) {
                statusText.innerText = "Chyba pri získavaní názvu.";
            }
        },
        () => { statusText.innerText = "Prístup zamietnutý."; }
    );
};

document.addEventListener('DOMContentLoaded', function() {
    let cropper;
    let croppedBlobs = [];
    const MAX_PHOTOS = 10;
    
    const imageInput = document.getElementById('imageInput');
    const previews = document.getElementById('previews');
    const cropModal = document.getElementById('cropModal');
    const imageToCrop = document.getElementById('imageToCrop');
    const photoCountDisplay = document.getElementById('photoCount');
    const uploadBtn = document.getElementById('uploadBtn');
    const dropZone = document.getElementById('dropZone');
    let pendingFiles = [];

    // Počítadlo znakov pre názov
    const inputNazov = document.querySelector('#id_nazov');
    const countDisplay = document.querySelector('#char-count');
    
    if (inputNazov && countDisplay) {
        const aktualizujPocitadlo = () => {
            countDisplay.textContent = 50 - inputNazov.value.length;
        };
        inputNazov.addEventListener('input', aktualizujPocitadlo);
        aktualizujPocitadlo(); // Prvotné načítanie pri editácii
    }

    // --- 1. INICIALIZÁCIA EXISTUJÚCICH FOTIEK PRI ÚPRAVE ---
    const dataElement = document.getElementById('existing-photos-data');
    if (dataElement) {
        try {
            const existingPhotos = JSON.parse(dataElement.textContent);
            const validPhotos = existingPhotos.filter(url => url && url.trim() !== "");

            validPhotos.forEach((url, index) => {
                fetch(url)
                    .then(res => {
                        if (!res.ok) throw new Error('Foto sa nepodarilo stiahnuť');
                        return res.blob();
                    })
                    .then(blob => {
                        const fileName = url.split('/').pop() || `povodna_foto_${index}.jpg`;
                        const file = new File([blob], fileName, { type: blob.type });
                        croppedBlobs.push(file);
                        renderPreviews();
                        updateInterface();
                    })
                    .catch(err => console.error("Chyba pri načítaní existujúcej fotky:", url, err));
            });
        } catch (e) {
            console.error("Chyba pri spracovaní JSON dát:", e);
        }
    }

    // --- 2. LOGIKA PRE DRAG & DROP A PASTE ---
    if (dropZone) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, e => { e.preventDefault(); e.stopPropagation(); }, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.add('border-info', 'bg-info', 'bg-opacity-10'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.remove('border-info', 'bg-info', 'bg-opacity-10'), false);
        });

        dropZone.addEventListener('drop', e => handleFiles(e.dataTransfer.files));
    }

    imageInput?.addEventListener('change', e => handleFiles(e.target.files));
    
    window.addEventListener('paste', e => {
        if (e.clipboardData.files.length > 0) handleFiles(e.clipboardData.files);
    });

    function handleFiles(files) {
        const availableSlots = MAX_PHOTOS - croppedBlobs.length;
        if (availableSlots <= 0) {
            alert("Dosiahli ste maximálny limit 10 fotografií.");
            return;
        }

        let selectedFiles = Array.from(files).filter(file => file.type.startsWith('image/'));
        if (selectedFiles.length > availableSlots) {
            alert(`Môžete pridať už len ${availableSlots} fotiek.`);
            selectedFiles = selectedFiles.slice(0, availableSlots);
        }

        pendingFiles = [...pendingFiles, ...selectedFiles];
        if (cropModal?.classList.contains('d-none')) processNextFile();
    }

    // --- 3. OREZÁVANIE (CROPPER) ---
    function processNextFile() {
        if (pendingFiles.length === 0) {
            if (imageInput) imageInput.value = "";
            return;
        }

        const file = pendingFiles.shift();
        const reader = new FileReader();
        reader.onload = function(event) {
            if (!imageToCrop || !cropModal) return;
            imageToCrop.src = event.target.result;
            cropModal.classList.remove('d-none');
            
            if (cropper) cropper.destroy();
            cropper = new Cropper(imageToCrop, {
                aspectRatio: NaN,
                viewMode: 1,
                autoCropArea: 1,
                dragMode: 'move',
                restore: false,
                guides: true,
                center: true,
                cropBoxMovable: true,
                cropBoxResizable: true,
                toggleDragModeOnDblclick: false,
            });
        };
        reader.readAsDataURL(file);
    }

    document.getElementById('selectAllBtn')?.addEventListener('click', () => {
        if (!cropper) return;
        cropper.setCropBoxData({
            left: 0, top: 0,
            width: cropper.getContainerData().width,
            height: cropper.getContainerData().height
        });
    });

    document.getElementById('saveCrop')?.addEventListener('click', () => {
        if (!cropper) return;
        const canvas = cropper.getCroppedCanvas({ maxWidth: 1200 });
        canvas.toBlob(blob => {
            const file = new File([blob], `img_${Date.now()}.jpg`, { type: "image/jpeg" });
            croppedBlobs.push(file);
            renderPreviews();
            updateInterface();
            cropModal?.classList.add('d-none');
            processNextFile();
        }, 'image/jpeg', 0.9);
    });

    document.getElementById('cancelCrop')?.addEventListener('click', () => {
        cropModal?.classList.add('d-none');
        processNextFile();
    });

    // --- 4. RENDER A ROZHRANIE ---
    function renderPreviews() {
        if (!previews) return;
        previews.innerHTML = "";
        
        // Vytvorenie dočasnej funkcie v objekte window, aby fungovalo inline mazanie tlačidlom
        window._removePhotoGlobal = function(index) {
            croppedBlobs.splice(index, 1);
            renderPreviews();
            updateInterface();
        };

        croppedBlobs.forEach((file, index) => {
            const url = URL.createObjectURL(file);
            const div = document.createElement('div');
            div.className = "position-relative m-1";
            div.innerHTML = `
                <img src="${url}" class="rounded border border-info shadow-sm" style="width: 120px; height: 100px; object-fit: contain; background: #000;">
                <button type="button" class="btn btn-danger btn-sm position-absolute top-0 end-0 rounded-circle" 
                        style="transform: translate(30%, -30%); width: 25px; height: 25px; line-height: 1;" 
                        onclick="window._removePhotoGlobal(${index})">&times;</button>
            `;
            previews.appendChild(div);
        });
    }

    function updateInterface() {
        if (!photoCountDisplay) return;
        const count = croppedBlobs.length;
        photoCountDisplay.innerText = `${count} / ${MAX_PHOTOS} fotografií`;
        if (count >= MAX_PHOTOS) {
            photoCountDisplay.classList.replace('text-white-50', 'text-danger');
            if (uploadBtn) uploadBtn.disabled = true;
        } else {
            photoCountDisplay.classList.replace('text-danger', 'text-white-50');
            if (uploadBtn) uploadBtn.disabled = false;
        }
    }

    // --- 5. ODOSLANIE FORMY ---
    const form = document.getElementById('inzeratForm');
    form.onsubmit = function(e) {
        e.preventDefault();
        
        const btn = document.getElementById('submit-btn');
        const btnText = document.getElementById('btn-text');
        const btnSpinner = document.getElementById('btn-spinner');
        const nextUrl = this.getAttribute('data-next-url');
        const csrfToken = this.querySelector('[name=csrfmiddlewaretoken]')?.value;

        if (croppedBlobs.length === 0) {
            alert("Pridajte aspoň jednu fotografiu.");
            return;
        }

        btn.disabled = true;
        if (btnText) btnText.innerText = "Spracovávam (AI analýza)...";
        btnSpinner?.classList.remove('d-none');

        let formData = new FormData(this);
        formData.delete('dodatocne_obrazky'); 
        
        croppedBlobs.forEach((file, index) => {
            formData.append('dodatocne_obrazky', file, file.name || `foto_${index}.jpg`);
        });

        fetch(window.location.href, {
            method: 'POST',
            body: formData,
            headers: { 'X-CSRFToken': csrfToken }
        })
        .then(async response => {
            if (response.ok) {
                window.location.href = nextUrl;
            } else if (response.status === 429) {
                alert("Spomaľte! Inzerát môžete pridať raz za 30 sekúnd.");
                resetButton(btn, btnText, btnSpinner);
            } else {
                alert("Chyba pri ukladaní. Skontrolujte povinné polia.");
                resetButton(btn, btnText, btnSpinner);
            }
        })
        .catch(err => {
            console.error("Chyba siete:", err);
            alert("Chyba pripojenia k serveru.");
            resetButton(btn, btnText, btnSpinner);
        });
    };

    function resetButton(btn, text, spinner) {
        if (!btn) return;
        btn.disabled = false;
        if (text) text.innerHTML = '<i class="bi bi-check-lg me-1"></i> Uložiť inzerát';
        spinner?.classList.add('d-none');
    }
});