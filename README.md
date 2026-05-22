# LyriPy

Player de letras sincronizadas `.lrc` direto no terminal. Busque músicas online, baixe o áudio do YouTube automaticamente e cante acompanhando as letras em tempo real.

## Funcionalidades

- **Busca online** — integração com [lrclib.net](https://lrclib.net), 20 resultados com indicador de LRC disponível
- **Download de áudio** — baixa o áudio do YouTube via `yt-dlp` logo após encontrar a letra
- **Biblioteca local** — letras em `lyrics/` e áudios em `audio/`, com detecção automática
- **Janela de letras** — histórico + linha atual destacada + próximas linhas visíveis
- **Controles em tempo real** — pausa e ajuste de sincronia enquanto a música toca

## Controles durante o karaokê

| Tecla | Ação |
|-------|------|
| `Space` | Pausar / retomar |
| `+` | Adiantar sincronia em 0.5s |
| `-` | Atrasar sincronia em 0.5s |
| `Ctrl+C` | Sair da música |

## Instalação

```bash
pip install -r requirements.txt
python music.py
```

> Requer Python 3.10+ e Windows (usa `msvcrt` e Windows MCI para áudio).

## Estrutura

```
lyripy/
├── music.py
├── requirements.txt
├── lyrics/     # letras .lrc
└── audio/      # áudios baixados
```
