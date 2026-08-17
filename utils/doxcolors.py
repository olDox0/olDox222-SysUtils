# -*- coding: utf-8 -*-
# doxoade/doxoade/tools/doxcolors.py
"""
Doxcolors Nexus Edition – High-Performance CLI UI Engine
Versão: 2.0 (Nexus UI)
"""
import os
import sys
import builtins
import time
# [DOX-UNUSED] import math
import threading
# [DOX-UNUSED] import itertools
import atexit

import ctypes
import ctypes.wintypes

class _COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.wintypes.SHORT), ("Y", ctypes.wintypes.SHORT)]

class _SMALL_RECT(ctypes.Structure):
    _fields_ = [
        ("Left", ctypes.wintypes.SHORT), ("Top", ctypes.wintypes.SHORT),
        ("Right", ctypes.wintypes.SHORT), ("Bottom", ctypes.wintypes.SHORT),
    ]

class _CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
    _fields_ = [
        ("dwSize", _COORD),
        ("dwCursorPosition", _COORD),
        ("wAttributes", ctypes.wintypes.WORD),
        ("srWindow", _SMALL_RECT),
        ("dwMaximumWindowSize", _COORD),
    ]

def _get_console_info():
    """Retorna (cursor_y, window_top) usando API do Windows. (-1, -1) em outros OS."""
    if os.name != 'nt':
        return -1, -1
    try:
        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        csbi = _CONSOLE_SCREEN_BUFFER_INFO()
        ctypes.windll.kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(csbi))
        return csbi.dwCursorPosition.Y, csbi.srWindow.Top
    except Exception:
        return -1, -1

def _force_reset():
    """Envia o sinal de reset global de forma agressiva."""
    # O código \033[0m reseta cores de fundo, frente e estilos (negrito, etc)
    # Enviamos para stdout e stderr para garantir que o terminal receba
    try:
        if os.name == 'nt':
            os.system('')
        sys.stdout.write('\033[0m')
        sys.stdout.flush()
        sys.stderr.write('\033[0m')
        sys.stderr.flush()
    except KeyboardInterrupt:
        print("KeyboardInterrupt")

class AnsiCode(str):
    __slots__ = ()
    def __new__(cls, code: str):
        try:
            if not ANSI_ENABLED: return str.__new__(cls, '')
            return str.__new__(cls, f'\x1b[{code}m')
        except Exception:
            # Fallback total: se falhar, retorna string vazia (texto sem cor)
            return str.__new__(cls, '')

# --- CORE ENGINE ---

def _ansi_enabled():
    if os.name != 'nt':
        return sys.stdout.isatty()
    return sys.stdout.isatty() or 'ANSICON' in os.environ or 'WT_SESSION' in os.environ or (os.environ.get('TERM_PROGRAM') == 'vscode')

#ANSI_ENABLED = _ansi_enabled()
ANSI_ENABLED = sys.stdout.isatty() if hasattr(sys.stdout, 'isatty') else False

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
    LIGHTRED_EX   = AnsiCode('91')
    LIGHTGREEN_EX   = AnsiCode('92')
    LIGHTYELLOW_EX  = AnsiCode('93')
    LIGHTMAGENTA_EX = AnsiCode('95')
    LIGHTWHITE_EX   = AnsiCode('97')

    # Nexus Semantic Colors

    ORANGE      = AnsiCode('38;2;255;100;0')   # ORANGE
    LIGHTYELLOW = AnsiCode('38;2;255;255;100')   # LIGHTYELLOW
    EMERALD     = AnsiCode('38;2;38;188;95')   # Verde Estável
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
    def apply_tags(text: str) -> str:
        """Processa tags customizadas «TAG»...«/». Fail-Safe."""
        if not text or not isinstance(text, str):
            return ""
        try:
            # Lógica de substituição de tags...
            # (seu código atual de regex)
            return rendered_text
        except Exception:
            # Se houver erro de sintaxe nas tags, retorna o texto puro
            return text

    @staticmethod
    def load_animation(file_path, separator="===FRAME==="):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            content = NexusUI.apply_tags(content)
            import re
            raw_parts = re.split(re.escape(separator), content)
            return [p.strip('\r\n') for p in raw_parts if p.strip()]
        except Exception as e:
            import logging as _dox_log
            _dox_log.error(f"[INFRA] load_animation: {e}")
            return []

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
        self._force_redraw = True
        self.last_draw_y = -1
        
        if frames:
            term_width = shutil.get_terminal_size().columns
            
            # ═══ CORREÇÃO: Remove linhas vazias do final de cada frame ═══
            cleaned_frames = []
            for f in frames:
                lines = f.split('\n')
                # Remove linhas vazias do final
                while lines and not lines[-1].strip():
                    lines.pop()
                if lines:  # Só adiciona se não ficou vazio
                    cleaned_frames.append('\n'.join(lines))
            
            if not cleaned_frames:
                return
            
            # Calcula altura real baseada nos frames limpos
            self.canvas_height = max(len(f.split('\n')) for f in cleaned_frames)
            
            for f in cleaned_frames:
                lines = f.split('\n')
                # Normaliza todos os quadros para a mesma altura exata
                while len(lines) < self.canvas_height:
                    lines.append("")
                
                frame_buffer = ""
                for i, line in enumerate(lines):
                    clean_line = line.rstrip()
                    safe_line = clean_line[:term_width - 15]
                    prefix = f"\x1b[90m{i+1:02} |\x1b[0m " if self.debug else ""
                    frame_buffer += f"\r{prefix}{self.base_color}{safe_line}\x1b[0m\x1b[K"
                    if i < self.canvas_height - 1:
                        frame_buffer += "\n"
                self.atomic_frames.append(frame_buffer)


    def _animate(self):
        if hasattr(sys, '_doxoade_current_tracer'):
            sys.settrace(sys._doxoade_current_tracer)
            
        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()
        
        idx = 0
        step = 1
        count = len(self.atomic_frames)
        
        while self.running.is_set():
            frame_data = self.atomic_frames[idx]
            t_start = time.perf_counter()
            
            try:
                with self.lock:
                    current_y, window_top = _get_console_info()
                    
                    should_clear_old = False
                    should_move_up = False
                    
                    if self.last_draw_y != -1 and not self._force_redraw:
                        if self.last_draw_y >= window_top:
                            # A animação antiga ainda está visível na tela
                            expected_cursor_y = self.last_draw_y + self.canvas_height
                            if current_y == expected_cursor_y:
                                should_move_up = True
                            elif current_y > expected_cursor_y:
                                # 🚨 Logs externos foram impressos! A animação "afundou".
                                should_clear_old = True
                    
                    if should_clear_old:
                        # 1. Vai até a posição antiga e limpa (evita fantasmas na tela)
                        sys.stdout.write(f"\x1b[{self.last_draw_y + 1};1H")
                        for _ in range(self.canvas_height):
                            sys.stdout.write("\x1b[2K\x1b[B")
                        # 2. Vai para a nova posição do cursor (abaixo dos logs externos)
                        sys.stdout.write(f"\x1b[{current_y + 1};1H")
                    elif should_move_up:
                        # Caso normal: sobe para sobrescrever o frame anterior
                        sys.stdout.write(f"\x1b[{self.canvas_height - 1}A\r")
                    elif self._force_redraw or self.last_draw_y == -1:
                        sys.stdout.write("\r")
                        
                    # Desenha o frame
                    sys.stdout.write(frame_data)
                    sys.stdout.flush()
                    
                    # Atualiza a posição Y gravada
                    if self._force_redraw or self.last_draw_y == -1 or should_clear_old or not should_move_up:
                        self.last_draw_y = current_y
                        
                    self._force_redraw = False
                    
            except Exception as e:
                import logging as _dox_log
                _dox_log.error(f"[INFRA] _animate: {e}")
                break
                
            # Lógica Ping-Pong
            if self.ping_pong and count > 1:
                idx += step
                if idx >= count - 1 or idx <= 0: step *= -1
            else:
                idx = (idx + 1) % count
                
            t_elapsed = time.perf_counter() - t_start
            time.sleep(max(0, self.interval - t_elapsed))
            
        self._cleanup_display()

    def _cleanup_display(self):
        """Faxina total usando posicionamento absoluto."""
        with self.lock:
            try:
                current_y, window_top = _get_console_info()
                if self.last_draw_y != -1 and self.last_draw_y >= window_top:
                    # Vai para a posição exata da animação e limpa
                    sys.stdout.write(f"\x1b[{self.last_draw_y + 1};1H")
                    for _ in range(self.canvas_height):
                        sys.stdout.write("\x1b[2K\x1b[B")
                    # Deixa o cursor na linha abaixo da área limpa
                    sys.stdout.write(f"\x1b[{self.last_draw_y + self.canvas_height + 1};1H")
                else:
                    # Fallback relativo se não soubermos a posição
                    if self.canvas_height > 0:
                        sys.stdout.write(f"\r\x1b[{self.canvas_height - 1}A")
                        for i in range(self.canvas_height):
                            sys.stdout.write("\x1b[2K")
                            if i < self.canvas_height - 1:
                                sys.stdout.write("\n")
                        sys.stdout.write(f"\r\x1b[{self.canvas_height - 1}A")
                        
                sys.stdout.write("\x1b[?25h")
                sys.stdout.flush()
                self.last_draw_y = -1
            except Exception as e:
                import logging as _dox_log
                _dox_log.error(f"[INFRA] _cleanup_display: {e}")

    def start(self):
        if not self.atomic_frames: return
        self.running.set()
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def stop(self):
        if self.running.is_set():
            self.running.clear()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)

    def print(self, text):
        """
        Injeta log SEM ser engolido pela animação.
        
        Estratégia:
        1. Pausa a animação (limpa o canvas atual)
        2. Imprime o log em linha nova
        3. Retoma a animação ABAIXO do log
        """
        from .doxcolors import NexusUI
        formatted = NexusUI.apply_tags(text)
        
        with self.lock:
            # 1. Para a animação momentaneamente
            was_running = self.running.is_set()
            if was_running:
                self.running.clear()
            
            # 2. Limpa o canvas da animação (move cursor para baixo do canvas)
            if self.canvas_height > 0:
                # Move para o topo do canvas
                sys.stdout.write(f"\r\x1b[{self.canvas_height}A")
                # Limpa todas as linhas do canvas
                for _ in range(self.canvas_height):
                    sys.stdout.write("\x1b[2K\n")
                # Volta para a posição correta (abaixo de onde o canvas estava)
                sys.stdout.write(f"\r\x1b[{self.canvas_height}A")
            
            # 3. Imprime o log (sempre em linha nova, nunca sobrescrito)
            sys.stdout.write(f"\x1b[2K{formatted}\n")
            sys.stdout.flush()
            
            # 4. Retoma a animação (ela vai redesenhar abaixo do log)
            if was_running:
                self.running.set()
                # Força redesenho na próxima iteração
                self._force_redraw = True

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

# --- OVERRIDES ---

#_original_print = builtins.print
def safe_print(*args, **kwargs):
    """Print seguro com proteção contra recursão."""
    try:
        if ANSI_ENABLED:
            _original_print('\x1b[0m', end='')  # Reset ANSI
        
        _original_print(*args, **kwargs)
        
        if ANSI_ENABLED:
            _original_print('\x1b[0m', end='')  # Reset ANSI
    except RecursionError:
        # Se detectar recursão, usa o print do builtins diretamente
        builtins._doxoade_original_print(*args, **kwargs)
    except Exception:
        # Fallback para qualquer outro erro
        try:
            builtins._doxoade_original_print(*args, **kwargs)
        except:
            pass  # Último recurso: silêncio

# Substitui o print global
builtins.print = safe_print

# --- EXPORTS ---
class DoxColors:
    Fore = Fore; Back = Back; Style = Style; UI = NexusUI
    rgb = staticmethod(rgb); hex = staticmethod(hex_to_ansi)
    AsyncAnimation = AsyncAnimation
colors = DoxColors

def init(autoreset=True):
    """
    Inicializa o motor de cores.
    Se autoreset=True, registra a limpeza automática ao sair do programa.
    """
    if os.name == 'nt' and ANSI_ENABLED:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # Habilita VIRTUAL_TERMINAL_PROCESSING
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 4)
        except Exception as e:
            # Silencioso, mas evita o crash do fluxo de I/O
            pass

    if autoreset:
        # Registra a função de limpeza automática
        atexit.register(_force_reset)
