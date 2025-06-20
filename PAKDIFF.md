# pakdiff Format Specification v4.3.0

## Overview

The **pakdiff** format is a **method-level** diff format designed for granular code changes. Unlike traditional line-based diffs, pakdiff operates at the **method/function** level, allowing precise modifications, additions, and deletions.

**v4.3.0 Enhancements:**
- Added `GLOBAL_PREAMBLE` section support for module-level changes
- Enhanced decorator handling in method boundaries
- Support for import statements, global variables, and constants

## Format Structure

### Basic Schema

**Method-level changes:**
```
FILE: path/to/file.extension
FIND_METHOD: method_signature_to_find
UNTIL_EXCLUDE: next_method_signature_or_empty
REPLACE_WITH:
full_replacement_code
```

**Global section changes (v4.3.0):**
```
FILE: path/to/file.extension
SECTION: GLOBAL_PREAMBLE
UNTIL_EXCLUDE: def first_method
REPLACE_WITH:
import statements
global variables
module constants
```

### Block Separator

Each change is separated by **a blank line**. No additional separators are allowed.

## Operation Types

### 1. **Global Section Changes** (v4.3.0)

**Python example:**
```diff
FILE: api_client.py
SECTION: GLOBAL_PREAMBLE
UNTIL_EXCLUDE: class APIClient
REPLACE_WITH:
import requests
import json
from datetime import datetime
from typing import Dict, Any, Optional

# Updated API configuration
API_BASE_URL = "https://api.example.com/v2"
DEFAULT_TIMEOUT = 30
RETRY_ATTEMPTS = 3

# Global logger setup
logger = setup_logger(__name__)
```

**C++ example:**
```diff
FILE: network_client.cpp
SECTION: GLOBAL_PREAMBLE
UNTIL_EXCLUDE: class NetworkClient
REPLACE_WITH:
#include <iostream>
#include <string>
#include <memory>
#include <chrono>
#include "network_client.h"
#include "logger.h"

using namespace std;
using namespace chrono;

// Global configuration constants
constexpr int DEFAULT_TIMEOUT_MS = 30000;
constexpr int MAX_RETRY_ATTEMPTS = 3;
const string API_BASE_URL = "https://api.example.com/v2";

// Global logger instance
static auto logger = Logger::getInstance();
```

### 2. **Modify Existing Method**

**Python example:**
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

**C++ example:**
```diff
FILE: calculator.cpp
FIND_METHOD: double Calculator::add(double a, double b)
UNTIL_EXCLUDE: double Calculator::subtract(double a, double b)
REPLACE_WITH:
double Calculator::add(double a, double b) {
    // Enhanced addition with logging and error checking
    if (!isfinite(a) || !isfinite(b)) {
        throw std::invalid_argument("Invalid input: non-finite values");
    }
    
    double result = a + b;
    logger->info("ADD: {} + {} = {}", a, b, result);
    history.push_back({Operation::ADD, a, b, result});
    
    return round(result * precision) / precision;
}
```

### 3. **Decorator Changes** (Enhanced v4.3.0)

```diff
FILE: models.py
FIND_METHOD: def get_name(self)
UNTIL_EXCLUDE: def set_name(self, value)
REPLACE_WITH:
def get_name(self):
    """Get name without property decorator"""
    return self._name
```

### 4. **Add New Method** (Append)

```diff
FILE: calculator.py
FIND_METHOD: 
UNTIL_EXCLUDE: 
REPLACE_WITH:
def new_method(self):
    """This method will be appended at the end"""
    return "new functionality"
```

### 5. **Mixed Global and Method Changes**

```diff
FILE: config.py
SECTION: GLOBAL_PREAMBLE
UNTIL_EXCLUDE: def load_config
REPLACE_WITH:
import os
from pathlib import Path

VERSION = "2.1.0"
CONFIG_FILE = Path.home() / ".app" / "config.json"

FILE: config.py
FIND_METHOD: def load_config(self)
UNTIL_EXCLUDE: def save_config
REPLACE_WITH:
def load_config(self):
    """Load configuration with new version support"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            config = json.load(f)
            config.setdefault('version', VERSION)
            return config
    return {'version': VERSION}
```

## Enhanced Features (v4.3.0)

### Global Section Support

- **SECTION: GLOBAL_PREAMBLE** - Handles module-level changes
- **Auto-boundary detection** - Finds first class/function if no UNTIL_EXCLUDE
- **Import management** - Track import statement changes
- **Global variables** - Handle module constants and configuration

### Enhanced Method Boundary Detection

- **Decorator inclusion** - Automatically includes decorators with methods
- **Backward scanning** - Finds decorators above method definitions
- **Proper replacement** - Replaces entire method including decorators

### Processing Order

1. **Global sections first** - Apply GLOBAL_PREAMBLE changes
2. **Method sections second** - Apply method-level changes
3. **File-by-file processing** - Complete each file before next

## Backward Compatibility

- **v4.1.0 format** - Fully supported (SECTION defaults to METHOD)
- **Legacy diffs** - Work unchanged with enhanced processor
- **Optional keywords** - SECTION directive is optional

## Implementation Notes

### Decorator Bug Fix

The enhanced format fixes the decorator removal bug by:
- Including decorators in method boundary detection
- Scanning backwards from method signature to find decorators
- Replacing entire decorator+method block as unit

### Global Section Extraction

- Detects changes in module preamble (before first class/function)
- Extracts import modifications, global variable changes
- Generates GLOBAL_PREAMBLE sections automatically

## LLM Integration Guidelines

When working with LLMs to generate pakdiff format, use these prompts for optimal results:

### Analysis Prompt Template

```
You are a code analysis expert. Given two versions of a codebase, generate a pakdiff v4.3.0 format diff.

**Instructions:**
1. Identify ALL changes between the codebases (files, methods, global sections)
2. Use GLOBAL_PREAMBLE sections for: imports, includes, using statements, global variables, constants
3. Use FIND_METHOD for specific method/function changes
4. Include decorators and access modifiers in method signatures
5. Use proper UNTIL_EXCLUDE boundaries for each change

**Supported Languages:** Python, JavaScript, Java, C++, C
**Supported Section Types:** GLOBAL_PREAMBLE, METHOD (default)

**Output Format:** Valid pakdiff v4.3.0 with FILE:, SECTION:, FIND_METHOD:, UNTIL_EXCLUDE:, REPLACE_WITH: blocks

**Multi-language examples in pakdiff format are provided in the specification.**
```

### Validation Prompt Template

```
You are validating a pakdiff v4.3.0 format file. Check for:

**Format Requirements:**
- Each change starts with FILE: path/to/file.extension
- SECTION: GLOBAL_PREAMBLE for module-level changes (optional, defaults to METHOD)
- FIND_METHOD: signature for modifications (empty for additions)
- UNTIL_EXCLUDE: boundary signature (optional)
- REPLACE_WITH: new content (can be empty for deletions)
- Blank line separates each change block

**Language-Specific Validation:**
- Python: def/class signatures, import statements
- C++: function signatures with types, #include directives, namespace/using statements
- Java: method signatures with access modifiers, import statements
- JavaScript: function signatures, import/export statements

**Report:** Any format violations, missing required fields, or syntax errors
```

### Exhaustive Mode Prompt

```
Generate a comprehensive pakdiff covering ALL differences between two project versions.

**Process:**
1. **File Discovery:** Identify all changed, added, deleted files
2. **Global Analysis:** Compare imports, includes, global variables, constants
3. **Method Analysis:** Compare all functions, methods, classes
4. **Template Generation:** Create pakdiff blocks for each identified change

**Priority Order:**
1. GLOBAL_PREAMBLE sections first
2. Core class/struct definitions
3. Method implementations
4. Utility functions

**Output:** Complete pakdiff v4.3.0 format that transforms codebase_v1 → codebase_v2
```

## Configuration Files and INI Support

For configuration files (INI, YAML, JSON, TOML), the standard GLOBAL_PREAMBLE approach may not be ideal. Consider these alternative section types:

### INI Files

```diff
FILE: config.ini
SECTION: INI_SECTION
SECTION_NAME: [database]
REPLACE_WITH:
host = localhost
port = 5432
username = newuser
password = newpass
timeout = 30

FILE: config.ini
SECTION: INI_SECTION
SECTION_NAME: [cache]
REPLACE_WITH:
enabled = true
redis_url = redis://localhost:6379
ttl = 3600
```

### YAML Files

```diff
FILE: config.yaml
SECTION: YAML_PATH
PATH: database.connection
REPLACE_WITH:
host: localhost
port: 5432
ssl: true
pool_size: 10
```

### Alternative: Use FIND_METHOD with Section Headers

```diff
FILE: app.ini
FIND_METHOD: [database]
UNTIL_EXCLUDE: [logging]
REPLACE_WITH:
[database]
host = newhost.example.com
port = 5432
ssl_enabled = true
```

These specialized section types could be implemented as future enhancements to handle structured configuration files more naturally.

## Compatibility

This pakdiff v4.3.0 format is compatible with pak tool v5.0.0 and later.
