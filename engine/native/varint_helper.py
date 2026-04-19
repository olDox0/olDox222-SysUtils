# engine/native/varint_helper.py

def encode_varint(buf, n):
    """
    Implementação em Python do Varint Encoder.
    Nota: Quando o ORN estiver compilado, esta função será 
    substituída pela versão em C (orn_varint.c).
    """
    if n < 0: 
        raise ValueError("varint exige inteiro não-negativo")
    while n >= 0x80:
        buf.append((n & 0x7F) | 0x80)
        n >>= 7
    buf.append(n)