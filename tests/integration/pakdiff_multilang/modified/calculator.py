#!/usr/bin/env python3
"""
Enhanced calculator module for testing pakdiff format.
Now supports advanced operations and better logging.
"""

import math
import logging
from typing import List, Union
from decimal import Decimal

# Updated global configuration
DEFAULT_PRECISION = 4
LOG_LEVEL = "DEBUG"
ENABLE_HISTORY = True

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, LOG_LEVEL))

def precision(self):
    """Get calculation precision (decorator removed)."""
    return self._precision

class Calculator:
    """Enhanced calculator with history tracking and validation."""
    
    def __init__(self, precision=DEFAULT_PRECISION):
        self._precision = precision
        self.history = []
        self.operation_count = 0
    
    def add(self, a, b):
        """Add two numbers with enhanced logging."""
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            raise TypeError("Arguments must be numeric")
        
        result = a + b
        self.operation_count += 1
        
        if ENABLE_HISTORY:
            self.history.append(f"ADD: {a} + {b} = {result} (op #{self.operation_count})")
            logger.debug(f"Addition performed: {a} + {b} = {result}")
        
        return round(result, self._precision)
    
    def multiply(self, a, b):
        """Multiply two numbers with validation."""
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            raise TypeError("Arguments must be numeric")
            
        result = a * b
        self.operation_count += 1
        
        if ENABLE_HISTORY:
            self.history.append(f"MUL: {a} * {b} = {result} (op #{self.operation_count})")
            logger.debug(f"Multiplication performed: {a} * {b} = {result}")
        
        return round(result, self._precision)
    
    def divide(self, a, b):
        """Divide two numbers with zero-division protection."""
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            raise TypeError("Arguments must be numeric")
        
        if b == 0:
            raise ZeroDivisionError("Cannot divide by zero")
        
        result = a / b
        self.operation_count += 1
        
        if ENABLE_HISTORY:
            self.history.append(f"DIV: {a} / {b} = {result} (op #{self.operation_count})")
            logger.debug(f"Division performed: {a} / {b} = {result}")
        
        return round(result, self._precision)

def create_calculator(precision=None):
    """Enhanced factory function for calculator."""
    if precision is None:
        precision = DEFAULT_PRECISION
    return Calculator(precision)