function showToast(message) {
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);

    window.setTimeout(() => {
        toast.remove();
    }, 2200);
}

async function copyFromInput(inputId) {
    const input = document.getElementById(inputId);
    if (!input) {
        return;
    }

    try {
        await navigator.clipboard.writeText(input.value);
        showToast('Copied to clipboard');
    } catch (error) {
        input.focus();
        input.select();
        document.execCommand('copy');
        showToast('Copied to clipboard');
    }
}

document.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-copy-target]');
    if (!trigger) {
        return;
    }

    copyFromInput(trigger.dataset.copyTarget);
});
