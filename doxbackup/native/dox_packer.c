#include <stdio.h>
#include <string.h>
#include <windows.h>
#include <fcntl.h>
#include <io.h>

#define BUFFER_SIZE (1024 * 1024)

void pack_file(const char *base_path, const char *full_path, char *buffer) {
    // Calcula caminho relativo
    const char *rel = full_path + strlen(base_path);
    if (*rel == '\\' || *rel == '/') rel++;

    FILE *f = fopen(full_path, "rb");
    if (!f) return;

    // Obtém tamanho
    fseek(f, 0, SEEK_END);
    unsigned long long dlen = _ftelli64(f);
    fseek(f, 0, SEEK_SET);

    unsigned int nlen = strlen(rel);

    // Protocolo: [nlen][name][dlen][data]
    fwrite(&nlen, 4, 1, stdout);
    fwrite(rel, 1, nlen, stdout);
    fwrite(&dlen, 8, 1, stdout);

    size_t n;
    while ((n = fread(buffer, 1, BUFFER_SIZE, f)) > 0) {
        fwrite(buffer, 1, n, stdout);
    }
    fclose(f);
}

int main(int argc, char *argv[]) {
    if (argc < 3) return 1;
    // argv[1] = Caminho Base
    // argv[2] = Caminho para arquivo de lista (.txt)

    _setmode(_fileno(stdout), _O_BINARY);
    char *buf = malloc(BUFFER_SIZE);

    FILE *list_f = fopen(argv[2], "r");
    if (!list_f) return 1;

    char line[32768];
    while (fgets(line, sizeof(line), list_f)) {
        line[strcspn(line, "\r\n")] = 0; // Remove \n
        if (strlen(line) > 0) {
            pack_file(argv[1], line, buf);
        }
    }

    fclose(list_f);
    free(buf);
    return 0;
}