# Pak: il tool che risolve il dramma quotidiano del copia-incolla con gli LLM

## Il problema che tutti abbiamo (ma che fingiamo di non vedere)

Sei un programmatore nel 2025. Usi Claude, GPT, o qualsiasi altro LLM per praticamente ogni attività di sviluppo. E ogni volta è la stessa **commedia dell'assurdo**:

- Devi condividere 5-10 file con l'LLM per avere il context giusto
- Apri il primo file → Ctrl+A → Ctrl+C → vai nel chat → aggiungi "File: path/file.py" → Ctrl+V
- Ripeti per ogni singolo file, pregando di non sbagliare l'ordine
- Dopo 15 minuti hai un prompt che sembra un collage di appunti universitari
- L'LLM ti risponde con codice modificato in blocchi separati
- **Il vero incubo**: ora devi copiare ogni pezzo dall'LLM e salvarlo nel file giusto
- Ti sbagli, sovrascrivi qualcosa di importante, e bestemmie in dialetto

**Questo teatrino 20 volte al giorno.**

Se questo workflow ti suona familiare, Pak è nato per te.

## La soluzione: due tool, due filosofie, zero compromessi

Pak non è un singolo strumento, ma una **famiglia di tool** che risolve lo stesso problema con due approcci distinti:

### **`pak`** - La via della semplicità

*"Voglio risolvere il problema, subito, senza installare nulla"*

- **Bash puro**: funziona su qualsiasi sistema Unix senza dipendenze
- **Zero setup**: scarichi, rendi eseguibile, funziona
- **Compressione intelligente ma pragmatica**: rimuove spazi vuoti, commenti banali, ottimizza per la leggibilità dell'LLM
- **Perfetto per**: workflow quotidiano, ambienti corporate con restrizioni, situazioni "voglio che funzioni e basta"

### **`pak4.py`** - La via della precisione chirurgica

*"Lavoro intensivamente con LLM costosi e ogni token conta"*

- **Analisi AST**: comprende la struttura sintattica del codice, non solo il testo
- **Prioritizzazione semantica**: distingue automaticamente tra `README.md` (critico) e `test_utils.py` (sacrificabile)
- **Budget management**: gestione rigorosa dei token con compressione adattiva
- **Perfetto per**: progetti complessi, ottimizzazione token avanzata, workflow professionali intensivi

## Esempi pratici: dalla teoria alla realtà

### Scenario 1: Debug veloce (usa `pak`)

Il tuo server Node.js ha un bug nell'autenticazione:

```bash
# Con pak classico
pak server.js routes/auth.js middleware/validation.js > bug-context.pak
# Incolli il contenuto nel chat + "Bug nell'auth, token scaduto viene accettato"
# L'LLM vede tutto il context necessario e ti dà la soluzione
```

**Tempo**: 30 secondi  
**Complessità**: Zero  
**Efficacia**: Perfetta per il 90% dei casi

### Scenario 2: Refactoring importante (usa `pak4.py`)

Devi convertire un'intera app React da class components a hooks:

```bash
# Versione completa
pak4.py --compress-level smart --max-tokens 12000 src/ > refactoring.pak

# Versione concisa (identica)
pak4.py -cs -m 12000 src/ -o refactoring.pak

# L'LLM riceve:
# - Struttura completa del progetto
# - Priorità ai componenti principali  
# - API surface dei file di supporto
# - Budget token ottimizzato
```

**Risultato**: Context preciso senza spreco di token, refactoring guidato e completo

### Scenario 3: Ambiente aziendale restrittivo (usa `pak`)

Il tuo laptop di lavoro ha Python rotto, policy IT draconiane, e zero possibilità di installare dipendenze:

```bash
# pak funziona comunque (sintassi più spartana ma affidabile)
pak --compress-level medium project/ --ext .java .xml > enterprise-safe.pak
# oppure
pak -c2 project/ --ext .java .xml > enterprise-safe.pak
```

**Filosofia**: Il tool che funziona batte il tool perfetto che non riesci a far partire

## Installazione: scegli la tua strada

### Per la semplicità (`pak`)

```bash
curl -O https://raw.githubusercontent.com/pakkio/pak/main/pak
chmod +x pak
sudo mv pak /usr/local/bin/
```

**Done.** Zero dipendenze, funziona ovunque.

### Per la potenza (`pak4.py`)

```bash
# Scarica pak4.py
curl -O https://raw.githubusercontent.com/pakkio/pak/main/pak4.py
curl -O https://raw.githubusercontent.com/pakkio/pak/main/pak_core.py
chmod +x pak4.py
sudo mv pak4.py pak_core.py /usr/local/bin/

# Installa le dipendenze per l'analisi AST (opzionale ma raccomandato)
pip3 install --user tree-sitter tree-sitter-languages tree-sitter-python

# Verifica che tutto funzioni
pak4.py --ast-info
```

**Note**: Se non installi le dipendenze Python, pak4.py **fallback automaticamente** alla compressione testuale. Non si rompe mai.

## Cheat sheet: sintassi rapida per l'uso quotidiano

### Pak3 - Comandi essenziali
```bash
# Pattern più comuni (memorizza questi!)
pak4.py . -c2 -o project.pak           # Tutto, medium compression
pak4.py src/ -cs -m 8000              # Smart mode, budget 8k
pak4.py -c3 -t py,md . -o minimal.pak # Solo Python/Markdown, aggressive
pak4.py -l archive.pak                # Lista contenuti
pak4.py -x archive.pak -d extracted/  # Estrai tutto
pak4.py -x archive.pak -p "test.*"    # Estrai solo test files

# Livelli compressione shorthand
-c0  # none (tutto)
-c1  # light (spazi e commenti base)  
-c2  # medium (commenti e ottimizzazioni)
-c3  # aggressive (solo API surface)
-cs  # smart (adattivo per importanza file)

# Estensioni shorthand
-t py,md,js     # invece di --ext .py .md .js
-t java,xml     # invece di --ext .java .xml
```

### Pak classico - Sintassi essenziale
```bash
# Comandi base pak (versione semplice)
pak . > project.pak                 # Tutto senza compressione
pak --compress-level medium src/    # Medium compression
pak --ext .py .md src/ > docs.pak   # Solo Python e Markdown
pak --ls project.pak                # Lista contenuti
pak --unpack project.pak            # Estrai tutto
```

## Guide d'uso: dal basic al professional

### Pak classico: workflow essenziale

```bash
# Impacchetta tutto
pak . > progetto.pak

# Solo certi tipi di file
pak --ext .py .md ./src > python-docs.pak

# Compressione media (rimuove commenti e spazi extra)
pak --compress-level medium src/ > compressed.pak

# Con limite di token approssimativo
pak --max-tokens 8000 large-project/ > constrained.pak

# Vedi cosa hai impacchettato
pak --ls progetto.pak

# Scompatta quando l'LLM ti ha risposto
pak --unpack risposta.pak
```

### Pak3: controllo chirurgico

```bash
# Sintassi completa vs. forma breve (equivalenti)
pak4.py --compress-level smart --max-tokens 12000 src/ > optimized.pak
pak4.py -cs -m 12000 src/ > optimized.pak

# Solo API surface (per code review)
pak4.py --compress-level aggressive backend/ --ext .py .sql > api-review.pak
pak4.py -c3 -t py,sql backend/ > api-review.pak

# Debug con prioritizzazione automatica e output automatico
pak4.py -cs -m 8000 -o debug-context.pak main.py utils/ config/

# Estrazione con filtri regex
pak4.py -x response.pak -p ".*test.*" -d ./tests-only

# Analisi dettagliata del contenuto
pak4.py -l -p ".*\\.py$" complex-project.pak

# Quick reference comandi brevi:
# -c[0-3,s]  : compressione (0=none, 1=light, 2=medium, 3=aggressive, s=smart)
# -t py,md   : estensioni (senza punti, separate da virgole)
# -m NUM     : max tokens
# -o FILE    : output file (invece di stdout)
# -q         : quiet mode
# -l         : list contents
# -x         : extract
# -v         : verify
# -p REGEX   : pattern filter
# -d DIR     : output directory per extract
```

## Filosofia: perché due tool invece di uno?

### La trappola del "tool unico universale"

La maggior parte dei progetti open source cade nella **feature creep**: iniziano semplici, aggiungono funzionalità per ogni caso d'uso, e alla fine diventano complessi e fragili.

Noi abbiamo fatto il contrario: **cristallizzato la semplicità** in `pak`, e **canalizzato la complessità** in `pak4.py`.

### Quando usare cosa

**Usa `pak` quando**:
- Vuoi risolvere il problema velocemente
- Sei in un ambiente con restrizioni 
- Il tuo progetto è "normale" (< 50 file importanti)
- Preferisci affidabilità a ottimizzazione estrema
- Non hai voglia di pensare a dipendenze

**Usa `pak4.py` quando**:
- Lavori con LLM costosi intensivamente
- Gestisci progetti complessi (> 100 file)
- Ogni token risparmiato ha valore economico
- Vuoi controllo granulare sulla compressione
- Apprezzi l'analisi sintattica precisa

## Trucchi del mestiere

### Alias per workflow comuni (ora con comandi brevi!)

```bash
# Nel tuo .bashrc/.zshrc - versioni ultra-concise
alias pak-quick='pak -c2 -m 8000'  # medium compression, 8k tokens
alias pak4.py-smart='pak4.py -cs -m 12000'  # smart mode, 12k budget
alias pak4.py-mini='pak4.py -c3 -m 6000'   # aggressive, 6k budget
alias pak4.py-review='pak4.py -c2 -t py,js,ts'  # code review setup

# Template per situazioni comuni
alias pak-bug='pak -c2'  # debug rapido
alias pak-refactor='pak4.py -cs -m 15000'  # refactoring complesso
alias pak-deploy='pak4.py -c1 -t py,sql,yml'  # deploy prep
```

### Quick commands per situazioni frecuenti

```bash
# "Ho bisogno di tutto, subito, formato standard"
pak4.py . -c2 -o project.pak

# "Solo Python e Markdown, aggressive compression"
pak4.py src/ -c3 -t py,md -o minimal.pak

# "Smart mode con budget preciso per GPT-4"
pak4.py . -cs -m 8000 -o gpt4-ready.pak

# "Vediamo cosa c'è in questo pak senza scompattare"
pak4.py -l archive.pak

# "Estrai solo i test"
pak4.py -x archive.pak -p "test.*" -d tests/

# "Verifica rapidamente se il pak è valido"
pak4.py -v archive.pak
```

### Integrazione con Git

```bash
# Solo file modificati di recente
git diff --name-only HEAD~5 | xargs pak > recent-changes.pak

# Staging area per review
git diff --cached --name-only | xargs pak4.py --compress-level smart > staging-review.pak
```

### Template per richieste ricorrenti

```bash
# Crea template riutilizzabili
echo "Analizza questo codice per problemi di performance e security:" > review-template.txt
pak4.py --compress-level medium src/ >> review-template.txt
```

## Casi d'uso reali (testati sul campo)

### 1. **Code review distribuito**
*"Il collega remoto deve revieware una feature"*
```bash
pak4.py --compress-level light feature-branch/ > feature-review.pak
# Mandi il .pak via Slack, il collega può leggerlo o scompattarlo localmente
```

### 2. **Debug assistito**
*"C'è un bug complesso che coinvolge più moduli"*
```bash
pak --compress-level medium \
    server.js \
    routes/ \
    models/ \
    middleware/ > bug-hunting.pak
# Context completo per l'LLM senza dispersioni
```

### 3. **Migrazione guidata**
*"Converto da Python 3.8 a 3.12"*
```bash
pak4.py --compress-level smart --max-tokens 15000 \
     src/ requirements.txt setup.py > migration-context.pak
# L'LLM vede struttura + dipendenze + codice prioritizzato
```

### 4. **Ottimizzazione performance**
*"Questi componenti React renderizzano troppo"*
```bash
pak4.py --compress-level aggressive \
     --ext .jsx .js \
     src/components/ > performance-review.pak
# Solo API surface dei componenti, focus sulla logica di rendering
```

## Limitazioni oneste

### Pak classico
- **Stima token approssimativa**: `len(content) / 4` è una euristica, non scienza
- **Compressione testuale**: intelligente ma non sintattica
- **Prioritizzazione basic**: basata su estensioni e pattern di nomi

### Pak3
- **Dipendenze Python**: tree-sitter richiede setup aggiuntivo
- **Complessità**: più opzioni = più modi per sbagliare configurazione
- **Curva di apprendimento**: la modalità smart richiede comprensione del progetto

### Entrambi
- **Non è magia**: 100k linee non diventano 1k token mantenendo tutto il context
- **Qualità input = qualità output**: se il progetto è un casino architetturale, pak non fa miracoli
- **Context window limits**: anche con compressione, progetti enormi richiedono selezione manuale

## Evoluzione: dal problema personale al tool pubblico

Pak è nato dalla frustrazione personale di uno sviluppatore che passava più tempo a formattare prompt che a programmare. 

La **versione 1** era uno script bash di 50 righe che concatenava file. Funzionava, ma era spartano.

La **versione 2** ha aggiunto compressione intelligente, gestione token, filtri semantici. Già usabile professionalmente.

La **versione 3** introduce analisi AST, prioritizzazione avanzata, fallback robusti. Per chi fa sul serio.

Ma la **filosofia core** è rimasta la stessa: **risolvere un problema reale senza cerimonie**.

## Conclusione: il tool che avresti dovuto avere ieri

Pak non rivoluziona il mondo. Non usa AI per l'AI. Non ha una startup unicorno dietro.

**Semplicemente funziona.** 

Risolve un problema quotidiano fastidioso in modo elegante, affidabile, e senza pretese filosofiche eccessive.

Se lavori con LLM regolarmente, hai due scelte:
1. Continuare con il balletto del copia-incolla (e perdere 20 minuti al giorno per sempre)
2. Investire 5 minuti per scaricare pak e recuperare ore ogni settimana

La matematica è semplice. La scelta è tua.

---

**Download**: https://github.com/pakkio/pak  
**Tempo di setup**: 5 minuti  
**ROI**: Ogni giorno che passa  
**Filosofia**: Pragmatismo senza compromessi  
**Garanzia**: Se non ti semplifica la vita, hai perso solo 5 minuti. Se ti semplifica la vita, hai guadagnato ore per sempre.
