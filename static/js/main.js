// ReUse Campus — main.js
document.addEventListener('DOMContentLoaded', function () {
    const input = document.getElementById('id_image');
    const preview = document.getElementById('photo-preview');
    const previewImg = document.getElementById('photo-preview-img');
    const remove = document.getElementById('id_remove_image');
    const current = document.getElementById('current-photo');
    if (!input || !preview || !previewImg) return;

    input.addEventListener('change', function () {
        const file = input.files && input.files[0];
        if (!file) {
            preview.hidden = true;
            return;
        }
        if (previewImg.dataset.objectUrl) {
            URL.revokeObjectURL(previewImg.dataset.objectUrl);
        }
        const url = URL.createObjectURL(file);
        previewImg.dataset.objectUrl = url;
        previewImg.src = url;
        preview.hidden = false;
        if (remove) remove.checked = false;
        if (current) current.classList.remove('is-removed');
    });

    if (remove) {
        remove.addEventListener('change', function () {
            if (current) current.classList.toggle('is-removed', remove.checked);
            if (remove.checked) {
                preview.hidden = true;
                input.value = '';
            }
        });
    }
});
