import os
import re
import time
import requests

# Configurações de Cores
Y = "\033[93m"
P = "\033[95m"      # Linha atual / Opções (Roxo)
D = "\033[37;2m"    # Texto Antigo / escuro
G = "\033[92m"      # Verde / sucesso
CYAN = "\033[96m"   # Menu / info
RED = "\033[91m"    # Erro
BOLD = "\033[1m"
R = "\033[0m"       # Reset

# --- CONFIGURAÇÃO DE PASTA ---
PASTA_LYRICS = "lyrics"

if not os.path.exists(PASTA_LYRICS):
    os.makedirs(PASTA_LYRICS)
# -----------------------------


def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')


def buscar_online():
    limpar_tela()
    print(f"{CYAN}--- BUSCAR MÚSICAS ---{R}\n")
    termo_busca = input("Digite o Artista ou Música: ").strip()

    if not termo_busca:
        print(f"{RED}Por favor, digite algo para buscar.{R}")
        time.sleep(2)
        return

    print(f"\n{CYAN}Procurando no servidor...{R}")
    try:
        # Usamos o parâmetro 'q' que é uma busca geral (mais chance de achar)
        r = requests.get("https://lrclib.net/api/search",
                         params={"q": termo_busca}, timeout=10)

        if r.status_code == 200:
            resultados = r.json()

            # Filtramos para mostrar apenas as que possuem letra (opcional, mas melhor para o karaokê)
            # Pegamos os primeiros 5 resultados
            opcoes = resultados[:5]

            if not opcoes:
                print(f"{RED}Nenhum resultado encontrado para '{termo_busca}'.{R}")
                time.sleep(2)
                return

            limpar_tela()
            print(f"{CYAN}--- SELECIONE A MÚSICA ---{R}\n")
            for i, res in enumerate(opcoes, 1):
                artista = res.get("artistName", "Desconhecido")
                track = res.get("trackName", "Sem título")
                # Verifica se tem a letra sincronizada (syncedLyrics)
                status = f"{G}[LRC]{R}" if res.get(
                    "syncedLyrics") else f"{RED}[Sem Sincronia]{R}"

                print(f"{P}{i}{R} - {BOLD}{track}{R} | {artista} {status}")

            print(f"\n{P}0{R} - Voltar")

            escolha = input(f"\n{BOLD}Escolha o número: {R}")
            if escolha == '0' or not escolha.isdigit():
                return

            idx = int(escolha) - 1
            if 0 <= idx < len(opcoes):
                selecionada = opcoes[idx]
                lrc = selecionada.get("syncedLyrics")

                if not lrc:
                    print(
                        f"\n{RED}Aviso: Esta música não possui letra sincronizada para o Karaokê.{R}")
                    time.sleep(2)
                    return

                # Salvar arquivo
                nome_musica = selecionada.get("trackName")
                nome_sanitizado = re.sub(r'[\\/*?:"<>|]', "", nome_musica)
                caminho_arquivo = os.path.join(
                    PASTA_LYRICS, f"{nome_sanitizado}.lrc")

                with open(caminho_arquivo, "w", encoding="utf-8") as f:
                    f.write(lrc)

                print(f"{G}Sucesso! Letra sincronizada salva.{R}")
                time.sleep(1)
                iniciar_karaoke(lrc, nome_musica)
            else:
                print(f"{RED}Opção fora da lista.{R}")
                time.sleep(1.5)
        else:
            print(f"{RED}Erro na API: {r.status_code}{R}")
            time.sleep(2)

    except Exception as e:
        print(f"{RED}Erro ao conectar: {e}{R}")
        time.sleep(2)


def listar_locais():
    limpar_tela()
    print(f"{CYAN}--- MÚSICAS EM ./{PASTA_LYRICS} ---{R}\n")

    # Lista apenas arquivos dentro da pasta lyrics
    arquivos = [f for f in os.listdir(PASTA_LYRICS) if f.endswith('.lrc')]

    if not arquivos:
        print(f"{RED}A pasta '{PASTA_LYRICS}' está vazia.{R}")
        time.sleep(2)
        return

    for i, arq in enumerate(arquivos, 1):
        print(f"{P}{i}{R} - {arq}")

    print(f"\n{P}0{R} - Voltar")

    try:
        escolha = int(input(f"\n{BOLD}Escolha o número: {R}"))
        if escolha == 0:
            return

        arquivo_escolhido = arquivos[escolha - 1]
        caminho_completo = os.path.join(PASTA_LYRICS, arquivo_escolhido)

        with open(caminho_completo, "r", encoding="utf-8") as f:
            iniciar_karaoke(f.read(), arquivo_escolhido)
    except (ValueError, IndexError):
        print(f"{RED}Opção inválida.{R}")
        time.sleep(1.5)


def parsear(texto):
    pat = re.compile(r"\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)")
    linhas = []
    for m in pat.finditer(texto):
        seg = int(m[1])*60 + int(m[2]) + int(m[3])/100
        linhas.append((seg, m[4].strip()))
    return sorted(linhas)


def iniciar_karaoke(conteudo_lrc, titulo):
    linhas = parsear(conteudo_lrc)
    limpar_tela()
    print(f"{CYAN}Preparado: {BOLD}{titulo}{R}")
    print(f"Dê o play na música no seu player externo...")
    input(f"\n{P}>>> Pressione ENTER para sincronizar <<< {R}")

    inicio = time.time()

    try:
        for i, (ts, texto) in enumerate(linhas):
            while (time.time() - inicio) < ts:
                time.sleep(0.01)

            limpar_tela()
            print(f"{G}Tocando: {titulo}{R}\n")

            inicio_view = max(0, i - 6)
            for idx in range(inicio_view, i + 1):
                t_hist, txt_hist = linhas[idx]
                if idx == i:
                    print(f"{BOLD}{P}>>> {txt_hist}{R}")
                else:
                    print(f"{D}    {txt_hist}{R}")

        print(f"\n{G}Fim da música!{R}")
        time.sleep(2)
    except KeyboardInterrupt:
        print(f"\n{RED}Interrompido.{R}")
        time.sleep(1)


# Loop principal
while True:
    limpar_tela()
    print(f"""{BOLD}{CYAN}
    ╔══════════════════════════════╗
    ║      TERMINAL KARAOKÊ        ║
    ╚══════════════════════════════╝{R}
    
    {P}1.{R} Buscar nova música (Online)
    {Y}2.{R} Listar músicas salvas (Pasta {PASTA_LYRICS})
    {P}3.{R} Fechar
    """)

    opc = input(f"{BOLD}Escolha uma opção: {R}")

    if opc == '1':
        buscar_online()
    elif opc == '2':
        listar_locais()
    elif opc == '3':
        print(f"\n{CYAN}Até a próxima!{R}")
        break
    else:
        print(f"{RED}Opção inválida!{R}")
        time.sleep(1)
