(() => {
    'use strict';
    const page = document.querySelector('.notificacoes-container');
    if (!page) return;
    const modal = page.querySelector('#notificacao-modal');
    const content = page.querySelector('#noti-modal-conteudo');
    let opener;
    let previousOverflow;

    const dateFormatter = new Intl.DateTimeFormat('pt-BR', {
        day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC'
    });
    function formatDates(root) {
        root.querySelectorAll('[data-noti-date]').forEach((element) => {
            const match = /^(\d{2})\/(\d{2})\/(\d{4})(?: (\d{2}:\d{2}))?$/.exec(element.dataset.notiDate);
            if (!match) return;
            const [, day, month, year, hour] = match;
            const date = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));
            if (date.getUTCDate() !== Number(day) || date.getUTCMonth() !== Number(month) - 1) return;
            const label = dateFormatter.format(date) + (hour ? ` às ${hour}` : '');
            if (element.textContent !== label) element.textContent = label;
        });
    }
    formatDates(page);
    const list = page.querySelector('#notificacoes-lista');
    if (list) new MutationObserver(() => formatDates(list)).observe(list, { childList: true, subtree: true });

    // Delegation keeps Details working when the list is replaced by an AJAX partial.
    page.addEventListener('click', (event) => {
        const button = event.target.closest('[data-detalhes]');
        if (button) {
            const template = button.closest('.noti-linha').querySelector('.noti-dados');
            opener = button;
            content.replaceChildren(template.content.cloneNode(true));
            formatDates(content);
            const image = content.querySelector('.noti-foto img');
            if (image) image.addEventListener('error', () => {
                image.hidden = true;
                content.querySelector('.noti-foto-erro').hidden = false;
            }, { once: true });
            previousOverflow ??= document.body.style.overflow;
            document.body.style.overflow = 'hidden';
            modal.showModal();
            modal.querySelector('[data-fechar]').focus();
        }
        if (event.target.closest('[data-fechar]')) modal.close();
    });
    modal.addEventListener('click', (event) => {
        if (event.target !== modal) return;
        const rect = modal.getBoundingClientRect();
        if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) modal.close();
    });
    modal.addEventListener('close', () => {
        // A new item may have been opened before the queued close event runs.
        if (modal.open) return;
        document.body.style.overflow = previousOverflow;
        previousOverflow = undefined;
        content.replaceChildren();
        const target = opener?.isConnected ? opener : page.querySelector('[data-detalhes], #filtro-tipo');
        target?.focus();
    });
    // Native dialog supplies Escape and background inertness; contain Tab explicitly.
    modal.addEventListener('keydown', (event) => {
        if (event.key !== 'Tab') return;
        const controls = [...modal.querySelectorAll('button:not(:disabled), a[href], input:not([type="hidden"])')].filter(el => el.getClientRects().length);
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    page.addEventListener('submit', (event) => {
        if (event.submitter?.value === 'excluir' && !window.confirm('Excluir esta notificação? Esta ação não pode ser desfeita.')) event.preventDefault();
    });
})();
