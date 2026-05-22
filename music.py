import os
import re
import glob
import time
import msvcrt
import subprocess
import tempfile
import requests
from urllib.parse import quote
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.prompt import Prompt, Confirm

try:
    import yt_dlp
    HAS_YT_DLP = True
except ImportError:
    HAS_YT_DLP = False

console = Console()
PASTA_LYRICS = "lyrics"
PASTA_AUDIO  = "audio"

for pasta in (PASTA_LYRICS, PASTA_AUDIO):
    if not os.path.exists(pasta):
        os.makedirs(pasta)


# ── Audio (PowerShell + Windows Media Foundation) ─────────────────────────────
# Funciona com qualquer formato que o Windows reconheça (m4a, mp3, wav, etc.)
# Sem dependências extras — PowerShell está em todo Windows 10/11.

def _ps_script_para(abs_path: str) -> str:
    uri = "file:///" + quote(abs_path.replace("\\", "/"), safe="/:@")
    return f"""
Add-Type -AssemblyName PresentationCore
$mp = New-Object System.Windows.Media.MediaPlayer
$mp.Open([System.Uri]::new("{uri}"))
Start-Sleep -Milliseconds 1200
while ($true) {{
    $cmd = [Console]::In.ReadLine()
    if     ($cmd -eq 'play') {{ $mp.Play() }}
    elseif ($cmd -eq 'pos')  {{ [Console]::WriteLine($mp.Position.TotalSeconds); [Console]::Out.Flush() }}
    elseif ($cmd -eq 'p')    {{ $mp.Pause() }}
    elseif ($cmd -eq 'r')    {{ $mp.Play()  }}
    elseif ($cmd -eq 'q')    {{ $mp.Close(); break }}
}}
"""


class AudioPlayer:
    def __init__(self, path: str):
        script = _ps_script_para(os.path.abspath(path))
        self._tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".ps1", delete=False, encoding="utf-8"
        )
        self._tmp.write(script)
        self._tmp.close()

        self._proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-File", self._tmp.name],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        time.sleep(1.8)  # aguarda o arquivo carregar (sem tocar ainda)

    def _send(self, cmd: str):
        try:
            self._proc.stdin.write(cmd + "\n")
            self._proc.stdin.flush()
        except OSError:
            pass

    @property
    def pos(self) -> float:
        self._send("pos")
        try:
            return float(self._proc.stdout.readline().strip().replace(",", "."))
        except (ValueError, OSError):
            return 0.0

    def play(self):   self._send("play")
    def pause(self):  self._send("p")
    def resume(self): self._send("r")

    def close(self):
        self._send("q")
        self._proc.wait(timeout=3)
        os.unlink(self._tmp.name)


# ── YouTube download ───────────────────────────────────────────────────────────

def baixar_audio(query: str, nome_sanitizado: str) -> str | None:
    base = os.path.join(PASTA_AUDIO, nome_sanitizado)
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio",
        "outtmpl": base + ".%(ext)s",
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"ytsearch1:{query}"])
        arquivos = glob.glob(base + ".*")
        return arquivos[0] if arquivos else None
    except Exception:
        return None


def _buscar_audio_local(nome_sanitizado: str) -> str | None:
    for ext in (".mp3", ".m4a", ".wav", ".wma", ".ogg"):
        path = os.path.join(PASTA_AUDIO, nome_sanitizado + ext)
        if os.path.isfile(path):
            return path
    return None


# ── Teclado não-bloqueante ─────────────────────────────────────────────────────

def _tecla():
    if msvcrt.kbhit():
        ch = msvcrt.getch()
        if ch == b'\xe0':
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

        nome       = selecionada.get("trackName", "musica")
        artista    = selecionada.get("artistName", "")
        nome_san   = re.sub(r'[\\/*?:"<>|]', "", nome)

        with open(os.path.join(PASTA_LYRICS, f"{nome_san}.lrc"), "w", encoding="utf-8") as f:
            f.write(lrc)

        console.print(f"\n[green]Letra salva.[/]")

        # ── oferecer download de áudio ────────────────────────────────────────
        audio_path = None
        if HAS_YT_DLP:
            if Confirm.ask("\nBaixar áudio do YouTube?", default=True):
                query = f"{artista} {nome}".strip()
                with console.status(f"[cyan]Baixando '{nome}'...[/]"):
                    audio_path = baixar_audio(query, nome_san)

                if audio_path:
                    console.print(f"[green]Áudio salvo:[/] {audio_path}")
                    time.sleep(1)
                else:
                    console.print("[red]Falha no download. Continuando sem áudio.[/]")
                    time.sleep(2)

        iniciar_karaoke(lrc, nome, audio_path=audio_path)

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
    table.add_column("Audio", width=6, justify="center")

    for i, arq in enumerate(arquivos, 1):
        nome_san = os.path.splitext(arq)[0]
        tem_audio = "[green]sim[/]" if _buscar_audio_local(nome_san) else "[dim]nao[/]"
        table.add_row(str(i), arq, tem_audio)

    console.print(Panel(table, title="[bold cyan]MÚSICAS SALVAS[/]", border_style="cyan"))
    console.print("[dim]0 — Voltar[/]")

    try:
        escolha = int(Prompt.ask("\nNúmero"))
        if escolha == 0:
            return
        arquivo  = arquivos[escolha - 1]
        nome_san = os.path.splitext(arquivo)[0]
        audio_path = _buscar_audio_local(nome_san)
        with open(os.path.join(PASTA_LYRICS, arquivo), "r", encoding="utf-8") as f:
            iniciar_karaoke(f.read(), arquivo, audio_path=audio_path)
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


def iniciar_karaoke(conteudo_lrc, titulo, audio_path=None):
    linhas = parsear(conteudo_lrc)

    if audio_path and os.path.isfile(audio_path):
        _karaoke_com_audio(linhas, titulo, audio_path)
        return

    # sem áudio pré-definido: perguntar
    console.clear()
    console.print(Panel(
        f"[bold]{titulo}[/]\n\n"
        "[dim]Arquivo de áudio para tocar junto?[/]\n"
        "[dim]Suporta MP3, WAV, WMA  —  Enter para pular[/]",
        border_style="cyan", padding=(1, 4)
    ))
    caminho = Prompt.ask("  Caminho", default="").strip().strip('"')

    if caminho and os.path.isfile(caminho):
        _karaoke_com_audio(linhas, titulo, caminho)
    else:
        _karaoke_manual(linhas, titulo)


def _karaoke_com_audio(linhas, titulo, audio_path):
    try:
        player = AudioPlayer(audio_path)
    except Exception as e:
        console.print(f"[red]Erro ao iniciar áudio: {e}[/]")
        time.sleep(2)
        _karaoke_manual(linhas, titulo)
        return

    console.clear()
    console.print(Panel(
        f"[bold]{titulo}[/]\n\n[dim]Space: pausar  |  + / -: ajustar sincronia[/]",
        border_style="cyan", padding=(1, 4)
    ))
    input("\n  >>> Pressione ENTER para iniciar <<<  \n")
    player.play()  # áudio e loop partem juntos

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


def _karaoke_manual(linhas, titulo, aviso: str = "Dê o play no seu player externo..."):
    console.clear()
    console.print(Panel(
        f"[bold]{titulo}[/]\n\n[dim]{aviso}[/]\n"
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
