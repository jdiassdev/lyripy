import os
import re
import glob
import time
import threading
import subprocess
import tempfile
import requests
import customtkinter as ctk
from urllib.parse import quote

try:
    import yt_dlp
    HAS_YT_DLP = True
except ImportError:
    HAS_YT_DLP = False

# ── Pastas ────────────────────────────────────────────────────────────────────

PASTA_LYRICS = "lyrics"
PASTA_AUDIO  = "audio"
for _p in (PASTA_LYRICS, PASTA_AUDIO):
    os.makedirs(_p, exist_ok=True)

# ── Cores ─────────────────────────────────────────────────────────────────────

BG       = "#0d0d1a"
BG_SIDE  = "#11111f"
BG_CARD  = "#16162a"
ACCENT   = "#c026d3"
ACCENT_H = "#a21caf"
DIM      = "#383852"
NEAR     = "#6b7a99"
TEXT     = "#e2e8f0"
GREEN    = "#22c55e"
YELLOW   = "#facc15"

# ── Fontes ────────────────────────────────────────────────────────────────────

F_TITLE = ("Segoe UI", 20, "bold")
F_SEC   = ("Segoe UI", 10, "bold")
F_SMALL = ("Segoe UI", 10)
F_CURR  = ("Segoe UI", 28, "bold")
F_NEAR  = ("Segoe UI", 17)
F_DIM   = ("Segoe UI", 12)


# ── Audio (PowerShell + Windows Media Foundation) ─────────────────────────────

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
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        self._pos_cache = 0.0
        self._lock      = threading.Lock()
        self._running   = True
        threading.Thread(target=self._poll, daemon=True).start()
        time.sleep(1.8)

    def _poll(self):
        while self._running:
            with self._lock:
                try:
                    self._proc.stdin.write("pos\n")
                    self._proc.stdin.flush()
                    line = self._proc.stdout.readline()
                    self._pos_cache = float(line.strip().replace(",", "."))
                except (ValueError, OSError):
                    pass
            time.sleep(0.08)

    def _send(self, cmd: str):
        with self._lock:
            try:
                self._proc.stdin.write(cmd + "\n")
                self._proc.stdin.flush()
            except OSError:
                pass

    @property
    def pos(self) -> float:
        return self._pos_cache

    def play(self):   self._send("play")
    def pause(self):  self._send("p")
    def resume(self): self._send("r")

    def close(self):
        self._running = False
        self._send("q")
        try:
            self._proc.wait(timeout=3)
        except Exception:
            self._proc.kill()
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass


# ── LRC ───────────────────────────────────────────────────────────────────────

def parsear(texto: str) -> list[tuple[float, str]]:
    pat = re.compile(r"\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)")
    linhas = []
    for m in pat.finditer(texto):
        seg = int(m[1]) * 60 + int(m[2]) + int(m[3]) / 100
        linhas.append((seg, m[4].strip()))
    return sorted(linhas)


# ── yt-dlp ────────────────────────────────────────────────────────────────────

def baixar_audio(query: str, nome_san: str) -> str | None:
    base = os.path.join(PASTA_AUDIO, nome_san)
    opts = {
        "format": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio",
        "outtmpl": base + ".%(ext)s",
        "quiet": True, "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"ytsearch1:{query}"])
        files = glob.glob(base + ".*")
        return files[0] if files else None
    except Exception:
        return None


def audio_local(nome_san: str) -> str | None:
    for ext in (".mp3", ".m4a", ".wav", ".wma", ".ogg"):
        p = os.path.join(PASTA_AUDIO, nome_san + ext)
        if os.path.isfile(p):
            return p
    return None


# ── App ───────────────────────────────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class LyriPy(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("LyriPy")
        self.geometry("980x620")
        self.minsize(800, 500)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self._fechar)

        self._player:  AudioPlayer | None = None
        self._linhas:  list[tuple[float, str]] = []
        self._current  = -1
        self._offset   = 0.0
        self._pausado  = False
        self._manual       = False
        self._manual_ini   = 0.0
        self._manual_pausa = 0.0
        self._manual_ini_p = 0.0
        self._resultados: list[dict] = []

        self._build()
        self._refresh_salvos()
        self._tick()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        self._side = ctk.CTkFrame(self, width=260, fg_color=BG_SIDE, corner_radius=0)
        self._side.pack(side="left", fill="y")
        self._side.pack_propagate(False)

        self._area = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._area.pack(side="right", fill="both", expand=True)

        self._build_sidebar()
        self._build_player()

    def _build_sidebar(self):
        s = self._side

        ctk.CTkLabel(s, text="LyriPy", font=F_TITLE,
                     text_color=ACCENT).pack(pady=(20, 16), padx=16, anchor="w")

        self._entry = ctk.CTkEntry(
            s, placeholder_text="Artista ou música...",
            height=36, corner_radius=8,
            border_color="#2a2a4a", fg_color=BG_CARD
        )
        self._entry.pack(fill="x", padx=14, pady=(0, 6))
        self._entry.bind("<Return>", lambda _: self._buscar())

        self._btn_buscar = ctk.CTkButton(
            s, text="Buscar", height=34, corner_radius=8,
            fg_color=ACCENT, hover_color=ACCENT_H, command=self._buscar
        )
        self._btn_buscar.pack(fill="x", padx=14, pady=(0, 8))

        self._lbl_status = ctk.CTkLabel(s, text="", font=F_SMALL, text_color="#555",
                                         wraplength=230, justify="left")
        self._lbl_status.pack(anchor="w", padx=14, pady=(0, 6))

        ctk.CTkLabel(s, text="RESULTADOS", font=F_SEC,
                     text_color="#3a3a5a").pack(anchor="w", padx=14, pady=(0, 2))
        self._fr_res = ctk.CTkScrollableFrame(
            s, fg_color=BG_SIDE, height=190, scrollbar_button_color="#1a1a2e"
        )
        self._fr_res.pack(fill="x", padx=6, pady=(0, 10))

        ctk.CTkLabel(s, text="SALVOS", font=F_SEC,
                     text_color="#3a3a5a").pack(anchor="w", padx=14, pady=(0, 2))
        self._fr_salvos = ctk.CTkScrollableFrame(
            s, fg_color=BG_SIDE, scrollbar_button_color="#1a1a2e"
        )
        self._fr_salvos.pack(fill="both", expand=True, padx=6, pady=(0, 12))

    def _build_player(self):
        a = self._area

        # placeholder (some quando tem música)
        self._placeholder = ctk.CTkLabel(
            a, text="Busque uma música\nou selecione uma salva",
            font=("Segoe UI", 16), text_color="#1e1e38", justify="center"
        )
        self._placeholder.place(relx=0.5, rely=0.45, anchor="center")

        # título
        self._lbl_titulo = ctk.CTkLabel(
            a, text="", font=("Segoe UI", 13), text_color=ACCENT
        )
        self._lbl_titulo.pack(pady=(18, 0))

        # letras
        self._fr_letras = ctk.CTkFrame(a, fg_color=BG)
        self._fr_letras.pack(fill="both", expand=True, padx=40)

        self._lbls: list[ctk.CTkLabel] = []
        for _ in range(7):
            lbl = ctk.CTkLabel(
                self._fr_letras, text="", wraplength=560,
                justify="center", font=F_DIM, text_color=DIM
            )
            lbl.pack(pady=5)
            self._lbls.append(lbl)

        # controles
        bar = ctk.CTkFrame(a, fg_color=BG_CARD, height=52, corner_radius=0)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        ctk.CTkButton(
            bar, text="▶ / ⏸", width=80, height=32,
            fg_color="#1e1e38", hover_color="#2a2a50",
            border_width=1, border_color="#2a2a55",
            command=self._toggle_pause
        ).pack(side="left", padx=(14, 6), pady=10)

        for delta, label in ((-0.5, "◀ 0.5s"), (+0.5, "0.5s ▶")):
            ctk.CTkButton(
                bar, text=label, width=70, height=32,
                fg_color="#181830", hover_color="#222244",
                border_width=1, border_color="#222244",
                command=lambda d=delta: self._adj(d)
            ).pack(side="left", padx=3, pady=10)

        self._lbl_info = ctk.CTkLabel(bar, text="", font=F_SMALL, text_color="#444")
        self._lbl_info.pack(side="left", padx=14)

    # ── Busca ─────────────────────────────────────────────────────────────────

    def _buscar(self):
        termo = self._entry.get().strip()
        if not termo:
            return
        self._status("Procurando...")
        self._btn_buscar.configure(state="disabled")
        threading.Thread(target=self._buscar_bg, args=(termo,), daemon=True).start()

    def _buscar_bg(self, termo: str):
        try:
            r = requests.get("https://lrclib.net/api/search",
                             params={"q": termo}, timeout=10)
            resultado = r.json()[:20] if r.status_code == 200 else []
        except Exception:
            resultado = []
        self.after(0, self._mostrar_resultados, resultado)

    def _mostrar_resultados(self, lista: list):
        self._resultados = lista
        for w in self._fr_res.winfo_children():
            w.destroy()

        if not lista:
            ctk.CTkLabel(self._fr_res, text="Sem resultados.",
                         font=F_SMALL, text_color="#333").pack(pady=8)
        else:
            for i, res in enumerate(lista):
                nome    = res.get("trackName", "?")
                artista = res.get("artistName", "?")
                tem_lrc = bool(res.get("syncedLyrics"))
                ctk.CTkButton(
                    self._fr_res,
                    text=f"{'●' if tem_lrc else '○'}  {nome}  —  {artista}",
                    anchor="w", height=30, font=F_SMALL,
                    fg_color="transparent",
                    text_color=TEXT if tem_lrc else "#333",
                    hover_color="#1a1a30",
                    command=lambda idx=i: self._selecionar(idx)
                ).pack(fill="x", pady=1)

        self._status("")
        self._btn_buscar.configure(state="normal")

    def _selecionar(self, idx: int):
        res = self._resultados[idx]
        lrc = res.get("syncedLyrics")
        if not lrc:
            self._status("Sem letra sincronizada.")
            return

        nome     = res.get("trackName", "musica")
        artista  = res.get("artistName", "")
        nome_san = re.sub(r'[\\/*?:"<>|]', "", nome)

        with open(os.path.join(PASTA_LYRICS, f"{nome_san}.lrc"), "w", encoding="utf-8") as f:
            f.write(lrc)

        self._refresh_salvos()
        encontrado = audio_local(nome_san)

        if encontrado:
            self._iniciar(lrc, nome, encontrado)
        elif HAS_YT_DLP:
            self._status("Baixando áudio do YouTube...")
            self._iniciar(lrc, nome, None)  # mostra letra já; áudio vem depois
            threading.Thread(
                target=self._baixar_e_conectar,
                args=(artista, nome, nome_san),
                daemon=True
            ).start()
        else:
            self._iniciar(lrc, nome, None)

    def _baixar_e_conectar(self, artista, nome, nome_san):
        path = baixar_audio(f"{artista} {nome}".strip(), nome_san)
        self._refresh_salvos()
        if path:
            self.after(0, self._conectar_audio, path)
        else:
            self.after(0, self._status, "Falha no download do áudio.")

    # ── Salvos ────────────────────────────────────────────────────────────────

    def _refresh_salvos(self):
        self.after(0, self._refresh_salvos_ui)

    def _refresh_salvos_ui(self):
        for w in self._fr_salvos.winfo_children():
            w.destroy()
        arqs = sorted(f for f in os.listdir(PASTA_LYRICS) if f.endswith(".lrc"))
        for arq in arqs:
            ns  = os.path.splitext(arq)[0]
            tem = bool(audio_local(ns))
            ctk.CTkButton(
                self._fr_salvos,
                text=f"{'●' if tem else '○'}  {ns}",
                anchor="w", height=28, font=F_SMALL,
                fg_color="transparent",
                text_color=TEXT if tem else "#555",
                hover_color="#1a1a30",
                command=lambda a=arq, n=ns: self._abrir_salvo(a, n)
            ).pack(fill="x", pady=1)

    def _abrir_salvo(self, arquivo: str, nome_san: str):
        with open(os.path.join(PASTA_LYRICS, arquivo), "r", encoding="utf-8") as f:
            lrc = f.read()
        self._iniciar(lrc, nome_san, audio_local(nome_san))

    # ── Karaokê ───────────────────────────────────────────────────────────────

    def _iniciar(self, lrc: str, titulo: str, audio_path: str | None):
        self._parar()
        self._linhas  = parsear(lrc)
        self._current = -1
        self._offset  = 0.0
        self._pausado = False
        self._manual  = False
        self._lbl_titulo.configure(text=titulo)
        self._lbl_info.configure(text="")
        self._placeholder.place_forget()
        self._render()

        if audio_path and os.path.isfile(audio_path):
            self._status("Carregando áudio...")
            threading.Thread(target=self._carregar_audio,
                             args=(audio_path,), daemon=True).start()
        else:
            self._status("Sem áudio  —  use ▶ / ⏸ para sincronizar manualmente")

    def _carregar_audio(self, path: str):
        try:
            player = AudioPlayer(path)
            self.after(0, self._audio_pronto, player)
        except Exception as e:
            self.after(0, self._status, f"Erro no áudio: {e}")

    def _audio_pronto(self, player: AudioPlayer):
        self._player = player
        player.play()
        self._status("")

    def _conectar_audio(self, path: str):
        if self._player:
            return  # já tem um player
        self._status("Conectando áudio...")
        threading.Thread(target=self._carregar_audio, args=(path,), daemon=True).start()

    def _parar(self):
        if self._player:
            threading.Thread(target=self._player.close, daemon=True).start()
            self._player = None
        self._manual = False

    def _toggle_pause(self):
        if self._player:
            self._pausado = not self._pausado
            if self._pausado:
                self._player.pause()
                self._lbl_info.configure(text="PAUSADO", text_color=YELLOW)
            else:
                self._player.resume()
                self._lbl_info.configure(text="")
            return

        if not self._linhas:
            return
        if not self._manual:
            self._manual       = True
            self._manual_ini   = time.time()
            self._manual_pausa = 0.0
            self._current      = -1
            self._lbl_info.configure(text="Sincronizando...", text_color=GREEN)
        else:
            self._pausado = not self._pausado
            if self._pausado:
                self._manual_ini_p = time.time()
                self._lbl_info.configure(text="PAUSADO", text_color=YELLOW)
            else:
                self._manual_pausa += time.time() - self._manual_ini_p
                self._lbl_info.configure(text="")

    def _adj(self, delta: float):
        self._offset += delta
        sinal = "+" if self._offset >= 0 else ""
        self._lbl_info.configure(
            text=f"offset {sinal}{self._offset:.1f}s", text_color="#64748b"
        )

    # ── Loop ──────────────────────────────────────────────────────────────────

    def _tick(self):
        if self._linhas and not self._pausado:
            pos = None
            if self._player:
                pos = self._player.pos + self._offset
            elif self._manual:
                elapsed = time.time() - self._manual_ini - self._manual_pausa
                pos = elapsed + self._offset

            if pos is not None:
                while (self._current + 1 < len(self._linhas)
                       and pos >= self._linhas[self._current + 1][0]):
                    self._current += 1
                self._render()

        self.after(50, self._tick)

    def _render(self):
        i = self._current
        for slot, idx in enumerate([i-3, i-2, i-1, i, i+1, i+2, i+3]):
            lbl = self._lbls[slot]
            txt = ""
            if 0 <= idx < len(self._linhas):
                txt = self._linhas[idx][1] or "·"
            if slot == 3:
                lbl.configure(text=txt, font=F_CURR, text_color="white")
            elif slot in (2, 4):
                lbl.configure(text=txt, font=F_NEAR, text_color=NEAR)
            else:
                lbl.configure(text=txt, font=F_DIM, text_color=DIM)

    # ── Utils ─────────────────────────────────────────────────────────────────

    def _status(self, msg: str):
        self._lbl_status.configure(text=msg)

    def _fechar(self):
        self._parar()
        self.destroy()


# ── Entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = LyriPy()
    app.mainloop()
