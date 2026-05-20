
# HTTP Range adapter
Serve un file interno a `.cl6b` via HTTP con supporto `Range`.

```bash
# genera TOC una volta per velocità
python3 cl6.py build-toc --container release.cl6b
# avvia server (consigliato con --toc per evitare full extract iniziale)
python3 tools/cl6_http_range_adapter.py --container release.cl6b --path data/big.bin --toc release.cl6b.toc.json --port 8080
```
