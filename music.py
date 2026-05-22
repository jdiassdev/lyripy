import os
import re
import time
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


def buscar_online():
    console.clear()
    console.print(Panel("[bold cyan]BUSCAR MÚSICAS[/]", border_style="cyan"))

    termo = Prompt.ask("\nArtista ou música").strip()
    if not termo:
        console.print("[red]Digite algo para buscar.[/]")
        time.sleep(2)
        return

    try:
        with console.status("[cyan]Procurando no servidor...[/]"):
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
            lrc_badge = "[green]✓[/]" if res.get("syncedLyrics") else "[red]✗[/]"
            table.add_row(str(i), res.get("trackName", "?"),
                          res.get("artistName", "?"), lrc_badge)

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

        console.print(f"\n[green]✓ Salvo:[/] {caminho}")
        time.sleep(1)
        iniciar_karaoke(lrc, nome)

    except Exception as e:
        console.print(f"[red]Erro ao conectar: {e}[/]")
        time.sleep(2)


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


def parsear(texto):
    pat = re.compile(r"\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)")
    linhas = []
    for m in pat.finditer(texto):
        seg = int(m[1]) * 60 + int(m[2]) + int(m[3]) / 100
        linhas.append((seg, m[4].strip()))
    return sorted(linhas)


def build_view(linhas, i, titulo):
    text = Text(justify="left")

    # Histórico: 4 linhas anteriores
    for idx in range(max(0, i - 4), i):
        linha = linhas[idx][1]
        text.append(f"    {linha}\n" if linha else "\n", style="dim")

    # Linha atual
    atual = linhas[i][1]
    text.append(f"  ► {atual}\n" if atual else "\n", style="bold magenta")

    # Próximas: 3 linhas à frente
    for idx in range(i + 1, min(i + 4, len(linhas))):
        proxima = linhas[idx][1]
        text.append(f"    {proxima}\n" if proxima else "\n", style="bright_black")

    return Panel(text, title=f"[cyan]{titulo}[/]",
                 border_style="magenta", padding=(1, 4))


def iniciar_karaoke(conteudo_lrc, titulo):
    linhas = parsear(conteudo_lrc)
    console.clear()
    console.print(Panel(
        f"[bold]{titulo}[/]\n\n[dim]Dê o play no seu player externo...[/]",
        border_style="cyan", padding=(1, 4)
    ))
    input("\n  >>> Pressione ENTER para sincronizar <<<  \n")

    inicio = time.time()
    try:
        with Live(console=console, refresh_per_second=30, screen=True) as live:
            for i, (ts, _) in enumerate(linhas):
                while (time.time() - inicio) < ts:
                    time.sleep(0.01)
                live.update(build_view(linhas, i, titulo))

        console.print("\n[green]Fim da música![/]")
        time.sleep(2)
    except KeyboardInterrupt:
        console.print("\n[red]Interrompido.[/]")
        time.sleep(1)


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
