// engine/native/vulcan_cleaner.c (Versão 2.0 - com Feedback)
#include <windows.h>
#include <process.h>
#include <stdint.h>

typedef struct {
    wchar_t** files;
    uint8_t* results; // 1 para sucesso, 0 para falha
    int start;
    int end;
} DeleteBatch;

unsigned __stdcall delete_thread_worker(void* arg) {
    DeleteBatch* batch = (DeleteBatch*)arg;
    for (int i = batch->start; i < batch->end; i++) {
        if (DeleteFileW(batch->files[i])) {
            batch->results[i] = 1;
        } else {
            batch->results[i] = 0;
        }
    }
    return 0;
}

__declspec(dllexport) int batch_delete_parallel_ext(wchar_t** file_list, uint8_t* results_out, int total_files, int num_threads) {
    HANDLE* threads = malloc(sizeof(HANDLE) * num_threads);
    DeleteBatch* batches = malloc(sizeof(DeleteBatch) * num_threads);
    int files_per_thread = total_files / num_threads;

    for (int i = 0; i < num_threads; i++) {
        batches[i].files = file_list;
        batches[i].results = results_out;
        batches[i].start = i * files_per_thread;
        batches[i].end = (i == num_threads - 1) ? total_files : (i + 1) * files_per_thread;
        threads[i] = (HANDLE)_beginthreadex(NULL, 0, delete_thread_worker, &batches[i], 0, NULL);
    }

    WaitForMultipleObjects(num_threads, threads, TRUE, INFINITE);
    
    int total_deleted = 0;
    for (int i = 0; i < total_files; i++) {
        if (results_out[i]) total_deleted++;
    }

    for (int i = 0; i < num_threads; i++) CloseHandle(threads[i]);
    free(threads); free(batches);
    return total_deleted;
}