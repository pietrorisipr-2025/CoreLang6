CL6 Upgrade v0.7 (light patch)
-------------------------------
Novità:
- Footer indice nel .cl6b (seek rapido) e comandi 'split' / 'join' direttamente in CLI.
- Codec opzionali 'zstd'/'lz4' selezionabili nel converter (richiedono runtime esterni).
- Firme ed25519: comandi esposti ma richiedono libreria; HS256 resta attivo.

Aggiornamento:
- Sovrascrivi i file inclusi in questa patch sulle stesse path del tuo cl6_toolkit.
- Verifica: 
  python3 cl6_toolkit/cl6.py --help

Esempi:
- Split <1MB: 
  python3 cl6_toolkit/cl6.py split --container release.cl6b --out-dir ./vol --payload 900000
- Join: 
  python3 cl6_toolkit/cl6.py join --parts-dir ./vol --out-file release_rejoined.cl6b

- Plugin decoder zstd/lz4 inclusi (auto). Ed25519 basato su librerie opzionali.
