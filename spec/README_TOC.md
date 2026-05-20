# TOC pre-calcolato (CL6b)
- File generato: `<container>.toc.json`
- Contiene: per ogni chunk `cid` → `payload_start`, `orig_len`, `codec`; per ogni file `path` → `cids`, `offsets` cumulativi, `total`.
- Uso:
  1) `python3 cl6.py build-toc --container release.cl6b` ⇒ produce `release.cl6b.toc.json`
  2) `python3 cl6.py extract-file --container release.cl6b --toc release.cl6b.toc.json --path data/big.bin --out-file big.1MiB --range 0:1048576`
- Benefici: evita parse di manifest/index a runtime, velocizza la scelta dei chunk e riduce I/O casuale.
