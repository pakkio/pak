# Specifica Formato pak4diff v4.1.0

## Panoramica

Il formato **pak4diff** è un formato di diff **method-level** progettato per modifiche granulari di codice. A differenza dei diff tradizionali basati su righe, pak4diff opera a livello di **metodi/funzioni**, permettendo modifiche, aggiunte e cancellazioni precise.

## Struttura del Formato

### Schema Base

```
FILE: percorso/del/file.estensione
FIND_METHOD: signature_metodo_da_trovare
UNTIL_EXCLUDE: signature_prossimo_metodo_o_vuoto
REPLACE_WITH:
codice_di_sostituzione_completo
```

### Blocco Separatore

Ogni modifica è separata da **una riga vuota**. Non sono permessi separatori aggiuntivi.

## Tipi di Operazioni

### 1. **Modifica Metodo Esistente**

```diff
FILE: calculator.py
FIND_METHOD: def add(self, a, b)
UNTIL_EXCLUDE: def subtract(self, a, b)
REPLACE_WITH:
def add(self, a, b):
    """Enhanced addition with logging"""
    result = a + b
    self.history.append(f"ADD: {a} + {b} = {result}")
    return round(result, self.precision)
```

### 2. **Aggiunta Nuovo Metodo** (Append)

```diff
FILE: calculator.py
FIND_METHOD: 
UNTIL_EXCLUDE: 
REPLACE_WITH:
def new_method(self):
    """This method will be appended at the end"""
    return "new functionality"
```

**Regola**: `FIND_METHOD` e `UNTIL_EXCLUDE` **vuoti** = aggiunta alla fine del file.

### 3. **Cancellazione Metodo**

```diff
FILE: calculator.py
FIND_METHOD: def old_method(self)
UNTIL_EXCLUDE: def next_method(self)
REPLACE_WITH:
# Method deleted
```

**Regola**: `REPLACE_WITH` contenente solo commento = cancellazione.

### 4. **Inserimento Prima di un Metodo**

```diff
FILE: calculator.py
FIND_METHOD: 
UNTIL_EXCLUDE: def existing_method(self)
REPLACE_WITH:
def new_method_before(self):
    """Inserted before existing_method"""
    pass
```

**Regola**: `FIND_METHOD` vuoto + `UNTIL_EXCLUDE` specificato = inserimento prima del metodo target.

## Signature Matching per Linguaggio

### Python

**Formato**: `def nome_metodo(parametri):`

```python
# ✅ Corretti
FIND_METHOD: def __init__(self)
FIND_METHOD: def calculate(self, a, b)
FIND_METHOD: def process_data(self, data, options=None)

# ❌ Errori comuni
FIND_METHOD: def __init__(self):  # NO: include i due punti
FIND_METHOD: __init__             # NO: manca 'def'
```

### JavaScript

**Formato**: `function nome_funzione` o `nome_metodo` (per metodi di classe)

```javascript
// ✅ Corretti per funzioni
FIND_METHOD: function calculateSum
FIND_METHOD: function main()

// ✅ Corretti per metodi di classe
FIND_METHOD: constructor
FIND_METHOD: add
FIND_METHOD: getResult

// ❌ Errori comuni
FIND_METHOD: function add() {     // NO: include le parentesi graffe
FIND_METHOD: add()                // NO: include le parentesi per metodi di classe
```

### Java

**Formato**: `nome_metodo(tipo parametri)` o `Classe()` per costruttori

```java
// ✅ Corretti
FIND_METHOD: Calculator()
FIND_METHOD: add(int a, int b)
FIND_METHOD: processData(String data, boolean flag)
FIND_METHOD: main(String[] args)

// ❌ Errori comuni
FIND_METHOD: public int add(int a, int b)  // NO: include modificatori
FIND_METHOD: add(a, b)                     // NO: mancano i tipi
```

## Regole di Path e File

### Path Resolution

- **Path relativi**: Sempre relativi alla directory di applicazione
- **Path nel diff**: Possono contenere directory (`src/main/Calculator.java`)
- **Matching**: Il path nel diff viene matchato con i file esistenti

```diff
# Esempi validi
FILE: calculator.py
FILE: src/main/Calculator.java
FILE: lib/utils/helper.js
FILE: ../parent/file.py
```

### Gestione Multi-File

Un singolo file `.diff` può contenere modifiche per **multipli file**:

```diff
FILE: calculator.py
FIND_METHOD: def add(self, a, b)
UNTIL_EXCLUDE: def subtract(self, a, b)
REPLACE_WITH:
def add(self, a, b):
    return a + b

FILE: utils.py
FIND_METHOD: def helper_function()
UNTIL_EXCLUDE: 
REPLACE_WITH:
def helper_function():
    return "modified"
```

## Conversione da Altri Formati

### Da Unified Diff Standard

**Input** (unified diff):
```diff
--- original.py
+++ modified.py
@@ -5,8 +5,12 @@
 
 class Calculator:
     def add(self, a, b):
-        return a + b
+        """Enhanced addition"""
+        result = a + b
+        self.log(f"Added {a} + {b} = {result}")
+        return result
     
     def subtract(self, a, b):
```

**Output** (pak4diff):
```diff
FILE: original.py
FIND_METHOD: def add(self, a, b)
UNTIL_EXCLUDE: def subtract(self, a, b)
REPLACE_WITH:
def add(self, a, b):
    """Enhanced addition"""
    result = a + b
    self.log(f"Added {a} + {b} = {result}")
    return result
```

### Da Git Diff

**Algoritmo di Conversione**:

1. **Parse** le sezioni `@@` per identificare metodi modificati
2. **Estrai** signature dei metodi dal codice
3. **Identifica** il prossimo metodo per `UNTIL_EXCLUDE`
4. **Genera** il blocco `REPLACE_WITH` con il codice completo

### Da Side-by-Side Comparison

**Processo**:

1. **AST parsing** di entrambi i file
2. **Confronto** metodo per metodo
3. **Identificazione** di: modificati, aggiunti, cancellati
4. **Generazione** dei blocchi pak4diff corrispondenti

## Gestione Caratteri Speciali

### Backtick Tripli (```) - REGOLA CRITICA

**Problema**: I file pak4diff possono contenere codice con backtick tripli (```), che interferiscono con il wrapping markdown.

**Soluzione Obbligatoria**:
1. **Sostituisci** tutti i ``` nel contenuto con `xxx`
2. **Applica** solo al contenuto dentro `REPLACE_WITH:`
3. **NON modificare** le sezioni `FILE:`, `FIND_METHOD:`, `UNTIL_EXCLUDE:`
4. **Segnala** al termine quali file sono stati modificati

**Esempio di Sostituzione**:

```diff
FILE: documentation.py
FIND_METHOD: def generate_docs(self)
UNTIL_EXCLUDE: def save_docs(self)
REPLACE_WITH:
def generate_docs(self):
    """Generate documentation with code examples"""
    markdown_content = '''
    # Example
    xxx
    def sample_function():
        pass
    xxx
    '''
    return markdown_content
```

**Segnalazione Obbligatoria**:
```
⚠️  SOSTITUZIONE BACKTICK EFFETTUATA:
    - documentation.py: 2 occorrenze di ``` → xxx
    - readme_generator.py: 1 occorrenza di ``` → xxx

💡 Per ripristinare: sostituire xxx con ``` nei file sopra indicati.
```

### Template per LLM

**Quando generi pak4diff, usa questo workflow**:

```python
# Pseudocodice per LLM
def generate_pak4diff(content):
    files_with_substitutions = []
    
    for block in content_blocks:
        if "REPLACE_WITH:" in block:
            original_backticks = block.count("```")
            if original_backticks > 0:
                block = block.replace("```", "xxx")
                files_with_substitutions.append({
                    'file': extract_filename(block),
                    'count': original_backticks
                })
    
    # Genera il pak4diff
    output_diff = generate_diff_content(content)
    
    # Aggiungi segnalazione se necessario
    if files_with_substitutions:
        output_diff += "\n⚠️  SOSTITUZIONE BACKTICK EFFETTUATA:\n"
        for file_info in files_with_substitutions:
            output_diff += f"    - {file_info['file']}: {file_info['count']} occorrenze di ``` → xxx\n"
        output_diff += "\n💡 Per ripristinare: sostituire xxx con ``` nei file sopra indicati.\n"
    
    return output_diff
```

## Best Practices per LLM

### ✅ Buone Pratiche

1. **Preserva indentazione** originale del file target
2. **Mantieni stile** di codice consistente
3. **Include commenti** appropriati per cancellazioni
4. **Verifica signature** con parser AST quando possibile
5. **Testa applicazione** prima di generare
6. **Gestisci backtick** secondo le regole sopra
7. **Segnala sempre** le sostituzioni effettuate

### ❌ Errori da Evitare

1. **Non includere** whitespace trailing nelle signature
2. **Non usare** signature parziali o ambigue
3. **Non mescolare** stili di indentazione (tab/space)
4. **Non includere** modificatori di visibilità nelle signature Java
5. **Non dimenticare** la riga vuota tra blocchi
6. **Non lasciare** backtick tripli nel contenuto senza sostituirli
7. **Non omettere** la segnalazione delle sostituzioni

## Esempio Completo Multi-Linguaggio

```diff
FILE: src/Calculator.py
FIND_METHOD: def __init__(self)
UNTIL_EXCLUDE: def add(self, a, b)
REPLACE_WITH:
def __init__(self):
    """Enhanced constructor with history tracking"""
    self.history = []
    self.precision = 2

FILE: src/Calculator.py
FIND_METHOD: def add(self, a, b)
UNTIL_EXCLUDE: def subtract(self, a, b)
REPLACE_WITH:
def add(self, a, b):
    """Add with logging"""
    result = a + b
    self.history.append(f"ADD: {a} + {b} = {result}")
    return round(result, self.precision)

FILE: src/documentation_generator.py
FIND_METHOD: def generate_readme(self)
UNTIL_EXCLUDE: def save_file(self)
REPLACE_WITH:
def generate_readme(self):
    """Generate README with code examples"""
    content = '''# Calculator Library
    
## Usage Example

xxx
from calculator import Calculator

calc = Calculator()
result = calc.add(5, 3)
print(f"Result: {result}")
xxx

## Installation

xxx
pip install calculator-lib
xxx
'''
    return content

FILE: src/calculator.js
FIND_METHOD: constructor
UNTIL_EXCLUDE: add
REPLACE_WITH:
constructor() {
    /** Enhanced constructor with history */
    this.history = [];
    this.precision = 2;
}

FILE: src/Calculator.java
FIND_METHOD: Calculator()
UNTIL_EXCLUDE: add(int a, int b)
REPLACE_WITH:
Calculator() {
    /** Enhanced constructor with history tracking */
    this.history = new ArrayList<>();
    this.precision = 2;
}
```

⚠️  **SOSTITUZIONE BACKTICK EFFETTUATA**:
    - src/documentation_generator.py: 4 occorrenze di ``` → xxx

💡 **Per ripristinare**: sostituire xxx con ``` nel file src/documentation_generator.py

## Validazione e Testing

### Verifica Syntax

```bash
pak4 -vd changes.diff
```

**Output atteso**:
```
✓ Method diff file is valid: N diffs found
  - file.py: method_name
  - file.py: [new method]
```

### Test di Applicazione

```bash
# Test dry-run (se supportato)
pak4 -ad changes.diff target_dir/ --dry-run

# Applicazione effettiva
pak4 -ad changes.diff target_dir/
```

## Troubleshooting Comune

### Problema: "Applied 0 of N method diffs"

**Cause possibili**:
1. **Signature mismatch**: Verifica che le signature nel diff matchino esattamente quelle nel file target
2. **Path issues**: Controlla che i path dei file siano corretti
3. **Encoding**: Assicurati che tutti i file usino lo stesso encoding (UTF-8)

**Debug**:
```bash
# Confronta signature
grep "def " target_file.py
grep "FIND_METHOD:" diff_file.diff
```

### Problema: Indentazione Incorretta

**Soluzione**: Mantieni l'indentazione originale del file target. Il parser rispetta lo stile esistente.

### Problema: Metodi Non Trovati

**Causa**: Signature incomplete o con whitespace extra.

**Fix**: Usa signature minime ma uniche:
- ✅ `def calculate(self, a, b)`  
- ❌ `def calculate(self, a, b):`

### Problema: Errori di Parsing con Markdown

**Causa**: Backtick tripli (```) nel contenuto causano conflitti con wrapping markdown.

**Soluzione**: 
1. Sempre sostituire ``` con xxx nel contenuto
2. Verificare la segnalazione di sostituzione
3. Ripristinare manualmente dopo l'applicazione se necessario

**Verifica**:
```bash
# Controlla sostituzioni nel diff
grep -n "xxx" changes.diff
grep -n "SOSTITUZIONE BACKTICK" changes.diff
```

---

*Questa specifica è compatibile con pak4 v4.1.0 e successivi. Per aggiornamenti, consultare il repository ufficiale.*
