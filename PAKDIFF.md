# pakdiff Format Specification v4.1.0

## Overview

The **pakdiff** format is a **method-level** diff format designed for granular code changes. Unlike traditional line-based diffs, pakdiff operates at the **method/function** level, allowing precise modifications, additions, and deletions.

## Format Structure

### Basic Schema

```
FILE: path/to/file.extension
FIND_METHOD: method_signature_to_find
UNTIL_EXCLUDE: next_method_signature_or_empty
REPLACE_WITH:
full_replacement_code
```

### Block Separator

Each change is separated by **a blank line**. No additional separators are allowed.

## Operation Types

### 1. **Modify Existing Method**

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

### 2. **Add New Method** (Append)

```diff
FILE: calculator.py
FIND_METHOD: 
UNTIL_EXCLUDE: 
REPLACE_WITH:
def new_method(self):
    """This method will be appended at the end"""
    return "new functionality"
```

## Compatibility

This pakdiff v4.1.0 format is compatible with pak tool v5.0.0 and later.
