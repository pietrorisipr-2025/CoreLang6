
# Codec in CL6
Supportati sempre: `zlib`, `store`. Opzionali: `zstd` (`pip install zstandard`), `lz4` (`pip install lz4`).

Esempi:
```bash
# Pack con zstd (se disponibile) chunk 1–2 MiB
python3 cl6.py pack-profile --profile zstd-lean --out-file release_zstd.cl6b

# Pack compatibile: zlib livello 6
python3 cl6.py pack-profile --profile zlib-compat --out-file release_compat.cl6b
```
