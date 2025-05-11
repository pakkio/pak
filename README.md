# Pak - A Simple Text-Based File Archiver

**Version: 1.4.0**

## Abstract

`pak` è un'utility da riga di comando scritta in Bash progettata per combinare file e directory multipli in un unico archivio testuale leggibile (file `.pak`). Memorizza metadati di base (percorso, dimensione, conteggio linee) per ogni file e fornisce comandi per impacchettare, elencare i contenuti e scompattare questi archivi. La sua caratteristica principale è il formato basato su testo, rendendo gli archivi ispezionabili e gestibili con strumenti di testo standard.

## Introduzione

Questo script fornisce un modo semplice per combinare diversi file in un unico pacchetto. A differenza dei formati binari come `.tar` o `.zip`, gli archivi `pak` sono file di testo semplice. Ciò può essere utile in ambienti dove è desiderata o consentita solo l'elaborazione di testo, per attività di raggruppamento semplici, o per incorporare risorse direttamente all'interno di altri sistemi basati su testo. Lo script include logica per escludere automaticamente artefatti di sviluppo comuni e file/directory nascosti.

## Razionale

Perché creare un altro archivatore quando esistono strumenti come `tar`?

1. **Semplicità e trasparenza:** Il formato dell'archivio è testo semplice, usando marcatori chiari. Puoi aprire un file `.pak` in un editor di testo e capirne facilmente la struttura.
2. **Flussi di lavoro orientati al testo:** Ideale per scenari in cui i blob binari sono indesiderabili o difficili da gestire, come l'incorporazione di file di configurazione o piccoli script all'interno di documenti di testo più grandi o codice sorgente.
3. **Strumento educativo:** Serve come esempio pratico di scripting shell, manipolazione di file, elaborazione di testo (`awk`, `find`) e gestione dello stato all'interno di uno script.
4. **Filtro integrato:** Esclude automaticamente file e directory temporanei/residuali comuni (come `.git`, `node_modules`, `__pycache__`, gli stessi file `.pak`) per mantenere gli archivi puliti senza flag di esclusione complessi.
5. **Nessuna dipendenza binaria esterna (oltre a coreutils):** Si basa su strumenti standard della riga di comando Unix/Linux (`bash`, `find`, `stat`, `wc`, `cat`, `awk`, `mkdir`, `dirname`, `basename`), tipicamente disponibili sulla maggior parte dei sistemi.
6. **Ottimizzato per file system di rete:** Funziona in modo efficiente anche su file system di rete come Google Drive montato in WSL2, utilizzando copie locali temporanee per migliorare le prestazioni.

## Esplicazione completa: Come funziona

### Formato dell'archivio

Un archivio `.pak` generato da questo script è strutturato come una sequenza di voci di file, con un identificatore UUID all'inizio per prevenire collisioni. Ogni voce segue questo schema:

```
__PAK_UUID__:12345678-abcd-9876-efgh-4321ijklmnop
__PAK_FILE_12345678-abcd-9876-efgh-4321ijklmnop_START__
Path: relative/path/to/your/file.txt
Size: <dimensione del file in byte>
Lines: <numero di linee nel file>
__PAK_DATA_12345678-abcd-9876-efgh-4321ijklmnop_START__
<Contenuto della linea 1 del file>
<Contenuto della linea 2 del file>
...
<Contenuto dell'ultima linea del file>
__PAK_DATA_12345678-abcd-9876-efgh-4321ijklmnop_END__
```

### Compressione (`--pack` o predefinito)

1. Lo script itera attraverso i file e le directory forniti come argomenti.
2. Se un argomento è un file, controlla rispetto alle regole di esclusione. Se consentito, raccoglie i metadati (`stat`, `wc`) e chiama `pack_file`.
3. Se un argomento è una directory, usa `find` per localizzare ricorsivamente tutti i file all'interno di quella directory.
4. Per ogni file valido trovato, viene chiamato `pack_file`.
5. `pack_file`:
   * Stampa il marcatore `__PAK_FILE_UUID_START__`.
   * Stampa le linee di metadati (`Path:`, `Size:`, `Lines:`).
   * Stampa il marcatore `__PAK_DATA_UUID_START__`.
   * Usa `cat` per aggiungere il contenuto del file.
   * Stampa il marcatore `__PAK_DATA_UUID_END__`.
6. Tutto l'output viene inviato allo standard output, permettendo il reindirizzamento (`>`) per creare il file di archivio `.pak`.

### Elenco (`--ls`)

1. Prende un percorso di file di archivio come input.
2. Usa `awk` per elaborare il file di archivio riga per riga.
3. Estrae i valori `Path` e `Size` dalle corrispondenti linee di metadati.
4. Quando incontra `__PAK_DATA_UUID_START__`, stampa i metadati raccolti nel formato `path and Size: size`.
5. Ignora il contenuto effettivo del file tra `__PAK_DATA_UUID_START__` e `__PAK_DATA_UUID_END__`.

### Estrazione (`--unpack`)

1. Prende un percorso di file di archivio come input, con opzioni aggiuntive:
   * `--include pattern`: Estrae solo i file che corrispondono al pattern glob
   * `--exclude pattern`: Esclude i file che corrispondono al pattern glob
   * `--include-regex pattern`: Estrae solo i file che corrispondono al pattern regex
   * `--exclude-regex pattern`: Esclude i file che corrispondono al pattern regex
   * `--outdir directory`: Estrae i file nella directory specificata invece della directory corrente
2. Copia l'archivio localmente nella directory temporanea per migliorare le prestazioni su file system di rete.
3. Legge l'archivio in memoria per un'elaborazione più efficiente.
4. Per ogni file nell'archivio:
   * Verifica se corrisponde ai criteri di inclusione/esclusione.
   * Se deve essere estratto, crea le directory necessarie e scrive il contenuto.

### Verifica (`--verify`)

1. Prende un percorso di file di archivio come input.
2. Verifica l'integrità dell'archivio controllando:
   * La presenza dell'header UUID
   * La corrispondenza dei marcatori di inizio e fine di ogni file
   * La completezza dei metadati per ogni file
3. Fornisce un rapporto dettagliato sull'integrità dell'archivio.

## Installazione

1. Scarica lo script `pak` (o clona il repository).
2. Rendilo eseguibile:
   ```bash
   chmod +x pak
   ```
3. (Opzionale) Spostalo in una directory nel tuo `$PATH`, come `/usr/local/bin` o `~/bin`:
   ```bash
   mv pak /usr/local/bin/
   ```

## Utilizzo

Lo script opera in diversi modi:

**1. Compressione di file/directory (modalità predefinita):**

```bash
# Sintassi
pak [--pack] <file_o_dir_1> [file_o_dir_2 ...] > nome_archivio.pak

# Esempi
# Comprimi un singolo file
pak my_script.sh > script_archive.pak

# Comprimi più file
pak file1.txt config.yaml > bundle.pak

# Comprimi i contenuti di una directory
pak ./my_project > project_backup.pak
```

**2. Elenco dei contenuti dell'archivio:**

```bash
# Sintassi
pak --ls <file_archivio.pak>

# Esempio
pak --ls project_backup.pak
```

**3. Estrazione dell'archivio:**

```bash
# Sintassi base
pak --unpack <file_archivio.pak>

# Estrazione selettiva con pattern glob
pak --unpack archive.pak --include "*.py"
pak --unpack archive.pak --exclude "*.txt"

# Estrazione selettiva con espressioni regolari
pak --unpack archive.pak --include-regex "NPC\.[a-z]+\..*\.txt"

# Estrazione in una directory specifica
pak --unpack archive.pak --outdir /path/to/extract

# Combinazione di opzioni
pak --unpack archive.pak --include "*.py" --exclude "test_*.py" --outdir ~/src
```

**4. Verifica dell'integrità dell'archivio:**

```bash
# Sintassi
pak --verify <file_archivio.pak>

# Esempio
pak --verify project_backup.pak
```

**5. Mostra versione:**

```bash
# Sintassi
pak --version
```

## Caratteristiche avanzate

1. **Estrazione selettiva con pattern glob e regex**:
   * `--include "*.py"`: Estrae solo i file Python
   * `--exclude "*.txt"`: Estrae tutti eccetto i file di testo
   * `--include-regex "NPC\.[a-z]+\..*\.txt"`: Estrae file corrispondenti all'espressione regolare

2. **Verifica dell'integrità**:
   * `--verify`: Controlla che l'archivio sia strutturalmente valido

3. **Directory di output personalizzata**:
   * `--outdir /path/to/extract`: Estrae i file nella directory specificata

4. **Ottimizzazione per file system di rete**:
   * Cache locale temporanea per prestazioni migliori
   * Messaggi di debug dettagliati durante l'estrazione

5. **Protezione contro le collisioni**:
   * Ogni archivio ha un UUID unico che viene usato nei marcatori
   * Riduce il rischio di collisioni tra i marcatori e il contenuto del file

## Limitazioni

* **Focus sul testo**: Progettato principalmente per file di testo. Sebbene possa tecnicamente memorizzare file binari, l'elaborazione basata su testo è inefficiente e potrebbe corrompere i dati binari.
* **Metadati**: Memorizza solo percorso, dimensione e conteggio linee. Non preserva permessi, proprietà o timestamp.
* **Efficienza**: Meno efficiente dei formati binari come `tar` per file di grandi dimensioni o un gran numero di file.
* **Gestione degli errori**: La gestione degli errori di base è presente, ma scenari complessi potrebbero portare a comportamenti imprevisti.
* **Vincoli del nome del file**: I nomi di file contenenti caratteri insoliti potrebbero potenzialmente causare problemi, in particolare durante la decompressione.
