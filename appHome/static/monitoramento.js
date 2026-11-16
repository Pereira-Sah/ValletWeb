(() => {
    'use strict';

    const page = document.querySelector('.monitoramento-page');
    if (!page) return;

    const cameras = JSON.parse(document.getElementById('monitoramento-data').textContent);
    const grid = page.querySelector('.monitoramento-grid');
    const template = document.getElementById('monitoramento-card');
    const filters = page.querySelectorAll('button[data-status]');
    const empty = page.querySelector('.monitoramento-empty');
    const count = page.querySelector('.monitoramento-count');
    const modal = page.querySelector('.monitoramento-modal');
    const modalMedia = modal.querySelector('.monitoramento-modal-media');
    const closeButton = modal.querySelector('.monitoramento-close');
    const cards = new Map();
    const FIRST_FRAME_TIMEOUT = 6000;
    let selectedStatus = 'all';
    let trigger;
    let expandedCamera;

    // Estado da conexão real independente dos status dos exemplos.
    const live = {
        state: 'connecting', image: null, generation: 0,
        probe: null, deadline: null, view: null, feedback: null, reconnect: null,
    };

    function unavailable(message, iconClass = 'bi-camera-video-off') {
        const state = document.createElement('div');
        state.className = 'monitoramento-unavailable';
        const icon = document.createElement('i');
        icon.className = `bi ${iconClass}`;
        icon.setAttribute('aria-hidden', 'true');
        const text = document.createElement('p');
        text.textContent = message;
        state.append(icon, text);
        return state;
    }

    function statusOf(camera) {
        // Ainda sem primeiro frame, a câmera não está online.
        return camera.kind === 'live' ? (live.state === 'live' ? 'online' : 'offline') : camera.status;
    }

    function applyFilter() {
        let visibleCount = 0;
        cameras.forEach(camera => {
            const visible = selectedStatus === 'all' || statusOf(camera) === selectedStatus;
            cards.get(camera.id).card.hidden = !visible;
            if (visible) visibleCount += 1;
        });
        empty.hidden = visibleCount > 0;
        count.textContent = `${visibleCount} ${visibleCount === 1 ? 'câmera exibida' : 'câmeras exibidas'}`;
        filters.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.status === selectedStatus)));
    }

    function setLiveState(state) {
        live.state = state;
        const camera = cameras.find(item => item.kind === 'live');
        if (!camera) return;
        const entry = cards.get(camera.id);
        const text = state === 'live' ? 'Ao vivo' : state === 'connecting' ? 'Conectando…' : 'Câmera indisponível';
        entry.badge.dataset.state = state === 'connecting' ? 'connecting' : statusOf(camera);
        entry.badge.querySelector('[data-status-label]').textContent = text;
        entry.expand.disabled = state !== 'live';
        live.feedback.querySelector('p').textContent = text;
        live.feedback.querySelector('i').className = state === 'connecting' ? 'bi bi-hourglass-split' : 'bi bi-camera-video-off';
        live.feedback.hidden = state === 'live';
        live.reconnect.hidden = state !== 'error';
        if (live.image) live.image.hidden = state !== 'live';
        applyFilter();
    }

    function clearFirstFrameTimers() {
        window.clearInterval(live.probe);
        window.clearTimeout(live.deadline);
        live.probe = null;
        live.deadline = null;
    }

    function stopStream() {
        live.generation += 1;
        clearFirstFrameTimers();
        const previous = live.image;
        live.image = null;
        if (previous) {
            // Cancela a requisição contínua antes de iniciar outra tentativa.
            previous.removeAttribute('src');
            previous.remove();
        }
    }

    function connectStream() {
        stopStream();
        setLiveState('connecting');
        const generation = live.generation;
        let url;
        try {
            url = new URL(page.dataset.streamUrl, document.baseURI);
            if (!['http:', 'https:'].includes(url.protocol)) throw new Error('URL de transmissão inválida');
            // URLSearchParams preserva os parâmetros de configuração já existentes.
            url.searchParams.set('_vallet_retry', `${Date.now()}-${generation}`);
        } catch {
            setLiveState('error');
            return;
        }

        // Uma imagem nova evita que dimensões antigas confirmem a tentativa seguinte.
        const image = document.createElement('img');
        image.alt = 'Transmissão ao vivo da câmera 01';
        image.width = 1600;
        image.height = 900;
        image.hidden = true;
        live.image = image;
        const currentAttempt = () => live.generation === generation && live.image === image;
        const fail = () => {
            if (!currentAttempt()) return;
            stopStream();
            setLiveState('error');
        };
        const confirmFirstFrame = () => {
            if (!currentAttempt() || live.state !== 'connecting') return;
            if (image.naturalWidth > 0 && image.naturalHeight > 0) {
                clearFirstFrameTimers();
                setLiveState('live');
            }
        };
        image.addEventListener('error', fail);
        image.addEventListener('load', confirmFirstFrame);
        live.view.prepend(image);
        // Inspeciona apenas o elemento durante a conexão inicial; não busca frames.
        // MJPEG pode disponibilizar dimensões antes de load, mantendo a resposta aberta.
        live.probe = window.setInterval(confirmFirstFrame, 100);
        live.deadline = window.setTimeout(() => {
            confirmFirstFrame();
            if (live.state === 'connecting') fail();
        }, FIRST_FRAME_TIMEOUT);
        image.src = url.href;
        // Primeiro frame confirma a conexão inicial, não a atualização contínua.
    }

    function openCamera(camera, button) {
        if (modal.open) return;
        trigger = button;
        expandedCamera = camera;
        modal.querySelector('#monitoramento-modal-title').textContent = camera.name;
        modal.querySelector('#monitoramento-modal-area').textContent = camera.area;
        modal.querySelector('.monitoramento-modal-note').textContent = camera.kind === 'live'
            ? 'Transmissão do ValletIoT' : 'Imagem estática de demonstração';
        if (camera.kind === 'live') {
            // Move a mesma árvore e o mesmo img, sem atribuir src ou abrir outra conexão.
            cards.get(camera.id).media.append(unavailable('Transmissão ampliada'));
            modalMedia.append(live.view);
        } else {
            const image = document.createElement('img');
            image.width = 1600;
            image.height = 900;
            image.alt = camera.alt;
            image.src = camera.image;
            modalMedia.replaceChildren(image);
        }
        modal.showModal();
    }

    function expandButton(camera) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'monitoramento-expand';
        button.setAttribute('aria-label', `Ampliar ${camera.name}`);
        button.setAttribute('aria-haspopup', 'dialog');
        const icon = document.createElement('i');
        icon.className = 'bi bi-arrows-fullscreen';
        icon.setAttribute('aria-hidden', 'true');
        button.append(icon, ' Ampliar');
        button.addEventListener('click', () => openCamera(camera, button));
        return button;
    }

    cameras.forEach(camera => {
        const card = template.content.firstElementChild.cloneNode(true);
        const heading = card.querySelector('h2');
        heading.id = `${camera.id}-title`;
        heading.textContent = camera.name;
        card.setAttribute('aria-labelledby', heading.id);
        card.querySelector('.monitoramento-area').textContent = camera.area;
        const badge = card.querySelector('.monitoramento-status');
        const media = card.querySelector('.monitoramento-media');
        const action = card.querySelector('.monitoramento-card-action');
        const entry = { card, badge, media, expand: null };
        cards.set(camera.id, entry);

        if (camera.kind === 'live') {
            badge.setAttribute('role', 'status');
            badge.setAttribute('aria-live', 'polite');
            live.view = document.createElement('div');
            live.view.className = 'monitoramento-live-view';
            live.feedback = unavailable('Conectando…', 'bi-hourglass-split');
            live.reconnect = document.createElement('button');
            live.reconnect.type = 'button';
            live.reconnect.className = 'monitoramento-reconnect';
            live.reconnect.textContent = 'Reconectar';
            live.reconnect.addEventListener('click', () => {
                // O botão desaparece durante a tentativa: mantém foco num controle visível.
                if (modal.open) closeButton.focus();
                else page.querySelector(`button[data-status="${selectedStatus}"]`).focus();
                connectStream();
            });
            live.feedback.append(live.reconnect);
            live.view.append(live.feedback);
            media.append(live.view);
            entry.expand = expandButton(camera);
            entry.expand.disabled = true;
            action.append(entry.expand);
        } else {
            badge.dataset.state = camera.status;
            badge.querySelector('[data-status-label]').textContent = camera.status === 'online' ? 'Online' : 'Offline';
            if (camera.status === 'online' && camera.image) {
                const image = document.createElement('img');
                image.alt = camera.alt;
                image.width = 1600;
                image.height = 900;
                image.decoding = 'async';
                entry.expand = expandButton(camera);
                image.addEventListener('error', () => {
                    media.replaceChildren(unavailable('Imagem indisponível'));
                    action.replaceChildren();
                }, { once: true });
                image.src = camera.image;
                media.append(image);
                action.append(entry.expand);
            } else {
                media.append(unavailable('Câmera indisponível'));
                const note = document.createElement('span');
                note.className = 'monitoramento-offline-note';
                note.textContent = 'Sem imagem disponível';
                action.append(note);
            }
        }
        grid.append(card);
    });

    // Filtrar oculta os cartões existentes: nunca recria o img do MJPEG.
    filters.forEach(button => button.addEventListener('click', () => {
        selectedStatus = button.dataset.status;
        applyFilter();
    }));
    closeButton.addEventListener('click', () => modal.close());
    modal.addEventListener('close', () => {
        if (expandedCamera?.kind === 'live') cards.get(expandedCamera.id).media.replaceChildren(live.view);
        modalMedia.replaceChildren();
        expandedCamera = null;
        const canFocus = element => element && !element.disabled && element.getClientRects().length > 0;
        if (canFocus(trigger)) trigger.focus({ preventScroll: true });
        else if (canFocus(live.reconnect)) live.reconnect.focus({ preventScroll: true });
        else page.querySelector(`button[data-status="${selectedStatus}"]`).focus({ preventScroll: true });
    });
    // Inclui Reconectar quando uma falha ocorre com a câmera ampliada.
    modal.addEventListener('keydown', event => {
        if (event.key !== 'Tab') return;
        const controls = [...modal.querySelectorAll('button')].filter(button => !button.disabled && button.getClientRects().length > 0);
        const first = controls[0], last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault(); last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault(); first.focus();
        }
    });
    modal.addEventListener('click', event => {
        if (event.target !== modal) return;
        const rect = modal.getBoundingClientRect();
        if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) modal.close();
    });
    window.addEventListener('pagehide', stopStream);
    window.addEventListener('pageshow', event => {
        if (event.persisted && !live.image) connectStream();
    });

    applyFilter();
    page.querySelector('.monitoramento-toolbar').hidden = false;
    if (cameras.some(camera => camera.kind === 'live')) connectStream();
})();
