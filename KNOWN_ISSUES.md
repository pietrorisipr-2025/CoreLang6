# Problemi noti — CoreLang6 v0.16

## Bug confermati

### 1. `pack.extract()` — random-access path corrotto
**File:** `cl6b/pack.py`, funzione `extract()`  
**Impatto:** la funzione `extract()` chiamata direttamente fallisce con `CRC32C mismatch` quando usa l'indice per accesso casuale ai chunk.  
**Causa:** il calcolo di `payload_start` nel dizionario dell'indice usa `+2` come approssimazione per i varint, poi il seek a `payload_start - 2` atterra nel mezzo del payload invece che all'inizio del frame.  
**Workaround:** il CLI non usa `pack.extract()` — usa `partial.extract_file()` che legge da `frame_start` correttamente. Le funzioni esposte dal CLI funzionano tutte.  
**Fix:** sostituire il seek a `payload_start - 2` con seek a `frame_start` nell'iterazione sui chunk dell'indice.

---

## Dipendenze opzionali non installate di default

### 2. BLAKE3 non disponibile → fallback silenzioso su SHA-256
**File:** `cl6b/hashing.py`  
**Impatto:** se `blake3` non è installato, i CID vengono calcolati con SHA-256. I manifest generati in ambienti diversi (uno con BLAKE3, uno senza) producono CID incompatibili.  
**Soluzione:** o installare `blake3` (`pip install blake3`) o fissare SHA-256 come hash ufficiale rimuovendo il fallback automatico. Da decidere prima di qualsiasi uso in produzione.

### 3. zstd e lz4 richiedono installazione esplicita
**File:** `cl6b/codecs.py`  
**Impatto:** il profilo `zstd-lean` (consigliato) richiede `pip install zstandard`. Senza, il pack fallisce o cade su zlib senza avviso esplicito.  
**Fix:** aggiungere un check esplicito all'avvio del CLI con messaggio chiaro se il codec richiesto dal profilo non è disponibile.

---

## Funzionalità definite ma non ancora implementate

### 4. Delta-sync — solo concettuale
Il protocollo di delta-sync (client invia CID posseduti, server risponde con delta) è documentato nella spec ma non ha un'implementazione client/server nel repository.

### 5. HTTP Range nativa
L'integrazione con HTTP Range per range-read diretto da storage remoto (S3/GCS/MinIO) è nella roadmap ma non implementata.

### 6. Binding non-Python
La spec è language-agnostic ma l'unica implementazione di riferimento è Python. Binding Go o Rust non esistono ancora.

---

## Note sulla CRC32C

L'implementazione in `cl6b/crc32c.py` è **corretta** — usa il polinomio di Castagnoli (`0x1EDC6F41`) in pure Python. Il README originale la descriveva erroneamente come placeholder. È lenta su payload grandi (pure Python); in produzione conviene sostituirla con `crcmod` o `crc32c` C-extension.
