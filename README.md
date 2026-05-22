# LyriPy

Player de letras sincronizadas `.lrc` direto no terminal. Busque músicas online, toque o áudio junto ou sincronize manualmente com seu player externo.

## Funcionalidades

- **Busca online** — integração com [lrclib.net](https://lrclib.net), 20 resultados com indicador de LRC disponível
- **Biblioteca local** — letras salvas automaticamente em `lyrics/`
- **Áudio integrado** — abre MP3, WAV ou WMA junto com a letra (sem dependências extras)
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
