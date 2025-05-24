#!/usr/bin/env python3
import re
import sys

def extract_python_structure(file_path):
    """Enhanced Python structure extraction"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file for text-based aggressive compression: {e}", file=sys.stderr)
        return ''

    lines = content.split('\n')
    result = []

    # Extract imports
    for line in lines:
        line = line.strip()
        if line.startswith('import ') or line.startswith('from '):
            result.append(line)

    result.append('')  # Empty line separator

    # Extract classes with methods
    in_class = False
    current_class = ''
    class_methods = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Class definition
        if stripped.startswith('class '):
            if in_class and class_methods:
                # Finish previous class
                result.append(f'class {current_class}:')
                for method in class_methods:
                    result.append(f'    {method}')
                result.append('')

            # Start new class
            class_match = re.match(r'class\s+(\w+)', stripped)
            if class_match:
                current_class = class_match.group(1)
                in_class = True
                class_methods = []

        # Method definition (inside class)
        elif in_class and stripped.startswith('def '):
            method_match = re.match(r'def\s+([^(]+\([^)]*\))', stripped)
            if method_match:
                method_sig = method_match.group(1)
                # Add return type if present
                if ' -> ' in stripped:
                    return_type = stripped.split(' -> ')[1].split(':')[0].strip()
                    method_sig += f' -> {return_type}'
                method_sig += ': ...'
                class_methods.append(method_sig)

        # Standalone function
        elif not in_class and stripped.startswith('def '):
            func_match = re.match(r'def\s+([^(]+\([^)]*\))', stripped)
            if func_match:
                func_sig = func_match.group(1)
                if ' -> ' in stripped:
                    return_type = stripped.split(' -> ')[1].split(':')[0].strip()
                    func_sig += f' -> {return_type}'
                func_sig += ': ...'
                result.append(func_sig)

        # Constants and important assignments
        elif re.match(r'^[A-Z_][A-Z0-9_]*\s*=', stripped):
            result.append(stripped)

    # Finish last class if needed
    if in_class and class_methods:
        result.append(f'class {current_class}:')
        for method in class_methods:
            result.append(f'    {method}')

    return '\n'.join(result)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python_extractor.py <file_path>", file=sys.stderr)
        sys.exit(1)
    
    result = extract_python_structure(sys.argv[1])
    print(result)
