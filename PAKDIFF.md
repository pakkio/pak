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

### 2. **Modify Existing Method**

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

## Compatibility

This pakdiff v4.3.0 format is compatible with pak tool v5.0.0 and later.
