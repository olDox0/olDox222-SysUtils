window.__dx_callbacks__ = {};
window.__dx_audio_listeners__ = [];

window.__dx_send__ = function(action, payload) {
    return new Promise((resolve, reject) => {
        const id = 'msg_' + Math.random().toString(36).substring(2, 9);
        window.__dx_callbacks__[id] = { resolve, reject };
        const request = JSON.stringify({ id, action, payload: payload || {} });
        if (window.__dx_native__ && typeof window.__dx_native__.send === 'function') {
            window.__dx_native__.send(request);
        } else {
            resolve({ status: 'mock' });
        }
    });
};

window.__dx_receive__ = function(rawResponse) {
    try {
        const res = typeof rawResponse === 'string' ? JSON.parse(rawResponse) : rawResponse;
        const cb = window.__dx_callbacks__[res.id];
        if (cb) {
            if (res.status === 'success') cb.resolve(res.payload);
            else cb.reject(new Error(res.payload?.message || 'Erro'));
            delete window.__dx_callbacks__[res.id];
        }
        if (res.action === 'audio.state' && res.payload) {
            window.__dx_audio_listeners__.forEach(cb => cb(res.payload));
        }
    } catch (e) {}
};

window.__dx_on_shizuku__ = function(status) {
    const el = document.getElementById('shizuku-status');
    if (!el) return;
    el.textContent = status.toUpperCase();
    el.style.color = status === 'granted' ? '#26BC5F' : '#B32E2E';
};

window.__dx_audio__ = {
    start: (i) => window.__dx_send__('audio.start_monitor', { interval: i || 2000 }),
    stop: () => window.__dx_send__('audio.stop_monitor', {}),
    checkShizuku: () => window.__dx_send__('shizuku.check', {}),
    on: (cb) => window.__dx_audio_listeners__.push(cb)
};

window.__dx_shizuku_diag__ = () => window.__dx_send__('shizuku.diag', {});
