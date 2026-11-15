(() => {
    'use strict';
    const loginForm = document.getElementById('loginForm');
    if (!loginForm) return;
    const password = document.getElementById('password');
    const toggle = document.getElementById('toggle-password');
    toggle.addEventListener('click', () => {
        const visible = password.type === 'password';
        password.type = visible ? 'text' : 'password';
        toggle.setAttribute('aria-label', visible ? 'Ocultar senha' : 'Mostrar senha');
        toggle.setAttribute('aria-pressed', String(visible));
    });
    const loginBotao = loginForm.querySelector('button[type="submit"]');
    const loginTextoOriginal = loginBotao.textContent;
    const feedback = document.getElementById('login-feedback');
    loginForm.addEventListener('submit', async event => {
        event.preventDefault();
        if (loginBotao.disabled) return;
        loginBotao.disabled = true; loginBotao.textContent = 'Entrando…';
        loginForm.setAttribute('aria-busy', 'true'); feedback.hidden = true;
        document.getElementById('email').removeAttribute('aria-invalid');
        password.removeAttribute('aria-invalid');
        const showError = text => {
            feedback.textContent = text; feedback.hidden = false;
            loginForm.setAttribute('aria-describedby', 'login-feedback');
        };
        try {
            const resp = await fetch('/auth/firebase/', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: document.getElementById('email').value, password: password.value })
            });
            const data = await resp.json();
            if (resp.ok) {
                window.location.href = data.redirect || '/gestor/';
            } else {
                showError(data.error || 'Não foi possível entrar. Confira seu e-mail e senha e tente novamente.');
                if (resp.status === 400 || resp.status === 401) {
                    document.getElementById('email').setAttribute('aria-invalid', 'true'); password.setAttribute('aria-invalid', 'true');
                }
            }
        } catch {
            showError('Não foi possível conectar. Verifique sua conexão e tente novamente.');
        } finally {
            loginBotao.disabled = false; loginBotao.textContent = loginTextoOriginal; loginForm.removeAttribute('aria-busy');
        }
    });
})();
