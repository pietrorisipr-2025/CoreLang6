
# Firma e Verifica
Due modalità:
- **Ed25519** (consigliata, richiede `cryptography`)
- **HMAC-SHA256** (fallback con segreto condiviso)

Esempi:
```bash
# genera chiavi
python3 cl6.py gen-keys --priv keys/priv.pem --pub keys/pub.pem

# firma TOC
python3 cl6.py sign --method ed25519 --priv keys/priv.pem --file release.cl6b.toc.json --out release.cl6b.toc.json.sig

# verifica
python3 cl6.py verify --method ed25519 --pub keys/pub.pem --file release.cl6b.toc.json --sig release.cl6b.toc.json.sig
```
