#include <stdio.h>
#include <string.h>
#include <windows.h>
#include <fcntl.h>
#include <io.h>

#define BUFFER_SIZE (1024 * 1024)

// LISTA DE EXCLUSÃO DEFINITIVA
const char *DOX_SKIP_LIST[] = {
    "venv", ".venv", "__pycache__", ".git", "node_modules", 
    "tmp", "temp", ".cache", "dist", "build", 
    "nppBackup", "thirdparty", ".doxoade", NULL 
};

int should_skip(const char *name) {
    // 1. Ignora pastas da lista
    for (int i = 0; DOX_SKIP_LIST[i] != NULL; i++) {
        if (stricmp(name, DOX_SKIP_LIST[i]) == 0) return 1;
    }
    // 2. Ignora extensões de lixo (.bak e .log)
    const char *dot = strrchr(name, '.');
    if (dot) {
        if (stricmp(dot, ".bak") == 0 || stricmp(dot, ".log") == 0) return 1;
    }
    return 0;
}

void pack_recursive(const char *base_path, char *curr_path, char *buffer) {
    char search[MAX_PATH];
    sprintf(search, "%s\\*", curr_path);
    WIN32_FIND_DATA fd;
    HANDLE h = FindFirstFile(search, &fd);
    if (h == INVALID_HANDLE_VALUE) return;

    do {
        if (!strcmp(fd.cFileName, ".") || !strcmp(fd.cFileName, "..")) continue;
        if (should_skip(fd.cFileName)) continue; // FILTRO ATIVO

        char full[MAX_PATH];
        sprintf(full, "%s\\%s", curr_path, fd.cFileName);

        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            pack_recursive(base_path, full, buffer);
        } else {
            const char *rel = full + strlen(base_path) + 1;
            unsigned int nlen = strlen(rel);
            unsigned long long dlen = ((unsigned long long)fd.nFileSizeHigh << 32) | fd.nFileSizeLow;
            fwrite(&nlen, 4, 1, stdout);
            fwrite(rel, 1, nlen, stdout);
            fwrite(&dlen, 8, 1, stdout);
            FILE *f = fopen(full, "rb");
            if (f) {
                size_t n;
                while ((n = fread(buffer, 1, BUFFER_SIZE, f)) > 0) fwrite(buffer, 1, n, stdout);
                fclose(f);
            }
        }
    } while (FindNextFile(h, &fd));
    FindClose(h);
}

int main(int argc, char *argv[]) {
    if (argc < 2) return 1;
    _setmode(_fileno(stdout), _O_BINARY);
    char *buf = malloc(BUFFER_SIZE);
    pack_recursive(argv[1], argv[1], buf);
    free(buf);
    return 0;
}