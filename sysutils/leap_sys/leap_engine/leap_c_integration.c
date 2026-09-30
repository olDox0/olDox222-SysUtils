/* ============================================================================
 * LEAP C INTEGRATION — Motor Nativo Win32/WinSock2 Ultra-Leve (Metalcraft)
 * ============================================================================
 * Silo: Projeto SysUtils
 * Target: Celeron N2808 @ 1.58GHz (Memória O(1), ~2MB RAM)
 * ============================================================================
 */
#include <winsock2.h>
#include <windows.h>
#include <stdio.h>
#include <stdint.h>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "user32.lib")

#define LEAP_MAGIC 0x4C454150 // "LEAP"
#define PACKET_MOUSE 1
#define PACKET_KEYBOARD 2

#pragma pack(push, 1)
typedef struct {
    uint32_t magic;
    uint8_t  type;
    int32_t  dx;
    int32_t  dy;
    uint32_t flags;
    uint16_t keycode;
} LeapPacket;
#pragma pack(pop)

static SOCKET g_sock = INVALID_SOCKET;
static HHOOK g_mouse_hook = NULL;
static HHOOK g_key_hook = NULL;
static int g_screen_width = 0;
static int g_active = 0;

LRESULT CALLBACK MouseProc(int nCode, WPARAM wParam, LPARAM lParam) {
    if (nCode >= 0 && g_sock != INVALID_SOCKET) {
        MSLLHOOKSTRUCT *ms = (MSLLHOOKSTRUCT *)lParam;
        
        // Gatilho: Cursor atingiu a borda direita da tela
        if (!g_active && ms->pt.x >= g_screen_width - 1) {
            g_active = 1;
            printf("[VULCAN:C] Borda atingida. Redirecionando cursor para PC Remoto...\n");
        }

        if (g_active) {
            LeapPacket pkt;
            pkt.magic = LEAP_MAGIC;
            pkt.type = PACKET_MOUSE;
            pkt.dx = ms->pt.x;
            pkt.dy = ms->pt.y;
            pkt.flags = (uint32_t)wParam;
            pkt.keycode = 0;
            send(g_sock, (const char *)&pkt, sizeof(pkt), 0);
            return 1; // Bloqueia movimento no host local
        }
    }
    return CallNextHookEx(g_mouse_hook, nCode, wParam, lParam);
}

// Inicia servidor nativo em C
__declspec(dllexport) int start_native_server(int port) {
    WSADATA wsa;
    WSAStartup(MAKEWORD(2, 2), &wsa);
    g_screen_width = GetSystemMetrics(SM_CXSCREEN);

    SOCKET listen_sock = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in server_addr;
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons((u_short)port);

    bind(listen_sock, (struct sockaddr *)&server_addr, sizeof(server_addr));
    listen(listen_sock, 1);
    printf("[VULCAN:C] Servidor Nativo aguardando cliente na porta %d...\n", port);

    g_sock = accept(listen_sock, NULL, NULL);
    printf("[VULCAN:C] Cliente conectado! Instalando Windows Hooks...\n");

    g_mouse_hook = SetWindowsHookEx(WH_MOUSE_LL, MouseProc, GetModuleHandle(NULL), 0);

    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    UnhookWindowsHookEx(g_mouse_hook);
    closesocket(g_sock);
    closesocket(listen_sock);
    WSACleanup();
    return 0;
}

// Inicia cliente nativo em C (recebe pacotes e injeta via SendInput)
__declspec(dllexport) int start_native_client(const char *server_ip, int port) {
    WSADATA wsa;
    WSAStartup(MAKEWORD(2, 2), &wsa);

    g_sock = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in server_addr;
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = inet_addr(server_ip);
    server_addr.sin_port = htons((u_short)port);

    if (connect(g_sock, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        printf("[ERRO] Falha ao conectar ao servidor %s:%d\n", server_ip, port);
        return -1;
    }
    printf("[VULCAN:C] Conectado ao Servidor! Aguardando entradas...\n");

    LeapPacket pkt;
    while (recv(g_sock, (char *)&pkt, sizeof(pkt), 0) > 0) {
        if (pkt.magic == LEAP_MAGIC && pkt.type == PACKET_MOUSE) {
            SetCursorPos(pkt.dx, pkt.dy);
            if (pkt.flags == WM_LBUTTONDOWN) mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0);
            else if (pkt.flags == WM_LBUTTONUP) mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0);
            else if (pkt.flags == WM_RBUTTONDOWN) mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0);
            else if (pkt.flags == WM_RBUTTONUP) mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0);
        }
    }

    closesocket(g_sock);
    WSACleanup();
    return 0;
}
