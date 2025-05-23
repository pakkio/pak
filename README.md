# Pak - Token-Optimized Text-Based File Archiver for LLMs

**Version: 2.1.4**

## Abstract

`pak` è un'utility da riga di comando scritta in Bash, ora potenziata per essere particolarmente efficiente in termini di token, progettata per combinare file e directory multipli in un unico archivio testuale leggibile (file `.pak`). Memorizza metadati di base (percorso, dimensione originale, conteggio linee e token stimati post-compressione) per ogni file. Fornisce comandi per impacchettare (con varie strategie di compressione), elencare i contenuti e scompattare questi archivi. Il suo formato testuale e le nuove capacità di compressione lo rendono ideale per preparare contesti per Large Language Models (LLM), minimizzando il consumo di token.

## Introduzione

Questo script fornisce un modo semplice e ottimizzato per i token per combinare diversi file in un unico pacchetto. A differenza dei formati binari come `.tar` o `.zip`, gli archivi `pak` sono file di testo semplice, ora con funzionalità avanzate per ridurre la loro dimensione in termini di token. Ciò è particolarmente utile per fornire contesto agli LLM, dove ogni token conta. Lo script include logica per escludere automaticamente artefatti di sviluppo comuni, file binari e file/directory nascosti, e ora offre diverse modalità di compressione del contenuto per un ulteriore risparmio di token.

## Razionale

Perché `pak` in un mondo con `tar` e `zip`?

1.  **Ottimizzazione per LLM:** Progettato specificamente per creare archivi testuali compatti, riducendo il numero di token necessari per passare grandi quantità di codice o documentazione agli LLM.
2.  **Semplicità e Trasparenza:** Il formato dell'archivio rimane testo semplice, usando marcatori chiari. Puoi aprire un file `.pak` in un editor di testo e capirne la struttura.
3.  **Compressione Focalizzata sui Token:** Introduce livelli di compressione (`none`, `light`, `medium`, `aggressive`, `smart`) che mirano a rimuovere ridondanze e parti non essenziali per un LLM, come spazi eccessivi, commenti (opzionale) o estraendo solo strutture di codice chiave.
4.  **Gestione del Budget di Token:** L'opzione `--max-tokens` permette di creare archivi che non superino un budget di token specificato, con una prioritizzazione intelligente dei file.
5.  **Filtro Integrato e Semantico:** Esclude automaticamente file e directory temporanei/residuali comuni, file binari e offre un sistema di prioritizzazione semantica per la modalità "smart".
6.  **Nessuna Dipendenza Esterna Rilevante:** Si basa su strumenti standard della riga di comando Unix/Linux (`bash`, `find`, `stat`, `wc`, `cat`, `awk`, `sed`, `grep`, `head`, `tr`), tipicamente disponibili.
7.  **ID di Archivio Compatti:** Utilizza ID alfanumerici corti invece di UUID lunghi per i marcatori interni, risparmiando ulteriormente token.

## Esplicazione completa: Come funziona

### Formato dell'archivio

Un archivio `.pak` generato da questo script è strutturato come una sequenza di voci di file, con un identificatore univoco (ID corto) all'inizio. Ogni voce segue questo schema:


PAK_ID:aF30uOVUH0s5

Archive created with pak v2.1.4
Archive ID: aF30uOVUH0s5
Compression Mode: aggressive
Extension Filter: .py .md
Token Limit: 16000 (se specificato)

PAK_FILE_aF30uOVUH0s5_START
Path: relative/path/to/your/file.txt
Size: <dimensione originale del file in byte>
Lines: <numero di linee nel file dopo la compressione>
Tokens: <numero stimato di token del file dopo la compressione>
PAK_DATA_aF30uOVUH0s5_START
<Contenuto del file, potenzialmente compresso>
...
PAK_DATA_aF30uOVUH0s5_END

### Compressione (`--pack` o predefinito)

1.  **Parsing Argomenti:** Lo script prima analizza le opzioni globali come `--compress-level` e `--max-tokens`.
2.  **Generazione ID Archivio:** Viene generato un ID corto (es. 12 caratteri alfanumerici) per l'archivio.
3.  **Iterazione e Filtri:** Itera attraverso i file e le directory forniti.
    *   Applica filtri semantici (esclude `node_modules`, `.git`, file binari, ecc.).
    *   Applica filtri per estensione se specificati con `--ext`.
4.  **Compressione del Contenuto:** Per ogni file valido, il contenuto viene processato in base al `COMPRESSION_LEVEL`:
    *   **`none`**: Nessuna compressione.
    *   **`light`**: Rimozione di spazi eccessivi e linee vuote.
    *   **`medium`**: Come `light`, più compressione di commenti e import (per alcuni tipi di file).
    *   **`aggressive`**: Come `medium`, più estrazione di sole strutture di codice essenziali (es. definizioni di funzioni/classi per file di codice) o riduzione aggressiva per altri tipi di file.
    *   **`smart`**: Modalità adattiva. Prioritizza i file in base a estensione e nome. Applica livelli di compressione variabili (da `light` a `aggressive`) per rispettare il `--max-tokens` budget, comprimendo di più i file meno importanti o se il budget è stretto.
5.  **Metadati e Impacchettamento:** Per ogni file processato:
    *   Vengono stampati i marcatori e i metadati (percorso, dimensione originale, linee e token post-compressione).
    *   Il contenuto (compresso o meno) viene aggiunto.
6.  **Output:** Tutto l'output viene inviato allo standard output, permettendo il reindirizzamento (`>`) per creare il file di archivio `.pak`.

### Elenco (`--ls`)

1.  Prende un percorso di file di archivio come input.
2.  Legge l'ID dell'archivio dall'header.
3.  Usa `awk` per elaborare il file, estraendo `Path`, `Size` e `Tokens` (se presente) per ogni file e li stampa.

### Estrazione (`--unpack`)

1.  Prende un percorso di file di archivio e opzionalmente `--outdir`.
2.  Legge l'ID dell'archivio.
3.  Scorre l'archivio, identifica i marcatori di ogni file.
4.  Ricrea la struttura delle directory e scrive il contenuto di ogni file nella destinazione specificata.
    *(Nota: le opzioni di filtro avanzate come --include / --exclude glob/regex della versione 1.x non sono attualmente reimplementate in questa linea di sviluppo focalizzata sulla compressione per LLM.)*

### Verifica (`--verify`)

1.  Prende un percorso di file di archivio.
2.  Controlla la presenza dell'header ID, la corrispondenza dei marcatori di inizio/fine e la presenza dei metadati base per ogni file.
3.  Riporta il numero di file trovati e il totale dei token dichiarati.

## Installazione

1.  Scarica lo script `pak` (o chiamalo `pak2` o come preferisci).
2.  Rendilo eseguibile:
    ```bash
    chmod +x pak
    ```
3.  (Opzionale) Spostalo in una directory nel tuo `$PATH` (es. `/usr/local/bin` o `~/bin`):
    ```bash
    mv pak /usr/local/bin/
    ```

## Utilizzo

Lo script opera in diversi modi:

**1. Compressione di file/directory:**

```bash
# Sintassi Base
pak [GLOBAL_OPTS] [--pack] [PACK_OPTS] <files/dirs ...> > archive.pak

# Global Options (prima del comando o dei file)
#  --compress-level LEVEL : none, light, medium, aggressive, smart (default: none)
#  --max-tokens N         : Limita i token totali (0 per illimitato, default: 0)

# Pack Options (mescolate con file/dir se --pack è esplicito, o dopo i file se implicito)
#  --ext .ext1 .ext2 ...  : Includi solo file con queste estensioni/nomi (es. .py .md Makefile)

# Esempi
# Comprimi aggressivamente con limite di token, solo file Python e Markdown
pak --compress-level aggressive --max-tokens 8000 --ext .py .md ./my_project > project_mini.pak

# Compressione smart di una directory, priorità ai file wichtigen
pak --compress-level smart --max-tokens 16000 ./src > smart_archive.pak

# Compressione leggera di specifici file
pak main.py utils.py README.md --compress-level light > basic_bundle.pak

2. Elenco dei contenuti dell'archivio:

# Sintassi
pak --ls <file_archivio.pak>

# Esempio
pak --ls project_mini.pak


3. Estrazione dell'archivio:

# Sintassi base
pak --unpack <file_archivio.pak>

# Estrazione in una directory specifica
pak --unpack project_mini.pak --outdir ./extracted_stuff


4. Verifica dell'integrità dell'archivio:

# Sintassi
pak --verify <file_archivio.pak>

# Esempio
pak --verify project_mini.pak


5. Mostra versione:

# Sintassi
pak --version

Caratteristiche Avanzate introdotte dalla v2.x

Modalità di Compressione dei Token:

none, light, medium, aggressive, smart per un controllo granulare sul contenuto e sul risparmio di token.

Limite Massimo di Token (--max-tokens):

Assicura che l'archivio generato non superi una soglia di token specificata, cruciale per i limiti di contesto degli LLM.

Sistema di Prioritizzazione Semantica dei File (modalità smart):

Quando si usa --compress-level smart e --max-tokens, i file vengono ordinati per importanza (basata su estensione, nomi come README, main, ecc.) e compressi in modo adattivo per rispettare il budget.

Compressione Sintattica per File di Codice (modalità aggressive):

Tenta di estrarre solo le parti strutturalmente importanti del codice (definizioni di funzioni/classi, import) per massimizzare il rapporto segnale/rumore per gli LLM.

Stima dei Token e Gestione del Budget:

Lo script stima i token per ogni file dopo la compressione e gestisce il conteggio totale.

Limitazioni

Focus sul Testo per LLM: Progettato e ottimizzato per file di testo da usare con LLM. La gestione di file binari è intenzionalmente limitata dalla lista SEMANTIC_EXCLUDES.

Metadati: Memorizza percorso, dimensione originale, linee e token post-compressione. Non preserva permessi, proprietà o timestamp dettagliati (non tipicamente necessari per il contesto LLM).

Efficienza di Compressione vs. gzip: La "compressione" qui è più una "riduzione selettiva del contenuto testuale". Per la compressione dati generica, strumenti come gzip sono più appropriati.

Robustezza delle Regex di Compressione: Le funzioni di compressione (specialmente medium e aggressive) usano espressioni regolari che sono euristiche e potrebbero non essere perfette per tutti i linguaggi di programmazione o stili di codice esotici.

Nomi di File: Nomi di file estremamente insoliti (es. contenenti newline) non sono testati e potrebbero causare problemi.
