/* android_sys/templates/benzaiten_shell/assets/dx_bridge.js */
/**
 * Hermes Bridge Mobile — Paridade com HermesRouter Desktop.
 * Permite que a UI em HTML/JS envie ações e receba respostas do sistema.
 */
window.__dx_callbacks__ = {};

window.__dx_send__ = function(action, payload) {
    return new Promise((resolve, reject) => {
        const id = 'msg_' + Math.random().toString(36).substring(2, 9);
        window.__dx_callbacks__[id] = { resolve, reject };

        const request = JSON.stringify({ id, action, payload: payload || {} });

        if (window.__dx_native__ && typeof window.__dx_native__.send === 'function') {
            window.__dx_native__.send(request);
        } else {
            console.warn('[HERMES-MOCK] Modo navegador/desktop:', request);
            resolve({ status: 'mock', payload: { echo: payload } });
        }
    });
};

window.__dx_receive__ = function(rawResponse) {
    try {
        const response = typeof rawResponse === 'string' ? JSON.parse(rawResponse) : rawResponse;
        const cb = window.__dx_callbacks__[response.id];
        if (cb) {
            if (response.status === 'success') {
                cb.resolve(response.payload);
            } else {
                cb.reject(new Error(response.payload?.message || 'Erro desconhecido'));
            }
            delete window.__dx_callbacks__[response.id];
        }
    } catch (e) {
        console.error('[HERMES] Falha ao processar resposta do backend:', e);
    }
};

console.log('✔ Hermes Mobile Bridge carregada.');
