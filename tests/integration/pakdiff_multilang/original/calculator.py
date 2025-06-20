#!/usr/bin/env python3
"""
Simple calculator module for testing pakdiff format.
"""

import math
import logging

# Global configuration
DEFAULT_PRECISION = 2
LOG_LEVEL = "INFO"

logger = logging.getLogger(__name__)

@property
def precision(self):
    """Get calculation precision."""
    return self._precision

class Calculator:
    """Basic calculator with history tracking."""
    
    def __init__(self, precision=DEFAULT_PRECISION):
        self._precision = precision
        self.history = []
    
    def add(self, a, b):
        """Add two numbers."""
        result = a + b
        self.history.append(f"ADD: {a} + {b} = {result}")
        return result
    
    def multiply(self, a, b):
        """Multiply two numbers."""
        result = a * b
        self.history.append(f"MUL: {a} * {b} = {result}")
        return result

def create_calculator():
    """Factory function for calculator."""
    return Calculator()