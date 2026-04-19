// engine/native/vulcan_ram.c
#include <windows.h>
#include <psapi.h>
#include <stdio.h>

__declspec(dllexport) int trim_all_processes() {
    DWORD processes[1024], cbNeeded, cProcesses;
    int success_count = 0;

    if (!EnumProcesses(processes, sizeof(processes), &cbNeeded)) return 0;
    cProcesses = cbNeeded / sizeof(DWORD);

    for (unsigned int i = 0; i < cProcesses; i++) {
        if (processes[i] != 0) {
            HANDLE hProcess = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA, FALSE, processes[i]);
            if (hProcess) {
                // Força o processo a liberar RAM não utilizada
                if (EmptyWorkingSet(hProcess)) {
                    success_count++;
                }
                CloseHandle(hProcess);
            }
        }
    }
    return success_count;
}