# LyriPy

Player de karaokê no terminal com interface gráfica. Busque músicas online, baixe o áudio do YouTube automaticamente e acompanhe as letras sincronizadas em tempo real.

## Funcionalidades

- Busca integrada com [lrclib.net](https://lrclib.net) — letras sincronizadas `.lrc`
- Download de áudio direto do YouTube via `yt-dlp`
- Biblioteca local com detecção automática de áudio salvo
- Janela de letras com linha atual em destaque + contexto anterior e próximo
- Pausa e ajuste de sincronia em tempo real
- Sincronização manual para quem não tiver arquivo de áudio
- Executável standalone para Windows (sem precisar instalar Python)

## Como usar

### Opção 1 — executável

Baixe o `LyriPy.exe` da pasta `dist/`, coloque em qualquer pasta e execute.  
As pastas `lyrics/` e `audio/` são criadas automaticamente ao lado do `.exe`.

### Opção 2 — rodar com Python

```bash
pip install -r requirements.txt
python app.py
```

> Requer Python 3.10+ e Windows (usa PowerShell para reprodução de áudio).

## Controles

| Botão | Ação |
|-------|------|
| `▶ / ⏸` | Pausar / retomar (ou iniciar sync manual) |
| `◀ 0.5s` | Atrasar a letra em 0.5s |
| `0.5s ▶` | Adiantar a letra em 0.5s |

## Estrutura

```
lyripy/
├── app.py            # aplicação principal
├── music.py          # versão terminal (legado)
├── requirements.txt
├── lyrics/           # letras .lrc salvas (ignorado pelo git)
└── audio/            # áudios baixados  (ignorado pelo git)
```

## Dependências

```
requests
rich
yt-dlp
customtkinter
pyinstaller
```

## Build

```bash
python -m PyInstaller --onefile --windowed --name LyriPy app.py
```
