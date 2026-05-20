
# Strumenti parti `.xs.partNNN.zip`

Verifica parti:
```bash
python3 cl6.py parts-check --dir /path/alle/parti --base 074__CL6_from_Largest_artifacts.zip
```
Se mancano numeri, esce con codice 2 e riporta `missing`.

Ricomposizione:
```bash
python3 cl6.py join-xs --dir /path/alle/parti --base 074__CL6_from_Largest_artifacts.zip --out ./CL6_from_Largest_artifacts.zip
```
Ordina `part001`..`partNNN` e concatena il contenuto unico interno.
