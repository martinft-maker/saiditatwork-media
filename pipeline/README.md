# Pipeline – saiditatwork

Brukes av den ukentlige planlagte oppgaven (se prosjektdokument claude/agent-ukeslop.md).

- `reel.py` – renderer, design C. `python3 reel.py render manusbank.md 012,013 OUTDIR`
- `manusbank.md` – alle manus, format `id|serie|topp|bunn`
- `used_ids.txt` – manus som er brukt eller sperret. Bruk aldri en ID herfra igjen.

Ferdige videoer legges i `reels/saiditatwork_NNN.mp4` på denne grenen (`media`).
