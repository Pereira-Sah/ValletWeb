(() => {
    'use strict';
    const menu = document.querySelector('.menu-toggle');
    const nav = document.querySelector('#site-nav');
    if (menu && nav) {
        const closeMenu = () => { nav.classList.remove('is-open'); menu.setAttribute('aria-expanded', 'false'); menu.setAttribute('aria-label', 'Abrir menu'); };
        menu.addEventListener('click', () => {
            const open = menu.getAttribute('aria-expanded') !== 'true';
            menu.setAttribute('aria-expanded', String(open));
            menu.setAttribute('aria-label', open ? 'Fechar menu' : 'Abrir menu');
            nav.classList.toggle('is-open', open);
        });
        nav.addEventListener('click', event => { if (event.target.closest('a')) closeMenu(); });
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape' && menu.getAttribute('aria-expanded') === 'true') { closeMenu(); menu.focus(); }
        });
    }

    const dialogTypes = [
        { id: 'contato-modal', open: '[data-open-contact]', close: '[data-close-contact]', form: 'contatoForm', email: 'contato-email' },
        { id: 'recuperar-senha-modal', open: '[data-open-password]', close: '[data-close-password]', form: 'recuperarSenhaForm', email: 'recuperar-email' }
    ];
    dialogTypes.forEach(config => {
        const modal = document.getElementById(config.id);
        if (!modal) return;
        const form = document.getElementById(config.form);
        let trigger;
        let previousOverflow;
        document.querySelectorAll(config.open).forEach(button => button.addEventListener('click', () => {
            if (modal.open) return;
            trigger = button;
            const email = document.getElementById(config.email);
            if (!email.value) email.value = document.getElementById('email')?.value.trim() || '';
            previousOverflow = document.body.style.overflow;
            document.body.style.overflow = 'hidden';
            modal.showModal();
        }));
        modal.querySelectorAll(config.close).forEach(button => button.addEventListener('click', () => modal.close()));
        modal.addEventListener('click', event => {
            if (event.target !== modal) return;
            const rect = modal.getBoundingClientRect();
            if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) modal.close();
        });
        modal.addEventListener('close', () => { document.body.style.overflow = previousOverflow; trigger?.focus({ preventScroll: true }); });
        modal.addEventListener('keydown', event => {
            if (event.key !== 'Tab') return;
            const controls = [...modal.querySelectorAll('button, input, select, textarea, a[href]')].filter(el => !el.disabled && el.tabIndex >= 0 && el.getClientRects().length);
            const first = controls[0], last = controls[controls.length - 1];
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        });
        form.addEventListener('submit', async event => {
            event.preventDefault();
            const feedback = form.querySelector('.contato-feedback');
            const button = form.querySelector('.contato-submit');
            if (button.disabled) return;
            const originalContent = [...button.childNodes].map(node => node.cloneNode(true));
            button.disabled = true; button.textContent = 'Enviando…';
            form.setAttribute('aria-busy', 'true'); feedback.hidden = true;
            try {
                const response = await fetch(form.dataset.url, { method: 'POST', body: new FormData(form), headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                const data = await response.json().catch(() => ({}));
                const ok = response.ok && data.ok;
                feedback.textContent = data.detail || (ok ? 'Enviado com sucesso.' : 'Não foi possível enviar agora. Tente novamente.');
                feedback.dataset.estado = ok ? 'ok' : 'erro';
                if (ok) form.reset();
            } catch {
                feedback.textContent = 'Erro de rede. Verifique sua conexão e tente novamente.';
                feedback.dataset.estado = 'erro';
            } finally {
                feedback.hidden = false; button.disabled = false; button.replaceChildren(...originalContent); form.removeAttribute('aria-busy');
            }
        });
    });
})();
