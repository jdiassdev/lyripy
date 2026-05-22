import os
import re
import time
import msvcrt
import ctypes
import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.prompt import Prompt

console = Console()
PASTA_LYRICS = "lyrics"

if not os.path.exists(PASTA_LYRICS):
    os.makedirs(PASTA_LYRICS)


# ── Audio (Windows MCI via ctypes — sem dependências extras) ──────────────────

_winmm = ctypes.windll.winmm
_MCI_ALIAS = "lyripy"


def _mci(cmd: str) -> str:
    buf = ctypes.create_unicode_buffer(512)
    _winmm.mciSendStringW(cmd, buf, 512, 0)
    return buf.value


class AudioPlayer:
    def __init__(self, path: str):
        _mci(f'open "{path}" alias {_MCI_ALIAS}')
        _mci(f'set {_MCI_ALIAS} time format milliseconds')

    @property
    def pos(self) -> float:
        result = _mci(f'status {_MCI_ALIAS} position')
        return int(result) / 1000.0 if result.strip() else 0.0

    def play(self):   _mci(f'play {_MCI_ALIAS}')
    def pause(self):  _mci(f'pause {_MCI_ALIAS}')
    def resume(self): _mci(f'resume {_MCI_ALIAS}')
    def close(self):  _mci(f'close {_MCI_ALIAS}')


# ── Teclado não-bloqueante ─────────────────────────────────────────────────────

def _tecla():
    if msvcrt.kbhit():
        ch = msvcrt.getch()
        if ch == b'\xe0':   # tecla especial (seta, F-key) — descarta
            msvcrt.getch()
            return None
        return ch
    return None


# ── Busca online ───────────────────────────────────────────────────────────────

def buscar_online():
    console.clear()
    console.print(Panel("[bold cyan]BUSCAR MÚSICAS[/]", border_style="cyan"))

    termo = Prompt.ask("\nArtista ou música").strip()
    if not termo:
        console.print("[red]Digite algo para buscar.[/]")
        time.sleep(2)
        return

    try:
        with console.status("[cyan]Procurando...[/]"):
            r = requests.get("https://lrclib.net/api/search",
                             params={"q": termo}, timeout=10)

        if r.status_code != 200:
            console.print(f"[red]Erro na API: {r.status_code}[/]")
            time.sleep(2)
            return

        resultados = r.json()[:20]
        if not resultados:
            console.print(f"[red]Nenhum resultado para '{termo}'.[/]")
            time.sleep(2)
            return

        console.clear()
        table = Table(border_style="dim", header_style="bold cyan", show_lines=False)
        table.add_column("#", style="magenta bold", width=3, justify="right")
        table.add_column("Música", style="bold white")
        table.add_column("Artista", style="dim white")
        table.add_column("LRC", width=5, justify="center")

        for i, res in enumerate(resultados, 1):
            badge = "[green]sim[/]" if res.get("syncedLyrics") else "[red]nao[/]"
            table.add_row(str(i), res.get("trackName", "?"),
                          res.get("artistName", "?"), badge)

        console.print(Panel(table, title="[bold cyan]SELECIONE A MÚSICA[/]",
                            border_style="cyan"))
        console.print("[dim]0 — Voltar[/]")

        escolha = Prompt.ask("\nNúmero")
        if not escolha.isdigit() or escolha == "0":
            return

        idx = int(escolha) - 1
        if not (0 <= idx < len(resultados)):
            console.print("[red]Opção fora da lista.[/]")
            time.sleep(1.5)
            return

        selecionada = resultados[idx]
        lrc = selecionada.get("syncedLyrics")
        if not lrc:
            console.print("\n[red]Esta música não tem letra sincronizada.[/]")
            time.sleep(2)
            return

        nome = selecionada.get("trackName", "musica")
        nome_sanitizado = re.sub(r'[\\/*?:"<>|]', "", nome)
        caminho = os.path.join(PASTA_LYRICS, f"{nome_sanitizado}.lrc")

        with open(caminho, "w", encoding="utf-8") as f:
            f.write(lrc)

        console.print(f"\n[green]Salvo:[/] {caminho}")
        time.sleep(1)
        iniciar_karaoke(lrc, nome)

    except Exception as e:
        console.print(f"[red]Erro ao conectar: {e}[/]")
        time.sleep(2)


# ── Lista local ────────────────────────────────────────────────────────────────

def listar_locais():
    console.clear()
    arquivos = [f for f in os.listdir(PASTA_LYRICS) if f.endswith(".lrc")]

    if not arquivos:
        console.print(Panel(f"[red]A pasta '{PASTA_LYRICS}' está vazia.[/]",
                            border_style="red"))
        time.sleep(2)
        return

    table = Table(border_style="dim", header_style="bold cyan", show_lines=False)
    table.add_column("#", style="magenta bold", width=3, justify="right")
    table.add_column("Arquivo", style="bold white")

    for i, arq in enumerate(arquivos, 1):
        table.add_row(str(i), arq)

    console.print(Panel(table, title="[bold cyan]MÚSICAS SALVAS[/]", border_style="cyan"))
    console.print("[dim]0 — Voltar[/]")

    try:
        escolha = int(Prompt.ask("\nNúmero"))
        if escolha == 0:
            return
        arquivo = arquivos[escolha - 1]
        with open(os.path.join(PASTA_LYRICS, arquivo), "r", encoding="utf-8") as f:
            iniciar_karaoke(f.read(), arquivo)
    except (ValueError, IndexError):
        console.print("[red]Opção inválida.[/]")
        time.sleep(1.5)


# ── Karaokê ────────────────────────────────────────────────────────────────────

def parsear(texto):
    pat = re.compile(r"\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)")
    linhas = []
    for m in pat.finditer(texto):
        seg = int(m[1]) * 60 + int(m[2]) + int(m[3]) / 100
        linhas.append((seg, m[4].strip()))
    return sorted(linhas)


def build_view(linhas, i, titulo, pausado=False, offset=0.0):
    text = Text(justify="left")

    for idx in range(max(0, i - 4), i):
        linha = linhas[idx][1]
        text.append(f"    {linha}\n" if linha else "\n", style="dim")

    atual = linhas[i][1]
    text.append(f"  > {atual}\n" if atual else "\n", style="bold magenta")

    for idx in range(i + 1, min(i + 4, len(linhas))):
        proxima = linhas[idx][1]
        text.append(f"    {proxima}\n" if proxima else "\n", style="bright_black")

    status = []
    if pausado:
        status.append("[yellow]PAUSADO[/]")
    if abs(offset) > 0.01:
        sinal = "+" if offset > 0 else ""
        status.append(f"[dim]offset {sinal}{offset:.1f}s[/]")

    return Panel(
        text,
        title=f"[cyan]{titulo}[/]",
        subtitle="  ".join(status) if status else None,
        border_style="yellow" if pausado else "magenta",
        padding=(1, 4)
    )


def iniciar_karaoke(conteudo_lrc, titulo):
    linhas = parsear(conteudo_lrc)

    console.clear()
    console.print(Panel(
        f"[bold]{titulo}[/]\n\n"
        "[dim]Arquivo de áudio para tocar junto?[/]\n"
        "[dim]Suporta MP3, WAV, WMA  —  Enter para pular[/]",
        border_style="cyan", padding=(1, 4)
    ))
    audio_path = Prompt.ask("  Caminho", default="").strip().strip('"')

    if audio_path and os.path.isfile(audio_path):
        _karaoke_com_audio(linhas, titulo, audio_path)
    else:
        _karaoke_manual(linhas, titulo)


def _karaoke_com_audio(linhas, titulo, audio_path):
    try:
        player = AudioPlayer(audio_path)
    except Exception as e:
        console.print(f"[red]Erro ao carregar áudio: {e}[/]")
        time.sleep(2)
        _karaoke_manual(linhas, titulo)
        return

    console.clear()
    console.print(Panel(
        f"[bold]{titulo}[/]\n\n[dim]Space: pausar  |  + / -: ajustar sincronia[/]",
        border_style="cyan", padding=(1, 4)
    ))
    input("\n  >>> Pressione ENTER para iniciar <<<  \n")

    player.play()
    offset = 0.0
    pausado = False
    current = -1

    try:
        with Live(console=console, refresh_per_second=30, screen=True) as live:
            while current < len(linhas) - 1:
                key = _tecla()
                if key == b' ':
                    pausado = not pausado
                    player.pause() if pausado else player.resume()
                elif key in (b'+', b'='):
                    offset += 0.5
                elif key == b'-':
                    offset -= 0.5

                if not pausado:
                    pos = player.pos + offset
                    while current + 1 < len(linhas) and pos >= linhas[current + 1][0]:
                        current += 1

                if current >= 0:
                    live.update(build_view(linhas, current, titulo, pausado, offset))

                time.sleep(0.01)

        player.close()
    except KeyboardInterrupt:
        player.close()

    console.print("\n[green]Fim da música![/]")
    time.sleep(2)


def _karaoke_manual(linhas, titulo):
    console.clear()
    console.print(Panel(
        f"[bold]{titulo}[/]\n\n[dim]Dê o play no seu player externo...[/]\n"
        "[dim]Space: pausar  |  + / -: ajustar sincronia[/]",
        border_style="cyan", padding=(1, 4)
    ))
    input("\n  >>> Pressione ENTER para sincronizar <<<  \n")

    inicio = time.time()
    tempo_pausado = 0.0
    pausa_inicio = 0.0
    offset = 0.0
    pausado = False
    current = -1

    try:
        with Live(console=console, refresh_per_second=30, screen=True) as live:
            while current < len(linhas) - 1:
                key = _tecla()
                if key == b' ':
                    if pausado:
                        tempo_pausado += time.time() - pausa_inicio
                        pausado = False
                    else:
                        pausa_inicio = time.time()
                        pausado = True
                elif key in (b'+', b'='):
                    offset += 0.5
                elif key == b'-':
                    offset -= 0.5

                if not pausado:
                    elapsed = time.time() - inicio - tempo_pausado + offset
                    while current + 1 < len(linhas) and elapsed >= linhas[current + 1][0]:
                        current += 1

                if current >= 0:
                    live.update(build_view(linhas, current, titulo, pausado, offset))

                time.sleep(0.01)
    except KeyboardInterrupt:
        pass

    console.print("\n[green]Fim da música![/]")
    time.sleep(2)


# ── Menu principal ─────────────────────────────────────────────────────────────

MENU = Panel("""
  [magenta bold]1.[/]  Buscar nova música  [dim](Online)[/]
  [yellow bold]2.[/]  Músicas salvas       [dim](Local)[/]
  [dim]3.[/]  Sair
""", title="[bold cyan]TERMINAL KARAOKE[/]", border_style="cyan", padding=(0, 4))

while True:
    console.clear()
    console.print(MENU)

    opc = Prompt.ask("[bold]Opção[/]", choices=["1", "2", "3"], show_choices=False)

    if opc == "1":
        buscar_online()
    elif opc == "2":
        listar_locais()
    elif opc == "3":
        console.print("\n[cyan]Até a próxima![/]")
        break
