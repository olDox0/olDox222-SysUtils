import os
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
    with open(in_file, 'rb') as f_in:
        salt = f_in.read(16)
        nonce = f_in.read(16)
        file_size = os.path.getsize(in_file)
        f_in.seek(file_size - 16)
        tag = f_in.read(16)
        f_in.seek(32) 
        data_size = file_size - 32 - 16
        key = PBKDF2(password, salt, dkLen=32, count=100000)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        with open(out_file, 'wb') as f_out:
            remaining = data_size
            while remaining > 0:
                chunk = f_in.read(min(remaining, 128 * 1024))
                if not chunk: break
                f_out.write(cipher.decrypt(chunk))
                remaining -= len(chunk)
            cipher.verify(tag)