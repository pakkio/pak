# pak4.py: il tool che ti salva dall'inferno del copia-incolla con gli LLM

## Il problema che tutti abbiamo (ma nessuno ammette)

Sei un programmatore nel 2025. Usi Claude, ChatGPT, o qualsiasi altro LLM **ogni 20 secondi**. E ogni volta è la stessa storia:

- Devi mandare 5-10 file all'LLM per context
- Apri il primo file → Ctrl+A → Ctrl+C → vai nel chat → Ctrl+V
- "Ah no, devo dire qual è il nome del file"
- Torni indietro → copi il path → incolli prima del codice
- Ripeti per tutti i file
- Dopo 10 minuti hai un prompt che sembra vomito di gatto
- L'LLM ti risponde con codice modificato
- Ora devi **rifare tutto al contrario**: copiare ogni pezzo di codice dall'LLM e salvarlo nel file giusto
- Ti sbagli, sovrascrivi la versione sbagliata, bestemmie

**Questo 20 volte al giorno.**

Se ti riconosci in questa descrizione, pak4.py è nato per te.

## Pak3: la soluzione che avresti dovuto inventare tu

Pak3 è un tool da riga di comando che risolve **esattamente** questo problema. In modo elegante, veloce, e senza rompere le scatole.

### Il workflow prima di pak4.py
```
1. Apri file1.py → copia → incolla nel chat con "File: file1.py"
2. Apri file2.js → copia → incolla nel chat con "File: file2.js"  
3. Apri file3.css → copia → incolla nel chat con "File: file3.css"
4. Scrivi la tua domanda
5. LLM risponde con codice modificato
6. Copi manualmente ogni pezzo e lo salvi nel file giusto
7. Speri di non aver fatto casino
```

**Tempo**: ~15 minuti di lavoro noioso  
**Errori**: Garantiti  
**Frustrazione**: Massima

### Il workflow con pak4.py
```bash
# Impacchetta tutto
pak4.py --compress-level smart src/ > progetto.pak

# Incolli il contenuto di progetto.pak nel chat + la tua domanda
# LLM risponde con un nuovo file .pak

# Scompatti la risposta
pak4.py --unpack risposta.pak --outdir ./updated
```

**Tempo**: 30 secondi  
**Errori**: Zero  
**Frustrazione**: Zero

## Come funziona pak4.py nella pratica

### Esempio reale: Refactoring di un componente React

Hai una directory con questi file:
```
src/
├── components/
│   ├── UserCard.jsx
│   ├── UserCard.css
│   └── UserCard.test.js
├── hooks/
│   └── useUser.js
└── utils/
    └── formatters.js
```

**Senza pak4.py:**
1. Apri 5 file
2. Copia-incolla ognuno nel chat
3. Scrivi: "Converti questo componente per usare TypeScript"
4. LLM risponde con 5 blocchi di codice
5. Copi manualmente ogni blocco nel file giusto
6. Rinomini i file da .js a .ts/.tsx
7. Controlli che non hai fatto errori

**Con pak4.py:**
```bash
# Impacchetta
pak4.py --compress-level medium src/ --ext .jsx .js .css > componente.pak

# Nel chat:
# [incolli contenuto di componente.pak]
# "Converti tutto a TypeScript e ottimizza le performance"

# LLM risponde con nuovo file .pak
# Lo salvi come typescript.pak

# Scompatti
pak4.py --unpack typescript.pak --outdir ./src-updated
```

Risultato: hai una directory `src-updated/` con tutti i file convertiti, ottimizzati, e già rinominati correttamente.

### Esempio 2: Debug di un bug complesso

Il tuo backend Node.js ha un bug che coinvolge più file. Invece di copiare manualmente:

```bash
# Impacchetta solo i file rilevanti
pak4.py --compress-level aggressive \
     server.js \
     routes/auth.js \
     middleware/validation.js \
     models/User.js \
     > bug-context.pak
```

Nel chat incolli il contenuto + "C'è un bug nell'autenticazione, l'utente viene loggato anche se il token è scaduto".

L'LLM vede **tutto il context** necessario in un colpo solo e può dare una risposta precisa.

### Esempio 3: Code review collaborativo

Il tuo collega ti chiede di revieware una feature. Invece di mandare link GitHub:

```bash
# Impacchetta la feature
pak4.py --compress-level light feature-branch/ --ext .py .sql > feature-review.pak
```

Mandi il file `.pak` al collega, che può:
1. Leggerlo direttamente (è testo semplice)
2. Scompattarlo per testare localmente
3. Mandarlo all'LLM per analysis automatica

## Perché pak4.py è geniale per il workflow LLM

### 1. **Formato LLM-native**

Il formato `.pak` è **progettato** per essere capito dagli LLM:

```
__PAK_FILE_abc123_START__
Path: src/components/Button.jsx
Language: javascript
Size: 1847
Lines: 67
Tokens: 425
Compression: medium
Method: AST-enabled
__PAK_DATA_abc123_START__
import React from 'react';
import './Button.css';

export const Button = ({ children, variant = 'primary', ...props }) => {
  return (
    <button className={`btn btn-${variant}`} {...props}>
      {children}
    </button>
  );
};
__PAK_DATA_abc123_END__
```

L'LLM sa **esattamente**:
- Che file è
- Che linguaggio è
- Quanto è grande  
- Come è stato compresso

E può **riprodurre lo stesso formato** quando ti risponde.

### 2. **Compressione intelligente**

Pak3 non è stupido. Con `--compress-level smart`:
- **README.md** → mantiene tutto (importante per context)
- **main.py** → mantiene tutto (file principale)
- **utils.py** → comprime i commenti ma mantiene la logica
- **test_*.py** → comprime aggressivamente (spesso non serve tutto)

### 3. **Gestione automatica dei token**

```bash
pak4.py --compress-level smart --max-tokens 8000 huge-project/
```

Pak3 **prioritizza automaticamente** i file più importanti e si ferma quando raggiunge il limite di token. Non devi più contare caratteri o preoccuparti di sforare il context window.

### 4. **Fallback robusto**

Se pak4.py non riesce a fare parsing AST di un file (per qualsiasi motivo), **non crasha**. Passa automaticamente alla compressione testuale. Il workflow non si interrompe mai.

## Setup: 5 minuti per sempre

### Installazione
```bash
# Scarica pak4.py
curl -O https://raw.githubusercontent.com/pakkio/pak/main/pak4.py
chmod +x pak4.py
sudo mv pak4.py /usr/local/bin/

# Verifica che funzioni
pak4.py --version
```

### Dipendenze (opzionali ma raccomandate)
```bash
# Per la compressione AST avanzata
pip3 install --user tree-sitter tree-sitter-languages tree-sitter-python

# Verifica supporto AST
pak4.py --ast-info
```

Se non installi le dipendenze Python, pak4.py **funziona comunque** con compressione testuale. L'AST è un bonus, non un requisito.

## I comandi che usi davvero

### Impacchettamento base
```bash
# Tutto il progetto
pak4.py src/ > progetto.pak

# Solo file specifici
pak4.py main.py utils.py config.yaml > core.pak

# Solo certi tipi di file
pak4.py --ext .py .md ./mio-progetto > python-docs.pak
```

### Compressione intelligente
```bash
# Leggera: rimuove spazi vuoti e commenti banali
pak4.py --compress-level light src/ > light.pak

# Media: mantiene struttura ma comprime implementazioni
pak4.py --compress-level medium src/ > medium.pak

# Aggressiva: solo signature e API pubbliche
pak4.py --compress-level aggressive src/ > minimal.pak

# Smart: sceglie automaticamente in base all'importanza del file
pak4.py --compress-level smart --max-tokens 12000 src/ > smart.pak
```

### Scompattamento
```bash
# Nella directory corrente
pak4.py --unpack risposta.pak

# In una directory specifica
pak4.py --unpack risposta.pak --outdir ./nuova-versione

# Verifica cosa c'è dentro prima di scompattare
pak4.py --ls risposta.pak
```

## Casi d'uso quotidiani

### 1. **Refactoring guidato**
"Prendi questi 10 file e convertili da Class Components a Function Components con hooks"

### 2. **Bug hunting**
"C'è un memory leak da qualche parte in questi moduli, aiutami a trovarlo"

### 3. **Code review automatico**
"Analizza questa pull request e dimmi se ci sono problemi di security o performance"

### 4. **Documentazione automatica**
"Genera documentazione API per questi endpoint"

### 5. **Migration assistita**
"Migra questo progetto da Python 3.8 a 3.12, aggiorna le dependency deprecate"

### 6. **Ottimizzazione performance**
"Questi componenti React renderizzano troppo spesso, ottimizzali"

### 7. **Test generation**
"Genera unit test per tutte queste funzioni"

### 8. **Architettura review**
"Questo codice è ben strutturato? Suggerisci miglioramenti architetturali"

## Confronti onesti

### vs. Copia-incolla manuale
**Pak3 vince sempre.** Non c'è gara.

### vs. Script personalizzato
Se hai già uno script che fa la stessa cosa e sei soddisfatto, continua a usarlo. Ma pak4.py probabilmente gestisce più edge cases e linguaggi del tuo script.

### vs. GitHub + link agli LLM
- **Pro GitHub**: Nessun setup locale
- **Pro pak4.py**: Funziona offline, più veloce, controllo totale sul context

### vs. Tool enterprise (LLMLingua, ecc.)
- **Pro enterprise**: Compressione più sofisticata matematicamente
- **Pro pak4.py**: Gratis, offline, zero setup, zero dipendenze da API

Per l'uso quotidiano personale, pak4.py **vince per praticità**.

## Limiti onesti

### 1. **Non è magia**
Se il tuo progetto ha 100k linee di codice, pak4.py non può comprimerlo in 1000 token mantenendo tutto il context. Devi essere selettivo.

### 2. **Dipendenze Python per AST**
Per la compressione avanzata serve Python + tree-sitter. Su ambienti molto ristretti potresti dover usare solo compressione testuale.

### 3. **Non sostituisce la comprensione**
Pak3 ti aiuta a **preparare** il context per l'LLM, ma devi comunque sapere **cosa chiedere** e **come interpretare** le risposte.

### 4. **Funziona meglio su progetti strutturati**
Se il tuo codice è un casino totale senza structure, pak4.py non può fare miracoli nella prioritizzazione.

## Trucchi e tips

### 1. **Usa alias per workflow comuni**
```bash
# Nel tuo .bashrc/.zshrc
alias pak-quick='pak4.py --compress-level smart --max-tokens 8000'
alias pak-review='pak4.py --compress-level medium --ext .py .js .ts'
alias pak-minimal='pak4.py --compress-level aggressive'
```

### 2. **Combina con altri tool**
```bash
# Solo file modificati di recente
git diff --name-only HEAD~5 | xargs pak4.py > recent-changes.pak

# Solo file che contengono una certa funzione  
grep -r "getUserData" src/ | cut -d: -f1 | sort -u | xargs pak4.py > user-data-logic.pak
```

### 3. **Template per richieste comuni**
Crea file template che includi nelle richieste:
```bash
pak4.py src/ > codebase.pak
cat codebase.pak refactoring-prompt-template.txt > full-request.txt
```

### 4. **Backup before unpack**
```bash
# Sempre backup prima di scompattare su codice esistente
cp -r src/ src-backup/
pak4.py --unpack new-version.pak --outdir src/
```

## Conclusione: il tool che non sapevi di volere

Pak3 è uno di quei tool che sembra **ovvio dopo** che lo usi. Ti chiedi come hai fatto senza per tutto questo tempo.

Non rivoluziona il mondo. Non usa AI. Non ha una startup da miliardi dietro.

**Semplicemente funziona.** Risolve un problema quotidiano fastidioso in modo elegante e affidabile.

Se lavori con LLM quotidianamente, scaricalo. Provalo per una settimana. Se non ti semplifica la vita, hai perso 5 minuti. Se ti semplifica la vita, hai guadagnato ore ogni settimana per sempre.

È gratis, è open source, e il tuo workflow con gli LLM non sarà più lo stesso.

**Download**: https://github.com/pakkio/pak  
**Tempo di setup**: 5 minuti  
**ROI**: Infinito
