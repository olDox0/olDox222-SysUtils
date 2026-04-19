#include <windows.h>
#include <stdio.h>
#include <stdint.h>

#define BUFFER_SIZE (1024 * 1024)
#define KYBER_768_SIZE 1088

typedef struct {
    uint8_t salt[16];
    uint8_t nonce[16];
    uint8_t kyber_ciphertext[KYBER_768_SIZE];
    uint32_t hint_len;
} DoxHeaderV3;

// Cifra de Fluxo Ultra-rápida Vulcan
void vulcan_crypt(uint8_t* data, DWORD len, const uint8_t* key, uint64_t* state) {
    for (DWORD i = 0; i < len; i++) {
        data[i] ^= key[(*state) % 32];
        (*state)++;
    }
}

void pack_single_file(HANDLE hOutput, const wchar_t* filePath, const wchar_t* relName, uint8_t* buffer, const uint8_t* key, uint64_t* state) {
    HANDLE hFile = CreateFileW(filePath, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hFile == INVALID_HANDLE_VALUE) return;

    LARGE_INTEGER fileSize;
    GetFileSizeEx(hFile, &fileSize);

    uint32_t nameLen = (uint32_t)wcslen(relName) * sizeof(wchar_t);
    DWORD written;

    // 1. Cifrar e Escrever o Tamanho do Nome (4 bytes)
    uint32_t nLenEnc = nameLen;
    vulcan_crypt((uint8_t*)&nLenEnc, 4, key, state);
    WriteFile(hOutput, &nLenEnc, 4, &written, NULL);

    // 2. Cifrar e Escrever o Nome do Arquivo
    uint8_t* encName = (uint8_t*)malloc(nameLen);
    memcpy(encName, relName, nameLen);
    vulcan_crypt(encName, nameLen, key, state);
    WriteFile(hOutput, encName, nameLen, &written, NULL);
    free(encName);

    // 3. Cifrar e Escrever o Tamanho do Arquivo (8 bytes)
    uint64_t fSizeEnc = (uint64_t)fileSize.QuadPart;
    vulcan_crypt((uint8_t*)&fSizeEnc, 8, key, state);
    WriteFile(hOutput, &fSizeEnc, 8, &written, NULL);

    // 4. Cifrar e Escrever o Conteúdo
    DWORD bytesRead;
    while (ReadFile(hFile, buffer, BUFFER_SIZE, &bytesRead, NULL) && bytesRead > 0) {
        vulcan_crypt(buffer, bytesRead, key, state);
        WriteFile(hOutput, buffer, bytesRead, &written, NULL);
    }

    CloseHandle(hFile);
}

__declspec(dllexport) int vulcan_dox_pack(
    const wchar_t* outputPath, 
    DoxHeaderV3* header, 
    const char* hint,
    const uint8_t* key,
    const wchar_t** fullPaths,  // Caminhos completos (C:\...)
    const wchar_t** relPaths,   // Caminhos relativos (diskdiag\core\...)
    int fileCount
) {
    HANDLE hOutput = CreateFileW(outputPath, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hOutput == INVALID_HANDLE_VALUE) return -1;

    DWORD written;
    header->hint_len = (uint32_t)strlen(hint);
    WriteFile(hOutput, header, sizeof(DoxHeaderV3), &written, NULL);
    WriteFile(hOutput, hint, header->hint_len, &written, NULL);

    uint8_t* buffer = (uint8_t*)VirtualAlloc(NULL, BUFFER_SIZE, MEM_COMMIT, PAGE_READWRITE);
    uint64_t crypt_state = 0;

    for (int i = 0; i < fileCount; i++) {
        // Usa fullPaths[i] para ler o arquivo, mas relPaths[i] para o nome no cabeçalho
        pack_single_file(hOutput, fullPaths[i], relPaths[i], buffer, key, &crypt_state);
    }

    VirtualFree(buffer, 0, MEM_RELEASE);
    CloseHandle(hOutput);
    return 0;
}