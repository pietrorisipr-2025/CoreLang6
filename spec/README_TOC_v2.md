
# TOC v2 — integrità chunk+file
- `version: 2`
- `chunks[cid]`: `payload_start`, `orig_len`, `codec`, **`sha256`** (sul contenuto decompresso)
- `files[path]`: `total`, `cids[]`, `offsets[]`, **`sha256`** (sull'intero file decompresso)

## Comandi
```bash
python3 cl6.py build-toc-v2 --container release.cl6b
python3 cl6.py extract-file --container release.cl6b --toc release.cl6b.toc.v2.json --path data/big.bin --out-file big.bin --verify
python3 cl6.py verify-file --container release.cl6b --toc release.cl6b.toc.v2.json --path data/big.bin
```
