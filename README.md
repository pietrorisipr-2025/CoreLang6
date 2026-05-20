# CoreLang6 (CL6)

**Packaging, distribuzione e verifica di artefatti binari su larga scala.**

CL6 è uno stack per rilasci, aggiornamenti e repliche efficienti di dati pesanti: dataset, modelli ML, corpora, indici, backup logici. Risolve un problema specifico — trasferire solo i byte che sono davvero cambiati, con integrità verificabile e accesso parziale senza scaricare tutto.

---

## Il problema che risolve

Hai 10 GB di dati. Aggiorni il 3%. Con un archivio tradizionale rispedisci 10 GB. Con CL6 rispedisci ~300 MB, verifichi l'integrità chunk per chunk, e estrai solo la parte che ti serve senza toccare il resto.

```
Prima:  upload 10 GB → download 10 GB → verifica manuale (o nessuna)
Con CL6: upload 300 MB di delta → download selettivo → verifica automatica SHA-256 + Merkle
```

Casi d'uso principali:

- **Dataset/corpora aggiornati frequentemente** — spedisci solo i chunk nuovi tra versioni
- **Modelli ML e patch** — LoRA, gradient update, shard di indici vettoriali con dedup e verifica
- **Distribuzione su larga scala** — HTTP Range, resume su rete instabile, storage S3/GCS/MinIO
- **Accesso parziale** — estrai un capitolo, uno shard, una porzione di file senza scaricare il container intero

---

## Come funziona

```
+---------------------- Release (.cl6b) --------------------------------+
| Manifest (file e segmenti)   |  TOC v2 (indice chunk/file)           |
|   - elenco file              |  - per ogni chunk:                    |
|   - segmenti → CID           |    {frame_start, comp_len, orig_len,  |
|   - profilo build            |     codec, sha256}                    |
|                              |  - per ogni file:                     |
|                              |    {cids, offsets, total, sha256}     |
|  +------------------------+  +-------------------------------------+  |
|  |   Chunks compressi     |    Footer → offset TOC v2              |  |
|  |  (zstd / zlib / store) |                                        |  |
|  +------------------------+----------------------------------------+  |
+-----------------------------------------------------------------------+
              ^                        ^
              |                        |
            CDC                   Accesso O(1)
      (content-defined             (range-read
       chunking)                    per chunk)
```

1. **Chunking CDC** — i file vengono spezzati con rolling hash (gear-hash). I confini sono stabili anche quando si inseriscono o spostano byte: massimizza il riuso tra versioni.
2. **Compressione codec-agnostica** — ogni chunk è compresso con il codec del profilo (zstd consigliato, zlib o store come fallback). CL6 non è un codec: ne usa uno.
3. **TOC v2** — indice precomputato che mappa ogni chunk a posizione, dimensioni, codec e SHA-256. Permette range-read O(1) e verifica senza parsare l'intero container.
4. **Integrità** — SHA-256 per chunk e per file, Merkle root globale della release. Firma Ed25519 opzionale per ambienti regolati.
5. **Delta-sync** — confronto tra release per CID: si trasferiscono solo i chunk che non esistono già sul destinatario.

---

## Quickstart

```bash
git clone https://github.com/tuousername/corelang6](https://github.com/pietrorisipr-2025/CoreLang6
cd corelang6
python3 --version  # richiede Python 3.9+
# dipendenza opzionale ma consigliata:
pip install zstandard
```

### Build e pubblicazione

```bash
# Pack con profilo zstd (consigliato in produzione)
python3 cl6.py pack-profile \
  --profile zstd-lean \
  --input-dir ./data \
  --out-file release.cl6b

# Costruisci l'indice TOC v2
python3 cl6.py build-toc-v2 \
  --container release.cl6b

# Verifica la release
python3 cl6.py release-checklist \
  --container release.cl6b \
  --toc release.cl6b.toc.v2.json
```

### Estrazione parziale e verifica

```bash
# Estrai un singolo file (fast-path con TOC v2, verifica chunk)
python3 cl6.py extract-file \
  --container release.cl6b \
  --toc release.cl6b.toc.v2.json \
  --path path/nel/container \
  --out-file output.bin \
  --verify

# Verifica integrità di un file specifico
python3 cl6.py verify-file \
  --container release.cl6b \
  --toc release.cl6b.toc.v2.json \
  --path path/nel/container

# Estrazione con byte range (senza scaricare tutto)
python3 cl6.py extract-file \
  --container release.cl6b \
  --path path/nel/container \
  --out-file output.bin \
  --range 0:65536
```

### Delta-sync (concetto operativo)

```
Client → Server: "ho questi CID: [abc123, def456, ...]"
Server → Client: chunk mancanti + manifest aggiornato
Risultato: trasferimento proporzionale al delta, non alla release completa
```

---

## Profili di build

| Profilo       | Codec | Livello | Chunk medio | Quando usarlo                        |
|---------------|-------|---------|-------------|--------------------------------------|
| `zstd-lean`   | zstd  | 6       | 512 KiB     | Produzione, rete lenta, dati ripetuti|
| `zlib-compat` | zlib  | 6       | 512 KiB     | Compatibilità massima, no dipendenze |
| `store`       | nessuno | 0     | 1 MiB       | Debug, dati già compressi            |

---

## Struttura del repository

```
cl6.py                  # CLI principale
cl6b/                   # Package Python
  chunker.py            # CDC (gear-hash)
  codecs.py             # Plugin codec (zlib/zstd/lz4/store)
  hashing.py            # BLAKE3 con fallback SHA-256
  ioframes.py           # Frame I/O con CRC32C
  manifest.py           # Validator manifest CL6/MANIFEST_v3
  merkle.py             # Merkle tree (fanout configurabile)
  pack.py               # Pack/extract container .cl6b
  partial.py            # Estrazione parziale e byte range
  signing.py            # Ed25519 + HMAC fallback
  toc.py                # Build TOC v1 e v2
  util.py               # Varint LEB128
spec/                   # Specifiche formato
  CL6_SPEC_v1_0.md
  README_TOC_v2.md
  README_SIGNING.md
  README_HTTP_RANGE.md
  README_PARTIAL_EXTRACTION.md
tools/                  # Utility aggiuntive
conformance/            # Test di conformance
```

---

## Cosa CL6 non è

- **Non è un protocollo di messaggistica** — va abbinato a HTTP/QUIC/gRPC per il trasporto
- **Non è un codec** — usa zstd/zlib/store; il valore è nell'organizzazione (indice, dedup, verifica)
- **Non sostituisce i tool di build ML** — li alimenta (packaging, transport, verifica post-build)
- **Non è la scelta giusta** per un singolo file, trasferimento unico, nessun delta: in quel caso un `.zst` basta e avanza

---

## Stato attuale e problemi noti

Il progetto è alla **v0.16** — prototipo funzionante, non production-ready.

**Funziona:**
- `pack-profile`, `build-toc-v2`, `release-checklist`
- `extract-file` (con e senza TOC v2, con verifica chunk)
- `verify-file`
- Byte range extraction
- Firma Ed25519 e HMAC fallback
- CRC32C reale (Castagnoli, implementazione pure-Python)

**Problemi noti:**
- `pack.extract()` (funzione interna, non esposta dal CLI) ha un bug nel path di accesso casuale via indice — usa `frame_start` invece di `payload_start` come workaround, già implementato in `partial.py`
- BLAKE3 non disponibile nell'ambiente base → fallback silenzioso su SHA-256; in produzione installare `blake3` o fissare SHA-256 come hash ufficiale
- zstd e lz4 richiedono installazione esplicita (`pip install zstandard lz4`)
- Delta-sync: il protocollo è definito concettualmente, l'implementazione client/server non è ancora nel repo

---

## Roadmap

- [ ] Fix `pack.extract()` random-access path
- [ ] Hash stabile (scelta definitiva: SHA-256 esplicito o BLAKE3 obbligatorio)
- [ ] Delta-sync: implementazione client/server minimale
- [ ] Binding Go o Rust (la spec è language-agnostic)
- [ ] Integrazione HTTP Range nativa
- [ ] Observability (OpenTelemetry): bytes risparmiati, latenza p50/p95, tasso riuso chunk
- [ ] Semantic chunking per testi e embedding

---

## Contributi

Il progetto è aperto. Se stai lavorando su distribuzione di artefatti ML, dataset pipeline, o sistemi di replica con delta-sync e hai un caso d'uso concreto, apri una issue — il feedback su problemi reali è la cosa più utile in questa fase.

---

## Licenza

MIT
