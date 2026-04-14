import os, struct
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2

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
    def __init__(self, out_file_path, password, hint=""):
        self.f_out = open(out_file_path, 'wb')
        self.salt = os.urandom(16)
        self.key = PBKDF2(password, self.salt, dkLen=32, count=100000)
        self.cipher = AES.new(self.key, AES.MODE_GCM)
        
        # Cabeçalho: Salt(16) + Nonce(16)
        self.f_out.write(self.salt)
        self.f_out.write(self.cipher.nonce)
        
        # Dica: Tamanho(4) + Texto
        h_bytes = hint.encode('utf-8', errors='ignore')
        self.f_out.write(struct.pack('I', len(h_bytes)))
        self.f_out.write(h_bytes)

    def write(self, chunk):
        if chunk: self.f_out.write(self.cipher.encrypt(chunk))
        return len(chunk)

    def flush(self): self.f_out.flush()
    def close(self):
        if not self.f_out.closed:
            self.f_out.write(self.cipher.digest())
            self.f_out.close()

class DoxDecryptorStream:
    def __init__(self, in_file_path, password):
        self.f_in = open(in_file_path, 'rb')
        self.salt = self.f_in.read(16)
        self.nonce = self.f_in.read(16)
        
        h_len = struct.unpack('I', self.f_in.read(4))[0]
        self.f_in.read(h_len) # Pula a dica
        
        header_size = 32 + 4 + h_len
        self.data_size = os.path.getsize(in_file_path) - header_size - 16
        self.bytes_read = 0
        self.key = PBKDF2(password, self.salt, dkLen=32, count=100000)
        self.cipher = AES.new(self.key, AES.MODE_GCM, nonce=self.nonce)

    def read(self, size):
        if self.bytes_read >= self.data_size: return b""
        chunk = self.f_in.read(min(size, self.data_size - self.bytes_read))
        dec = self.cipher.decrypt(chunk)
        self.bytes_read += len(chunk)
        return dec

    def __enter__(self): return self
    def __exit__(self, et, ev, tb): self.f_in.close()

def get_hint_from_file(filepath):
    """Lê a dica sem precisar da senha e sem carregar o arquivo na RAM."""
    try:
        with open(filepath, 'rb') as f:
            f.seek(32) # Pula salt(16) e nonce(16)
            raw_len = f.read(4)
            if not raw_len or len(raw_len) < 4: return "Nenhuma dica disponível."
            h_len = struct.unpack('I', raw_len)[0]
            # Limita a dica a 1KB por segurança
            if h_len > 1024: return "Dica muito longa ou corrompida."
            return f.read(h_len).decode('utf-8', errors='ignore')
    except Exception:
        return "Nenhuma dica disponível (arquivo pode ser de versão antiga)."