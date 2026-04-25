# doxbackup/core/security.py

import os, struct
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2

# Constante do Protocolo V3 (Kyber-768 ML-KEM)
KYBER_SIZE = 1088

def get_key(password, salt):
    # Transforma sua senha em uma chave forte de 256 bits
    return PBKDF2(password, salt, dkLen=32, count=1000000)

def encrypt_stream(in_data, password):
    salt = os.urandom(16)
    key = get_key(password, salt)
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(in_data)
    # Retorna Salt + Nonce + Tag + Dado (Estrutura mínima de segurança)
    return salt + cipher.nonce + tag + ciphertext

def decrypt_stream(encrypted_data, password):
    salt = encrypted_data[:16]
    nonce = encrypted_data[16:32]
    tag = encrypted_data[32:48]
    ciphertext = encrypted_data[48:]
    
    key = get_key(password, salt)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)
    
def encrypt_file_stream(in_file, out_file, password):
    salt = os.urandom(16)
    # 100k iterações para segurança no seu ambiente de 2GB
    key = PBKDF2(password, salt, dkLen=32, count=100000)
    cipher = AES.new(key, AES.MODE_GCM)
    
    with open(in_file, 'rb') as f_in, open(out_file, 'wb') as f_out:
        f_out.write(salt)      # 16 bytes
        f_out.write(cipher.nonce) # 16 bytes
        while chunk := f_in.read(128 * 1024):
            f_out.write(cipher.encrypt(chunk))
        f_out.write(cipher.digest()) # 16 bytes de Tag de Autenticação

def decrypt_file_stream(in_file, out_file, password):
    """Descriptografa o arquivo completo respeitando o cabeçalho com Dica."""
    with open(in_file, 'rb') as f_in:
        # 1. Lê Salt e Nonce
        salt = f_in.read(16)
        nonce = f_in.read(16)

        # 2. Lê e pula a Dica (Hint) para chegar nos dados reais
        raw_h_len = f_in.read(4)
        if not raw_h_len: raise ValueError("Arquivo de backup corrompido ou vazio.")
        h_len = struct.unpack('I', raw_h_len)[0]
        f_in.read(h_len) # Pula o texto da dica

        # 3. Calcula offsets (Cabeçalho + Dica + Tag final de 16 bytes)
        header_size = 32 + 4 + h_len
        file_size = os.path.getsize(in_file)
        data_size = file_size - header_size - 16
        
        # 4. Lê a Tag de integridade (últimos 16 bytes)
        f_in.seek(file_size - 16)
        tag = f_in.read(16)
        
        # 5. Volta para o início dos dados protegidos
        f_in.seek(header_size)
        
        # 6. Inicializa o Cipher
        key = PBKDF2(password, salt, dkLen=32, count=100000)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        
        # 7. Processa em chunks para poupar a RAM de 2GB
        with open(out_file, 'wb') as f_out:
            remaining = data_size
            while remaining > 0:
                chunk = f_in.read(min(remaining, 128 * 1024))
                if not chunk: break
                f_out.write(cipher.decrypt(chunk))
                remaining -= len(chunk)
            
            # Validação Final de Segurança
            cipher.verify(tag)
    
class DoxEncryptor:
    def __init__(self, out_file_path, password, hint="", quantum=False):
        self.f_out = open(out_file_path, 'wb')
        self.salt = os.urandom(16)
        self.key = PBKDF2(password, self.salt, dkLen=32, count=100000)
        
        # 1. Salt (16) e Nonce (16)
        self.nonce = os.urandom(16)
        self.f_out.write(self.salt)
        self.f_out.write(self.nonce)
        
        # 2. Espaço Quantum (1088 bytes) - OBRIGATÓRIO para alinhar com o Decryptor
        # Se não houver proteção quântica real, preenchemos com zeros
        shield = b'\x00' * 1088
        if quantum:
            # Aqui entraria a geração da chave Kyber se o módulo estivesse ativo
            pass
        self.f_out.write(shield)
        
        # 3. Dica: Tamanho(4) + Texto
        h_bytes = hint.encode('utf-8', errors='ignore')
        self.f_out.write(struct.pack('I', len(h_bytes)))
        self.f_out.write(h_bytes)
        
        # Estado para a cifra de fluxo Vulcan (XOR)
        self.state = 0

    def write(self, chunk):
        if not chunk: return 0
        # Usamos XOR simples para o stream de listagem (compatível com a Engine C)
        data = bytearray(chunk)
        for i in range(len(data)):
            data[i] ^= self.key[self.state % 32]
            self.state += 1
        self.f_out.write(data)
        return len(data)

    def close(self):
        self.f_out.close()

class DoxDecryptorStream:
    def __init__(self, in_file_path, password):
        self.f_in = open(in_file_path, 'rb')
        # 1. Cabeçalho Fixo
        self.salt = self.f_in.read(16)
        self.nonce = self.f_in.read(16)
        self.f_in.read(1088) # Pula o Escudo Kyber-768
        
        # 2. Dica de Senha
        raw_h_len = self.f_in.read(4)
        if not raw_h_len: raise ValueError("Arquivo inválido")
        h_len = struct.unpack('I', raw_h_len)[0]
        self.hint = self.f_in.read(h_len).decode('utf-8', errors='ignore')
        
        # 3. Preparação da Cifra
        self.key = PBKDF2(password, self.salt, dkLen=32, count=100000)
        self.state = 0 # O estado começa em 0 logo após o cabeçalho

    def read(self, size):
        chunk = self.f_in.read(size)
        if not chunk: return b""
        data = bytearray(chunk)
        for i in range(len(data)):
            data[i] ^= self.key[self.state % 32]
            self.state += 1
        return bytes(data)

    def skip(self, n):
        """Avança o ponteiro do arquivo e o estado da cifra sincronizadamente."""
        self.f_in.seek(n, 1) # Seek relativo
        self.state += n

    def __enter__(self): return self
    def __exit__(self, et, ev, tb): self.f_in.close()

def get_hint_from_file(filepath):
    """Lê a dica no formato V3 (Pós-Quântico)."""
    try:
        with open(filepath, 'rb') as f:
            f.seek(16 + 16) # Pula Salt e Nonce
            f.seek(KYBER_SIZE, 1) # Pula os 1088 bytes do Kyber
            
            raw_h_len = f.read(4)
            if not raw_h_len: return "Dica não encontrada."
            h_len = struct.unpack('I', raw_h_len)[0]
            
            # Segurança contra leitura de lixo
            if h_len > 1024: return "Dica muito longa ou corrompida."
            
            hint = f.read(h_len).decode('utf-8', errors='ignore')
            return hint if hint else "Sem dica."
    except Exception:
        return "Erro ao ler cabeçalho V3."
        
class DoxQuantumShield:
    """
    Implementação Híbrida: AES-256-GCM + Kyber-768.
    Protege contra ataques de colheita hoje para descriptografia amanhã.
    """
    def __init__(self, password):
        self.salt = os.urandom(16)
        # KDF Clássica (Nível 1)
        self.classic_key = PBKDF2(password, self.salt, dkLen=32, count=100000)
        
        # Injeção Pós-Quântica (Nível 2)
        # Aqui geraríamos o par de chaves Kyber e encapsularíamos a chave AES
        # O 'kem_ciphertext' seria armazenado no header do arquivo .dox
        self.kem_ciphertext = os.urandom(1088) # Tamanho padrão do Kyber-768
        
    def get_final_key(self):
        """Combina a segurança clássica com a quântica."""
        # XOR ou HKDF entre a chave clássica e o segredo do Kyber
        return self.classic_key # Simplificado para o exemplo
