# -*- coding: utf-8 -*-
# ────────────────────────────────────────────────────────────
# NEXUS UI ENGINE (Embedded Version)
# Sincronizado por: Doxoade Control
# Data: 2026-04-25 19:05:55
# Projeto Alvo: Projeto SysUtils
# Compliance: MPoT-1, PASC-6.4 (High-Performance UI)
# ────────────────────────────────────────────────────────────

"""
Doxcolors Nexus Edition – High-Performance CLI UI Engine
Versão: 2.0 (Nexus UI)
"""
import os
import sys
import builtins
import time
import math
import threading
import itertools

# --- CORE ENGINE ---

def _ansi_enabled():
    if os.name != 'nt':
        return sys.stdout.isatty()
    return sys.stdout.isatty() or 'ANSICON' in os.environ or 'WT_SESSION' in os.environ or (os.environ.get('TERM_PROGRAM') == 'vscode')

ANSI_ENABLED = _ansi_enabled()

if os.name == 'nt' and ANSI_ENABLED:
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 4)
    except Exception:
        pass

class AnsiCode(str):
    __slots__ = ()
    def __new__(cls, code: str):
        if not ANSI_ENABLED: return str.__new__(cls, '')
        return str.__new__(cls, f'\x1b[{code}m')

class Back: # Adicionado para corrigir o NameError
    BLACK   = AnsiCode('40')
    BLUE    = AnsiCode('44')
    CYAN    = AnsiCode('46')
    GREEN   = AnsiCode('42')
    MAGENTA = AnsiCode('45')
    RED     = AnsiCode('41')
    RESET   = AnsiCode('49')
    WHITE   = AnsiCode('47')
    YELLOW  = AnsiCode('43')

class Fore:
    BLACK   = AnsiCode('30')
    BLUE    = AnsiCode('34')
    CYAN    = AnsiCode('36')
    DIM     = AnsiCode('2') 
    GREEN   = AnsiCode('32')
    MAGENTA = AnsiCode('35')
    RED     = AnsiCode('31')
    RESET   = AnsiCode('0')
    WHITE   = AnsiCode('37')
    YELLOW  = AnsiCode('33')
    
    LIGHTBLUE_EX    = AnsiCode('94')
    LIGHTCYAN_EX    = AnsiCode('96')
    LIGHTBLACK_EX   = AnsiCode('90')
    RED     = AnsiCode('91')
    LIGHTGREEN_EX   = AnsiCode('92')
    LIGHTYELLOW_EX  = AnsiCode('93')
    LIGHTMAGENTA_EX = AnsiCode('95')
    LIGHTWHITE_EX   = AnsiCode('97')

    # Nexus Semantic Colors

    ORANGE      = AnsiCode('38;2;255;100;0')   # ORANGE
    LIGHTYELLOW = AnsiCode('38;2;255;255;100')   # LIGHTYELLOW
    GREY        = AnsiCode('38;2;100;100;100')   # LIGHTYELLOW

    PRIMARY     = AnsiCode('38;2;0;108;255')   # Azul Nexus
    SUCCESS     = AnsiCode('38;2;38;188;95')   # Verde Estável
    ERROR       = AnsiCode('38;2;255;103;0')   # Laranja Erro
    WARNING     = AnsiCode('38;2;232;170;0')   # Amarelo Alerta
    STABLE      = AnsiCode('38;2;176;176;176') # Cinza (Código antigo/estável)
    VOLATILE    = AnsiCode('38;2;255;0;255')   # Magenta (Código sendo alterado)
    
    XYZ          = AnsiCode('38;2;255;155;0')   # ORANGE

class Style:
    DIM = AnsiCode('2'); NORMAL = AnsiCode('22'); BRIGHT = AnsiCode('1')
    RESET_ALL = AnsiCode('0'); BLINK = AnsiCode('5'); ITALIC = AnsiCode('3')
    HIDDEN = AnsiCode('?25l'); SHOW = AnsiCode('?25h') # Cursor control

# --- UTILS ---

def rgb(r, g, b): return AnsiCode(f'38;2;{r};{g};{b}')
def hex_to_ansi(hex_code: str):
    h = hex_code.lstrip('#')
    return rgb(*(int(h[i:i+2], 16) for i in (0, 2, 4)))

# --- NEXUS UI & ANIMATIONS ---

class NexusUI:
    """Motor de Interface Visual do Doxoade."""
    
    @staticmethod
    def gradient_text(text, start_hex="#006CFF", end_hex="#26BC5F"):
        """Gera um texto com gradiente linear."""
        if not ANSI_ENABLED: return text
        h1, h2 = start_hex.lstrip('#'), end_hex.lstrip('#')
        r1, g1, b1 = (int(h1[i:i+2], 16) for i in (0, 2, 4))
        r2, g2, b2 = (int(h2[i:i+2], 16) for i in (0, 2, 4))
        
        result = ""
        steps = len(text)
        for i, char in enumerate(text):
            r = int(r1 + (r2 - r1) * (i / max(1, steps-1)))
            g = int(g1 + (g2 - g1) * (i / max(1, steps-1)))
            b = int(b1 + (b2 - b1) * (i / max(1, steps-1)))
            result += f"\x1b[38;2;{r};{g};{b}m{char}"
        return result + "\x1b[0m"

    @staticmethod
    def decode_effect(target_text, duration=1.0):
        """Efeito de decodificação 'Matrix' para revelar texto."""
        import string
        import random

        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        start_time = time.time()
        while time.time() - start_time < duration:
            current = "".join(random.choice(chars) for _ in range(len(target_text)))
            sys.stdout.write(f"\r{Fore.PRIMARY}{current}{Style.RESET_ALL}")
            sys.stdout.flush()
            time.sleep(0.05)
        sys.stdout.write(f"\r{NexusUI.gradient_text(target_text)}\n")

    @staticmethod
    def pulse(text, hex_color="#FF00FF", speed=1.0):
        """Efeito de pulsar (fade in/out) - Requer terminal com suporte a TrueColor."""
        # Simulado via alternância de brilho se não houver suporte total
        pass 

    @staticmethod
    def play_animation(frames, interval=0.1, loops=2):
        """
        Animação multi-linha ultra-estável por contagem de linhas.
        """
        if not ANSI_ENABLED: return
        
        sys.stdout.write("\x1b[?25l") # Esconde cursor
        
        try:
            for loop in range(loops):
                for frame in frames:
                    # Limpa espaços e divide linhas
                    lines = frame.strip('\n').split('\n')
                    num_lines = len(lines)
                    
                    # Desenha o frame linha por linha
                    for line in lines:
                        # \r volta pro início da linha, \x1b[2K apaga o que tinha antes
                        sys.stdout.write("\r\x1b[2K" + line + "\n")
                    
                    sys.stdout.flush()
                    time.sleep(interval)
                    
                    # SOBE O CURSOR exatamente o número de linhas que imprimimos
                    # para desenhar o próximo frame por cima
                    sys.stdout.write(f"\x1b[{num_lines}A")
            
            # Ao terminar, move o cursor para baixo da animação
            sys.stdout.write(f"\x1b[{num_lines}B\n")
            
        finally:
            sys.stdout.write("\x1b[?25h") # Mostra cursor
            sys.stdout.flush()

    @staticmethod
    def apply_tags(text):
        import re
        from .doxcolors import Fore, Style, Back
        tags = re.findall(r'<(.*?)>', text)
        for tag in tags:
            tag_upper = tag.upper()
            replacement = ""
            if hasattr(Fore, tag_upper): replacement = getattr(Fore, tag_upper)
            elif hasattr(Style, tag_upper): replacement = getattr(Style, tag_upper)
            elif hasattr(Back, tag_upper): replacement = getattr(Back, tag_upper)
            if replacement: text = text.replace(f"<{tag}>", replacement)
        return text.replace("<RESET>", Style.RESET_ALL)

    @staticmethod
    def load_animation(file_path, separator="===FRAME==="):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            content = NexusUI.apply_tags(content)
            import re
            raw_parts = re.split(re.escape(separator), content)
            return [p.strip('\r\n') for p in raw_parts if p.strip()]
        except: return []

    @staticmethod
    def loader(file_path, interval=0.1, debug=False, ping_pong=False, color=""):
        frames = NexusUI.load_animation(file_path)
        return AsyncAnimation(frames, interval, debug=debug, ping_pong=ping_pong, base_color=color)

class Spinner:
    """Braille Loading Spinner."""
    frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    
    def __init__(self, message="Processando"):
        self.message = message
        self.idx = 0

    def step(self):
        frame = self.frames[self.idx % len(self.frames)]
        sys.stdout.write(f"\r{Fore.CYAN}{frame}{Fore.RESET} {self.message}...")
        sys.stdout.flush()
        self.idx += 1

    def finish(self, success=True):
        symbol = f"{Fore.SUCCESS}✔" if success else f"{Fore.ERROR}✘"
        sys.stdout.write(f"\r{symbol}{Fore.RESET} {self.message} Finalizado.\n")

class ProgressBar:
    """Barra de progresso semântica."""
    def __init__(self, total, label="Progresso", width=30):
        self.total = total
        self.label = label
        self.width = width

    def update(self, current):
        perc = min(100, int((current / self.total) * 100))
        filled = int((self.width * current) // self.total)
        bar = "█" * filled + "░" * (self.width - filled)
        color = Fore.SUCCESS if perc == 100 else Fore.PRIMARY
        sys.stdout.write(f"\r{self.label} {color}[{bar}] {perc}%{Fore.RESET}")
        sys.stdout.flush()

class AsyncAnimation:
    def __init__(self, frames, interval=0.1, debug=False, ping_pong=False, base_color=""):
        import shutil

        self.interval = interval
        self.running = threading.Event()
        self.lock = threading.Lock()
        self.ping_pong = ping_pong
        self.debug = debug
        self.base_color = base_color
        self.canvas_height = 0
        self.atomic_frames = [] 
        self._force_redraw = False

        if frames:
            term_width = shutil.get_terminal_size().columns
            # 1. Geometria Fixa: Calcula altura real do canvas
            self.canvas_height = max(len(f.split('\n')) for f in frames)
            
            for f in frames:
                lines = f.split('\n')
                # Normaliza todos os quadros para a mesma altura exata
                while len(lines) < self.canvas_height:
                    lines.append("")
                
                frame_buffer = ""
                for i, line in enumerate(lines):
                    clean_line = line.rstrip()
                    # Blindagem de largura (margem maior para segurança)
                    safe_line = clean_line[:term_width - 15]
                    
                    prefix = f"\x1b[90m{i+1:02} |\x1b[0m " if self.debug else ""
                    
                    # \r (Home) + Cor + Conteúdo + \x1b[K (Limpa rastro)
                    frame_buffer += f"\r{prefix}{self.base_color}{safe_line}\x1b[0m\x1b[K"
                    
                    # Adiciona nova linha exceto na última do canvas (Proteção de Stacking)
                    if i < self.canvas_height - 1:
                        frame_buffer += "\n"
                
                self.atomic_frames.append(frame_buffer)

    def _animate(self):
        if hasattr(sys, '_doxoade_current_tracer'):
            sys.settrace(sys._doxoade_current_tracer)

        # Esconde o cursor
        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()
        
        idx = 0
        step = 1
        count = len(self.atomic_frames)
        is_first_draw = True
        
        # Pre-calcula o comando de subida (Altura - 1)
        # Usamos \x1b[A porque é o mais compatível universalmente
        up_cmd = f"\x1b[{self.canvas_height - 1}A" if self.canvas_height > 1 else ""

        while self.running.is_set():
            frame_data = self.atomic_frames[idx]
            t_start = time.perf_counter()
            
            try:
                with self.lock:
                    # REPOSICIONAMENTO NEXUS
                    if not is_first_draw and not self._force_redraw:
                        sys.stdout.write(up_cmd)
                    
                    # Escrita Atômica
                    sys.stdout.write(frame_data)
                    sys.stdout.flush()
                    
                    is_first_draw = False
                    self._force_redraw = False
            except:
                break
            
            # Lógica Ping-Pong
            if self.ping_pong and count > 1:
                idx += step
                if idx >= count - 1 or idx <= 0: step *= -1
            else:
                idx = (idx + 1) % count
            
            # Velocidade Dinâmica (usa self.interval atualizado)
            t_elapsed = time.perf_counter() - t_start
            time.sleep(max(0, self.interval - t_elapsed))

        self._cleanup_display()

    def _cleanup_display(self):
        """Faxina total via subida relativa."""
        with self.lock:
            try:
                if self.canvas_height > 0:
                    # Volta ao topo do canvas
                    sys.stdout.write(f"\r\x1b[{self.canvas_height - 1}A")
                    # Limpa todas as linhas
                    for i in range(self.canvas_height):
                        sys.stdout.write("\x1b[2K")
                        if i < self.canvas_height - 1:
                            sys.stdout.write("\n")
                    # Deixa o cursor no topo limpo
                    sys.stdout.write(f"\r\x1b[{self.canvas_height - 1}A")
                sys.stdout.write("\x1b[?25h") # Mostra cursor
                sys.stdout.flush()
            except: pass

    def start(self):
        if not self.atomic_frames: return
        self.running.set()
        # Thread não-daemon para permitir cleanup no join
        self._thread = threading.Thread(target=self._animate)
        self._thread.start()

    def stop(self):
        if self.running.is_set():
            self.running.clear()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)

    def print(self, text):
        """Injeta log movendo a animação."""
        from .doxcolors import NexusUI
        formatted = NexusUI.apply_tags(text)
        with self.lock:
            if self.canvas_height > 0:
                sys.stdout.write(f"\r\x1b[{self.canvas_height - 1}A")
                for _ in range(self.canvas_height):
                    sys.stdout.write("\x1b[2K\x1b[B")
                sys.stdout.write(f"\r\x1b[{self.canvas_height}A")
            sys.stdout.write(f"{formatted}\n")
            sys.stdout.flush()
            self._force_redraw = True

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

# --- OVERRIDES ---

_original_print = builtins.print
def safe_print(*args, **kwargs):
    _original_print(*args, **kwargs)
    if ANSI_ENABLED: _original_print('\x1b[0m', end='')
builtins.print = safe_print

# --- EXPORTS ---
class DoxColors:
    Fore = Fore; Back = Back; Style = Style; UI = NexusUI
    rgb = staticmethod(rgb); hex = staticmethod(hex_to_ansi)
    AsyncAnimation = AsyncAnimation
colors = DoxColors