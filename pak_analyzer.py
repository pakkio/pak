import ast
import re
from typing import List, Dict, Any, Optional, Union # Added Union
import subprocess
import tempfile
import os

class MultiLanguageAnalyzer:
    """
    Analyzes code structure using AST for multiple languages.
    Supports Python via built-in ast module and other languages via tree-sitter.
    """
    
    @staticmethod
    def compress_with_ast(content: str, language: str, level: str = "aggressive") -> str:
        """
        Compresses code using AST analysis.
        For Python: uses built-in ast module
        For other languages: delegates to ast_helper.py with tree-sitter
        
        Args:
            content: Source code content
            language: Language identifier (python, javascript, java, etc.)
            level: Compression level (light, medium, aggressive)
        
        Returns:
            Compressed code content
        """
        if language == "python":
            # Use Python-specific AST compression
            if level == "aggressive":
                structure = MultiLanguageAnalyzer.extract_structure(content)
                if "error" in structure:
                    return content  # Fallback to original on error
                return MultiLanguageAnalyzer._format_python_structure(structure)
            else:
                # For light/medium, delegate to ast_helper for consistency
                return MultiLanguageAnalyzer._compress_via_ast_helper(content, language, level)
        else:
            # Use tree-sitter via ast_helper for all non-Python languages
            return MultiLanguageAnalyzer._compress_via_ast_helper(content, language, level)
    
    @staticmethod
    def _compress_via_ast_helper(content: str, language: str, level: str) -> str:
        """
        Calls the frozen ast_helper binary as a subprocess for AST-based compression.
        Fallback to regex-based compression if the binary fails.
        """
        try:
            # Write content to a temporary file
            with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8', suffix='.txt') as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            # Find ast_helper binary (assume it's in the same dir as pak4 or in PATH)
            ast_helper_bin = os.environ.get('AST_HELPER_BIN', 'ast_helper')
            cmd = [ast_helper_bin, '--lang', language, '--level', level, tmp_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            os.unlink(tmp_path)
            if result.returncode == 0:
                return result.stdout
            else:
                return MultiLanguageAnalyzer._fallback_compression(content, language, level)
        except Exception as e:
            return MultiLanguageAnalyzer._fallback_compression(content, language, level)
    
    @staticmethod
    def _fallback_compression(content: str, language: str, level: str) -> str:
        """
        Regex-based compression fallback for when tree-sitter is unavailable.
        """
        if level == "light":
            # Remove single-line comments for common languages
            if language in ['javascript', 'java', 'c', 'cpp', 'csharp', 'go', 'rust']:
                # Remove // comments
                content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
            elif language in ['python']:
                # Remove # comments (but preserve shebangs)
                lines = content.split('\n')
                result_lines = []
                for line in lines:
                    if line.strip().startswith('#!'):  # Preserve shebangs
                        result_lines.append(line)
                    else:
                        result_lines.append(re.sub(r'#.*$', '', line))
                content = '\n'.join(result_lines)
            
            # Remove empty lines
            content = '\n'.join(line for line in content.split('\n') if line.strip())
            return content + f'\n# ... (Light compression via regex - {language})'
            
        elif level == "medium":
            # Remove comments and docstrings
            content = MultiLanguageAnalyzer._fallback_compression(content, language, "light")
            if language in ['javascript', 'java']:
                # Remove /* */ comments
                content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
            elif language == 'python':
                # Remove triple-quoted strings (basic regex)
                content = re.sub(r'""".*?"""', '', content, flags=re.DOTALL)
                content = re.sub(r"'''.*?'''", '', content, flags=re.DOTALL)
            return content + f'\n# ... (Medium compression via regex - {language})'
            
        elif level == "aggressive":
            # Extract function/class signatures only
            if language == 'javascript':
                # Extract class and function declarations
                signatures = []
                for line in content.split('\n'):
                    line = line.strip()
                    if (line.startswith('class ') or line.startswith('function ') or 
                        line.startswith('async function ') or 'function' in line or
                        line.startswith('import ') or line.startswith('export ')):
                        signatures.append(line.split('{')[0].strip() + ' { ... }')
                if signatures:
                    return '\n'.join(signatures) + f'\n# ... (Aggressive compression via regex - {language})'
                    
            elif language == 'java':
                # Extract class, method, and import declarations
                signatures = []
                for line in content.split('\n'):
                    line = line.strip()
                    if (line.startswith('public ') or line.startswith('private ') or 
                        line.startswith('protected ') or line.startswith('class ') or
                        line.startswith('interface ') or line.startswith('import ')):
                        signatures.append(line.split('{')[0].strip() + ' { ... }')
                if signatures:
                    return '\n'.join(signatures) + f'\n# ... (Aggressive compression via regex - {language})'
            
            elif language in ['cpp', 'c', 'cpp_header', 'c_header']:
                # Extract C++ class, function, and preprocessor declarations
                signatures = []
                for line in content.split('\n'):
                    line = line.strip()
                    # Include preprocessor directives, class/struct/namespace declarations, function signatures
                    if (line.startswith('#include') or line.startswith('#define') or 
                        line.startswith('#ifndef') or line.startswith('#endif') or
                        line.startswith('namespace ') or line.startswith('class ') or 
                        line.startswith('struct ') or line.startswith('template') or
                        line.startswith('using ') or line.startswith('typedef ') or
                        # Function-like patterns (simplified heuristic)
                        ('(' in line and ')' in line and not line.startswith('//') and
                         any(keyword in line for keyword in ['int ', 'void ', 'bool ', 'auto ', 'char ', 'float ', 'double ']))):
                        if '{' in line:
                            signatures.append(line.split('{')[0].strip() + ' { ... }')
                        elif ';' in line:
                            signatures.append(line.strip())
                        else:
                            signatures.append(line.strip())
                if signatures:
                    return '\n'.join(signatures) + f'\n# ... (Aggressive compression via regex - {language})'
            
            # Fallback to medium compression
            return MultiLanguageAnalyzer._fallback_compression(content, language, "medium")
        
        return content
    
    @staticmethod
    def _format_python_structure(structure: Dict[str, Any]) -> str:
        """
        Formats Python structure dictionary into compressed code representation.
        """
        lines = []
        
        # Add imports
        if structure.get("imports"):
            lines.extend(structure["imports"])
            lines.append("")  # Blank line after imports
        
        # Add top-level variables
        if structure.get("variables"):
            for var in structure["variables"]:
                lines.append(f"{var} = ...")
            lines.append("")
        
        # Add functions
        if structure.get("functions"):
            for func_sig in structure["functions"]:
                lines.append(f"{func_sig}:")
                lines.append("    ...")
                lines.append("")
        
        # Add classes
        if structure.get("classes"):
            for class_info in structure["classes"]:
                lines.append(class_info["signature"])
                
                # Add class variables
                for var in class_info.get("variables", []):
                    lines.append(f"    {var} = ...")
                
                # Add methods
                for method_sig in class_info.get("methods", []):
                    lines.append(f"    {method_sig}:")
                    lines.append("        ...")
                
                lines.append("")
        
        return "\n".join(lines) + "\n# ... (Structure extracted via AST - pak_analyzer.py)"

    @staticmethod
    def _get_node_source_segment(node: ast.AST, content_lines: List[str]) -> str:
        """
        Extracts the precise source segment for an AST node.
        Handles nodes that span multiple lines and considers decorators.
        """
        if not (hasattr(node, 'lineno') and hasattr(node, 'col_offset') and
                hasattr(node, 'end_lineno') and hasattr(node, 'end_col_offset')):
            return "" # Not enough info to get source

        # Adjust lineno to be 0-indexed for list access
        start_line_idx = node.lineno - 1
        end_line_idx = node.end_lineno - 1 if node.end_lineno is not None else start_line_idx

        # Include decorators if present (they are part of the function/class definition)
        if hasattr(node, 'decorator_list') and node.decorator_list:
            first_decorator = node.decorator_list[0]
            if hasattr(first_decorator, 'lineno'):
                start_line_idx = min(start_line_idx, first_decorator.lineno - 1)

        if start_line_idx < 0 or end_line_idx >= len(content_lines): # Boundary checks
             return f"# Error: Node line numbers out of bounds: {node.lineno}-{node.end_lineno}"


        if start_line_idx == end_line_idx: # Single-line node
            return content_lines[start_line_idx][node.col_offset:node.end_col_offset]
        else: # Multi-line node
            source_parts = []
            # First line: from col_offset to end of line
            source_parts.append(content_lines[start_line_idx][node.col_offset:])
            # Middle lines: full lines
            for i in range(start_line_idx + 1, end_line_idx):
                source_parts.append(content_lines[i])
            # Last line: from start of line to end_col_offset
            if node.end_col_offset is not None: # end_col_offset can be None for some nodes
                 source_parts.append(content_lines[end_line_idx][:node.end_col_offset])
            else: # If no end_col_offset, take the whole last line
                 source_parts.append(content_lines[end_line_idx])

            return "\n".join(source_parts)

    @staticmethod
    def extract_structure(content: str) -> Dict[str, Any]:
        """
        Extracts a summary of Python code structure (imports, functions, classes, top-level vars).
        Returns a dictionary representing the structure, or an error dict.
        """
        try:
            # Add parent pointers to the AST for easier context checking (e.g., top-level)
            tree = ast.parse(content)
            for node_obj in ast.walk(tree):
                for child in ast.iter_child_nodes(node_obj):
                    child.parent = node_obj # type: ignore
        except SyntaxError as e:
            return {"error": f"Invalid Python syntax: {e}"}
        except Exception as e: # Catch other parsing errors
            return {"error": f"Failed to parse Python AST: {e}"}


        structure: Dict[str, Union[List[str], List[Dict[str, Any]]]] = {
            "imports": [],
            "functions": [], # List of function signature strings
            "classes": [],   # List of dicts: {"signature": str, "methods": list[str], "variables": list[str]}
            "variables": []  # List of top-level variable names
        }

        for node in ast.walk(tree):
            parent_type = type(node.parent) if hasattr(node, 'parent') else None

            if isinstance(node, ast.Import):
                for alias in node.names:
                    structure["imports"].append(f"import {alias.name}{f' as {alias.asname}' if alias.asname else ''}") # type: ignore
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                # Handle relative imports (level > 0)
                relative_prefix = "." * node.level if node.level > 0 else ""
                for alias in node.names:
                    item_name = alias.name
                    as_name_suffix = f" as {alias.asname}" if alias.asname else ""
                    structure["imports"].append(f"from {relative_prefix}{module_name} import {item_name}{as_name_suffix}") # type: ignore

            elif isinstance(node, ast.FunctionDef):
                # Only include top-level functions in the "functions" list
                if parent_type == ast.Module:
                    args_list = [arg.arg for arg in node.args.args]
                    # Could also include: node.args.vararg, node.args.kwarg, type hints (arg.annotation, node.returns)
                    func_sig = f"def {node.name}({', '.join(args_list)})"
                    if node.returns: # Add return type hint if present
                         # Safely get annotation source (might be complex)
                         try:
                             return_type_str = ast.unparse(node.returns) if hasattr(ast, 'unparse') else "UnknownType"
                         except:
                             return_type_str = "ComplexType" # Fallback for unparse issues
                         func_sig += f" -> {return_type_str}"
                    structure["functions"].append(func_sig) # type: ignore

            elif isinstance(node, ast.ClassDef):
                # Only top-level classes
                if parent_type == ast.Module:
                    base_classes_str = []
                    for base_node in node.bases:
                        try:
                            base_classes_str.append(ast.unparse(base_node) if hasattr(ast, 'unparse') else "UnknownBase")
                        except:
                            base_classes_str.append("ComplexBase")

                    class_sig_str = f"class {node.name}"
                    if base_classes_str:
                        class_sig_str += f"({', '.join(base_classes_str)})"

                    class_methods = []
                    class_vars = []
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef): # Methods
                            method_args = [arg.arg for arg in item.args.args]
                            method_sig = f"def {item.name}({', '.join(method_args)})"
                            if item.returns:
                                try: ret_type = ast.unparse(item.returns) if hasattr(ast, 'unparse') else "Any"
                                except: ret_type = "ComplexRet"
                                method_sig += f" -> {ret_type}"
                            class_methods.append(method_sig)
                        elif isinstance(item, ast.Assign): # Class-level assignments
                            for target in item.targets:
                                if isinstance(target, ast.Name):
                                    class_vars.append(target.id)
                        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name): # Annotated class vars
                             class_vars.append(item.target.id)


                    structure["classes"].append({ # type: ignore
                        "signature": class_sig_str + ":",
                        "methods": class_methods,
                        "variables": class_vars
                    })

            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                # Capture top-level variable assignments
                if parent_type == ast.Module:
                    targets_to_add = []
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name): targets_to_add.append(target.id)
                    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                        targets_to_add.append(node.target.id)
                    elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                         targets_to_add.append(node.target.id)

                    for var_name in targets_to_add:
                        if var_name not in structure["variables"]: # Avoid duplicates
                             structure["variables"].append(var_name) # type: ignore
        return structure

    @staticmethod
    def extract_methods(content: str) -> List[Dict[str, Any]]:
        """
        Extracts individual functions and methods from Python code,
        including their full source code.
        Returns a list of dictionaries, each representing a method/function.
        """
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return [] # Return empty list on syntax error

        methods_details = []
        content_lines = content.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                source_segment = MultiLanguageAnalyzer._get_node_source_segment(node, content_lines)

                # Construct a more detailed signature if possible
                args_strs = []
                for arg_node in node.args.args:
                    arg_str = arg_node.arg
                    if arg_node.annotation:
                        try: arg_str += f": {ast.unparse(arg_node.annotation) if hasattr(ast, 'unparse') else 'Any'}"
                        except: arg_str += ": ComplexType"
                    args_strs.append(arg_str)

                # Handle *args, **kwargs, positional-only, keyword-only args if needed for signature
                # This is a simplified version for now.

                signature = f"def {node.name}({', '.join(args_strs)})"
                if node.returns:
                    try: signature += f" -> {ast.unparse(node.returns) if hasattr(ast, 'unparse') else 'Any'}"
                    except: signature += " -> ComplexType"

                methods_details.append({
                    "name": node.name,
                    "start_line": node.lineno,
                    "end_line": node.end_lineno if node.end_lineno is not None else node.lineno,
                    "source": source_segment.strip(), # Normalize by stripping leading/trailing whitespace
                    "signature": signature,
                    # Could add "class_name": parent_class_name if inside a class
                })
        return methods_details

    @staticmethod
    def compare_methods(old_content: str, new_content: str) -> List[Dict[str, Any]]:
        """
        Compares methods/functions between two Python code strings.
        Returns a list of diffs (added, removed, modified).
        Modification is detected by changes in the normalized source code.
        """
        old_methods_list = MultiLanguageAnalyzer.extract_methods(old_content)
        new_methods_list = MultiLanguageAnalyzer.extract_methods(new_content)

        # Create dictionaries keyed by method name for easier lookup
        # For methods with same name in different classes, this would need refinement (e.g. key by "ClassName.method_name")
        # Current implementation assumes top-level functions or uniquely named methods for simplicity of diffing.
        old_methods_map = {m["name"]: m for m in old_methods_list}
        new_methods_map = {m["name"]: m for m in new_methods_list}

        diff_results = []
        all_method_names = set(old_methods_map.keys()) | set(new_methods_map.keys())

        for name in all_method_names:
            old_method_data = old_methods_map.get(name)
            new_method_data = new_methods_map.get(name)

            if old_method_data and new_method_data:
                # Normalize source for comparison: strip whitespace from each line, then join.
                # This helps ignore minor formatting changes.
                norm_old_src = "\n".join(line.strip() for line in old_method_data["source"].splitlines() if line.strip()).strip()
                norm_new_src = "\n".join(line.strip() for line in new_method_data["source"].splitlines() if line.strip()).strip()

                if norm_old_src != norm_new_src:
                    diff_results.append({
                        "type": "modified",
                        "method_name": name,
                        "old_source": old_method_data["source"], # Keep original source for the diff output
                        "new_source": new_method_data["source"],
                        "old_signature": old_method_data["signature"],
                        "new_signature": new_method_data["signature"]
                    })
            elif new_method_data: # Method exists only in new content (added)
                diff_results.append({
                    "type": "added",
                    "method_name": name,
                    "new_source": new_method_data["source"],
                    "new_signature": new_method_data["signature"]
                })
            elif old_method_data: # Method exists only in old content (removed)
                diff_results.append({
                    "type": "removed",
                    "method_name": name,
                    "old_source": old_method_data["source"],
                    "old_signature": old_method_data["signature"]
                })
        return diff_results

# Backward compatibility alias
PythonAnalyzer = MultiLanguageAnalyzer

if __name__ == '__main__':
    sample_code_v1 = """
import os
import sys

# A global variable
GLOBAL_VAR = 100

class MyClass:
    # A class variable
    cls_var = "hello"

    def __init__(self, value):
        self.value = value

    def greet(self, name: str) -> str:
        '''Greets a person.'''
        # A comment inside method
        message = f"Hello, {name}! Value is {self.value}"
        return message

def top_level_func(a, b):
    # This is a simple function
    return a + b
"""

    sample_code_v2 = """
import os # Unchanged import
# import sys # Removed import

# A global variable, modified
GLOBAL_VAR = 200
NEW_GLOBAL = "new"

class MyClass: # Unchanged class signature
    cls_var = "world" # Modified class var

    def __init__(self, value): # Unchanged method
        self.value = value

    def greet(self, name: str, enthusiasm: int = 1) -> str: # Modified signature and body
        '''Greets a person with enthusiasm.'''
        # A modified comment
        message = f"Hello, {name}{'!' * enthusiasm} Value is {self.value}"
        print("Greeting!") # Added line
        return message

    def new_method(self): # Added method
        return "This is new"

# top_level_func removed

def another_func(): # Added function
    pass
"""
    print("--- Structure V1 ---")
    print(MultiLanguageAnalyzer.extract_structure(sample_code_v1))
    print("\n--- Methods V1 ---")
    for m in MultiLanguageAnalyzer.extract_methods(sample_code_v1): print(m)

    print("\n--- Structure V2 ---")
    print(MultiLanguageAnalyzer.extract_structure(sample_code_v2))
    print("\n--- Methods V2 ---")
    for m in MultiLanguageAnalyzer.extract_methods(sample_code_v2): print(m)

    print("\n--- Method Diffs (V1 -> V2) ---")
    diffs = MultiLanguageAnalyzer.compare_methods(sample_code_v1, sample_code_v2)
    for d in diffs:
        print(f"Type: {d['type']}, Name: {d['method_name']}")
        if 'old_source' in d: print(f"  Old Signature: {d.get('old_signature')}")
        if 'new_source' in d: print(f"  New Signature: {d.get('new_signature')}")
        print("-" * 10)
