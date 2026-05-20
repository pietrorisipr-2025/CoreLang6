# Estrazione parziale CL6 (range)
Comando:
```bash
python3 cl6.py extract-file --container release.cl6b --path data/big.bin --out-file big_part.bin --range 0:1048576
```
- `--range start:end` (byte) è opzionale. Se omesso, estrae l'intero file.
- Estrazione usa indice nel footer e decodifica solo i chunk coinvolti.
- Supporto codec: zlib + plugin opzionali zstd/lz4.
