
# olDox22 SysUtils — System Utilities

Uma suíte modular de ferramentas de diagnóstico e proteção de dados em desenvolvimento, otimizada para alta performance em ambientes com recursos limitados.

##  Arquitetura Híbrida
O SysUtils utiliza uma abordagem de três camadas para garantir velocidade e estabilidade:
1. **Python (Interface):** CLI intuitiva baseada em `Click`.
2. **C (Acelerador):** Processamento de I/O de baixo nível via `w64devkit`.

## Módulos Principais

### DiskDiag
Analista de armazenamento que mapeia o uso de disco e identifica candidatos para limpeza.
- **Scan:** Indexação ultra-rápida via SQLite.
- **Analyze:** Identificação de arquivos pesados, lixo de sistema e duplicatas.

### RamDiag
Monitor de telemetria para memória RAM e processos.
- **Status:** Visão da RAM física e virtual.
- **Top/Summary:** Identificação de processos "comilões" e árvore de parentesco (Pai/Filho).

###  DoxBackup
Sistema de backup blindado com foco em segurança e economia de disco.
- **Performance:** Varredura em C ignorando lixos de desenvolvimento automaticamente.
- **Streaming Chunks:** Processa gigabytes em blocos de 64KB.
- **Criptografia:** AES-256-GCM com suporte a dicas de senha integradas ao cabeçalho.

## Instalação e Preparação

1. **Dependências Python:**

```bash
pip install -e .
```

2. **Compilar Acelerador C:**
*(Requer gcc/w64devkit)*
```bash
gcc -O3 -s doxbackup/native/dox_packer.c -o doxbackup/native/dox_packer.exe
```

##  Exemplos de Uso

```bash
# Diagnóstico de Disco
sysutils disk scan C:\
sysutils disk analyze

# Monitoramento de RAM
sysutils ram top -v

# Backup Seguro
sysutils backup pack "C:\MeuProjeto" --hint "Lembrete da senha"
sysutils backup list backup_MeuProjeto.dox
```

---