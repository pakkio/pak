#!/usr/bin/env python3
"""
pak_core.py - Python business logic for pak3
Consolidates AST analysis, smart compression, and file prioritization
Enhanced with regex-based extraction filtering
"""

import sys
import os
import re
import argparse
import tempfile # Not actively used, but kept for potential future use
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set, Any
from abc import ABC, abstractmethod

# Tree-sitter imports (optional)
try:
    from tree_sitter import Language, Parser, Node, Query # type: ignore
    import tree_sitter_languages # type: ignore
    # Specific languages that might be bundled or easily available
    try:
        import tree_sitter_python # type: ignore
    except ImportError:
        tree_sitter_python = None # type: ignore
    AST_AVAILABLE = True
except ImportError:
    AST_AVAILABLE = False
    # Define dummy types for annotations if tree_sitter is not available
    Node = Any # type: ignore
    Query = Any # type: ignore
    Language = Any # type: ignore
    Parser = Any # type: ignore


VERSION = "3.1.0"

@dataclass
class FileEntry:
    path: Path
    language: str
    importance: int
    original_tokens: int
    compressed_content: str = ""
    compressed_tokens: int = 0
    compression_method: str = "unknown"
    size: int = 0 # Original file size in bytes
    lines: int = 0 # Lines in compressed content

@dataclass 
class ArchiveConfig:
    compression_level: str = "none"
    max_tokens: int = 0
    include_extensions: List[str] = field(default_factory=list) # List of strings like ".py", ".md"
    targets: List[Path] = field(default_factory=list) # List of Path objects
    quiet: bool = False

class CompressionStrategy(ABC):
    @abstractmethod
    def compress(self, content: str, file_path: Path, language: str) -> Tuple[str, str]:
        """Return (compressed_content, method_description)"""
        pass

class NoneCompression(CompressionStrategy):
    def compress(self, content: str, file_path: Path, language: str) -> Tuple[str, str]:
        return content, "raw (no compression)"

class LightCompression(CompressionStrategy):
    def compress(self, content: str, file_path: Path, language: str) -> Tuple[str, str]:
        lines = content.splitlines() # Preserves universal newlines behavior
        compressed_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped:  # Skip empty lines
                if line.startswith((' ', '\t')): # Check if line had leading whitespace
                    indent_len = len(line) - len(line.lstrip())
                    # Simple heuristic: 2 spaces per indent level, assuming mostly 4-space or tabs
                    # This is very basic and might not perfectly preserve all mixed indent styles
                    # A more robust approach would parse indent structure or use fixed conversion.
                    num_indents = indent_len // 4 
                    remainder_spaces = indent_len % 4
                    normalized_indent = ('  ' * num_indents) + (' ' * remainder_spaces)
                    compressed_lines.append(normalized_indent + stripped)
                else:
                    compressed_lines.append(stripped)
        return '\n'.join(compressed_lines), "text-light (whitespace/empty lines)"

class MediumCompression(CompressionStrategy):
    def compress(self, content: str, file_path: Path, language:str) -> Tuple[str, str]:
        content, _ = LightCompression().compress(content, file_path, language) # Start with light
        
        # Comment removal for common code languages (basic, single-line)
        # Multi-line comments are harder with regex and better handled by AST if available.
        code_like_languages = {'python', 'javascript', 'typescript', 'java', 'c', 'cpp', 'go', 'rust', 'csharp', 'ruby', 'php', 'swift', 'kotlin', 'scala'}
        if language in code_like_languages:
            lines = content.splitlines()
            filtered_lines = []
            in_multiline_comment = False # Basic state for block comments (very simple)

            comment_patterns = {
                'python': r'^\s*#.*$',
                'ruby': r'^\s*#.*$',
                'javascript': r'^\s*//.*$',
                'typescript': r'^\s*//.*$',
                'java': r'^\s*//.*$',
                'c': r'^\s*//.*$', # C99+ style comments
                'cpp': r'^\s*//.*$',
                'go': r'^\s*//.*$',
                'rust': r'^\s*//.*$',
                'csharp': r'^\s*//.*$',
                'php': r'^\s*(#|//).*$', # PHP allows # and //
                'swift': r'^\s*//.*$',
                'kotlin': r'^\s*//.*$',
                'scala': r'^\s*//.*$',
            }
            # Simple block comment start/end for languages like C, Java, JS, CSS
            block_comment_start = {'c', 'cpp', 'java', 'javascript', 'typescript', 'css', 'csharp', 'go', 'rust', 'swift', 'kotlin', 'scala'}
            block_comment_end_pattern = r'\*/\s*$'


            for line in lines:
                stripped_line = line.strip()
                
                # Handle block comments (very basic, assumes /* and */ are on their own lines or at start/end)
                if language in block_comment_start:
                    if in_multiline_comment:
                        if re.search(block_comment_end_pattern, stripped_line):
                            in_multiline_comment = False
                        continue # Skip line inside block comment
                    elif stripped_line.startswith('/*'):
                        if re.search(block_comment_end_pattern, stripped_line) and not stripped_line.endswith('/**/'): # not a /* ... */ on one line
                             # It's a single line block comment like /* comment */
                             if not (stripped_line.count('/*') == 1 and stripped_line.count('*/') == 1 and stripped_line.find('/*') < stripped_line.find('*/')):
                                 in_multiline_comment = True # It's a multiline starter
                        else: # It is /* ... */ on one line or just /*
                             if not (stripped_line.count('/*') == 1 and stripped_line.count('*/') == 1 and stripped_line.find('/*') < stripped_line.find('*/')):
                                in_multiline_comment = True
                        if in_multiline_comment and not re.search(block_comment_end_pattern, stripped_line): # if it starts and doesn't end on same line
                            continue

                # Single line comments
                if language in comment_patterns and re.match(comment_patterns[language], stripped_line):
                    continue
                
                # Specific check for C-style single line block comments: /* comment */
                if language in block_comment_start and stripped_line.startswith('/*') and stripped_line.endswith('*/'):
                    if stripped_line.count('/*') == 1 and stripped_line.count('*/') == 1: # Ensure it's a simple one
                        continue
                
                filtered_lines.append(line) # Keep original line to preserve indent
            
            content = '\n'.join(filtered_lines)
        
        return content, "text-medium (light+comments)"

class AggressiveTextCompression(CompressionStrategy): # Renamed to avoid conflict if AST is primary
    def compress(self, content: str, file_path: Path, language: str) -> Tuple[str, str]:
        method_suffix = "text-aggressive"
        if language == 'python':
            compressed = self._extract_python_structure_text(content)
            method_suffix += "-py"
        elif language in ['javascript', 'typescript']:
            compressed = self._extract_js_ts_structure_text(content)
            method_suffix += "-js"
        else:
            # Fallback for other languages: Medium compression + further reduction
            # This is a simple heuristic: take first N lines and last N lines
            content, _ = MediumCompression().compress(content, file_path, language)
            lines = content.splitlines()
            if len(lines) > 40: # If file is somewhat long
                compressed = "\n".join(lines[:20]) + "\n...\n" + "\n".join(lines[-20:])
            else:
                compressed = content # If short, medium is enough
            method_suffix += "-generic"
        
        return compressed, method_suffix
    
    def _extract_python_structure_text(self, content: str) -> str:
        lines = content.splitlines()
        result = []
        in_class_block = False
        current_class_header = ""
        class_methods_buffer = []

        for line_content in lines:
            stripped = line_content.strip()
            
            if not stripped or stripped.startswith('#'): continue # Skip empty and comment lines

            # Imports
            if stripped.startswith('import ') or stripped.startswith('from '):
                result.append(stripped)
                continue

            # Class definition
            if stripped.startswith('class '):
                if in_class_block and class_methods_buffer: # Finish previous class
                    result.append(current_class_header)
                    result.extend([f"    {m}" for m in class_methods_buffer])
                    result.append("") # Add newline after class
                current_class_header = stripped.split(':')[0] + ":" if ':' in stripped else stripped + ":"
                in_class_block = True
                class_methods_buffer = []
                continue

            # Method or function definition
            if stripped.startswith('def '):
                # If it's a function and we were in a class, finish the class
                if not line_content.startswith((' ', '\t')) and in_class_block: # Heuristic: not indented = new scope
                    if class_methods_buffer:
                        result.append(current_class_header)
                        result.extend([f"    {m}" for m in class_methods_buffer])
                        result.append("")
                    in_class_block = False; class_methods_buffer = [] # Reset class state

                # Extract signature
                match = re.match(r'def\s+([^(]+\([^)]*\))', stripped)
                if match:
                    signature = match.group(1)
                    # Append return type if present on the same line
                    if '->' in stripped:
                        return_type_match = re.search(r'->\s*([^:]+):', stripped)
                        if return_type_match:
                            signature += f" -> {return_type_match.group(1).strip()}"
                    signature += ": ..." # Add ellipsis for method body

                    if in_class_block:
                        class_methods_buffer.append(signature)
                    else:
                        result.append(signature)
                continue
            
            # Module-level constants (UPPER_CASE)
            if not in_class_block and re.match(r'^[A-Z_][A-Z0-9_]*\s*=', stripped):
                result.append(stripped)
                continue

        # Finish any remaining class
        if in_class_block and class_methods_buffer:
            result.append(current_class_header)
            result.extend([f"    {m}" for m in class_methods_buffer])

        return '\n'.join(result) if result else "# No Python structure found (text-aggressive)"


    def _extract_js_ts_structure_text(self, content: str) -> str:
        lines = content.splitlines()
        result = []
        # Regex for common JS/TS structures (simplified)
        # Matches imports, exports, classes, interfaces, functions (incl. arrow assigned to var/let/const)
        # This is a broad heuristic.
        structure_pattern = re.compile(
            r'^\s*(?:import|export|class|interface|type|function|const|let|var|async\s+function|\w+\s*=\s*async\s*\(|\w+\s*:\s*async\s*\()'
        )
        # Heuristic for end of signature (e.g. before { or => { )
        signature_end_pattern = re.compile(r'(\)\s*(?::\s*\w+)?\s*(?:=>)?\s*\{?)')

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('//') or stripped.startswith('/*'): # Basic comment skip
                continue

            if structure_pattern.match(stripped):
                # Try to get just the signature part
                sig_match = signature_end_pattern.search(stripped)
                if sig_match:
                    end_pos = sig_match.start(1) # End before the brace or fat arrow body
                    line_to_add = stripped[:end_pos] + (") ..." if not stripped[end_pos-1] == ')' else " ...")
                else: # if no clear signature end, take the line and add ellipsis if no brace
                    line_to_add = stripped + (" ..." if not stripped.endswith('{') else "")
                
                result.append(line_to_add)

        return '\n'.join(result) if result else "# No JS/TS structure found (text-aggressive)"


class ASTCompression(CompressionStrategy):
    def __init__(self):
        self.ast_available = AST_AVAILABLE
        self._parsers: Dict[str, Parser] = {} 
        self._languages: Dict[str, Language] = {}
    
    def _get_language(self, lang_name: str) -> Optional[Language]:
        if lang_name in self._languages:
            return self._languages[lang_name]
        if not AST_AVAILABLE: return None

        try:
            lang_obj = None
            if lang_name == 'python' and tree_sitter_python:
                lang_obj = Language(tree_sitter_python.language())
            # Map other languages using tree_sitter_languages
            # This mapping should align with LanguageDetector outputs
            elif lang_name in ['javascript', 'js']: lang_obj = tree_sitter_languages.get_language('javascript')
            elif lang_name == 'typescript': lang_obj = tree_sitter_languages.get_language('typescript')
            elif lang_name == 'java': lang_obj = tree_sitter_languages.get_language('java')
            elif lang_name == 'rust': lang_obj = tree_sitter_languages.get_language('rust')
            elif lang_name == 'c': lang_obj = tree_sitter_languages.get_language('c')
            elif lang_name == 'cpp': lang_obj = tree_sitter_languages.get_language('cpp')
            elif lang_name == 'go': lang_obj = tree_sitter_languages.get_language('go')
            elif lang_name == 'ruby': lang_obj = tree_sitter_languages.get_language('ruby')
            elif lang_name == 'php': lang_obj = tree_sitter_languages.get_language('php')
            elif lang_name == 'csharp': lang_obj = tree_sitter_languages.get_language('c_sharp')
            # Add more as needed and as supported by tree_sitter_languages
            
            if lang_obj:
                self._languages[lang_name] = lang_obj
                return lang_obj
            return None
        except Exception: # Errors from get_language() or Language() constructor
            return None

    def _get_parser(self, language_name: str) -> Optional[Parser]:
        if language_name in self._parsers:
            return self._parsers[language_name]
        if not AST_AVAILABLE: return None

        lang_obj = self._get_language(language_name)
        if lang_obj:
            parser = Parser(lang_obj) # Set language for the parser
            self._parsers[language_name] = parser
            return parser
        return None
    
    def compress(self, content: str, file_path: Path, language: str) -> Tuple[str, str]:
        if not self.ast_available:
            return AggressiveTextCompression().compress(content, file_path, language)
        
        parser = self._get_parser(language)
        if not parser:
            # Fallback if no parser for this language
            return AggressiveTextCompression().compress(content, file_path, language)
        
        try:
            source_bytes = content.encode('utf-8')
            tree = parser.parse(source_bytes)
            
            compressed_content = ""
            # Language-specific AST extraction
            if language == 'python':
                compressed_content = self._extract_python_ast(tree, source_bytes)
            elif language in ['javascript', 'typescript', 'js']:
                 compressed_content = self._extract_js_ts_ast(tree, source_bytes, language)
            # Add other specific extractors like:
            # elif language == 'java': compressed_content = self._extract_java_ast(tree, source_bytes)
            else: # Fallback to a more generic AST extraction for other languages
                compressed_content = self._extract_generic_ast(tree, source_bytes, language)
            
            return compressed_content, "AST-aggressive"
            
        except Exception as e:
            # Fallback on any AST processing error for this file
            # print(f"pak_core: AST compression error for {file_path} ({language}): {e}. Falling back to text.", file=sys.stderr)
            return AggressiveTextCompression().compress(content, file_path, language)

    def _node_text(self, node: Node, source_bytes: bytes) -> str:
        return source_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')

    def _extract_definition_header(self, node: Node, source_bytes: bytes, language: str) -> str:
        """Extracts the header of a definition (e.g., function/class signature)."""
        # Default: take the first line of the node text, up to a body opener like '{' or ':'
        full_node_text = self._node_text(node, source_bytes)
        first_line = full_node_text.splitlines()[0] if full_node_text else ""

        # Language-specific header endings
        if language == 'python':
            # Python headers end with ':'
            if ':' in first_line:
                return first_line.split(':', 1)[0].strip() + ":"
            return first_line.strip() # Should ideally have ':'
        elif language in ['javascript', 'typescript', 'java', 'c', 'cpp', 'csharp', 'rust', 'go', 'swift', 'kotlin', 'scala']:
            # These often end with '{' for the body, or ';' for declarations
            if '{' in first_line:
                return first_line.split('{', 1)[0].strip()
            if ';' in first_line: # e.g. C/C++ function prototype
                 return first_line.split(';', 1)[0].strip() + ";"
            return first_line.strip() # Fallback
        
        return first_line.strip() # Generic fallback

    def _query_ast(self, tree: Node, lang_obj: Language, query_string: str) -> List[Tuple[Node, str]]:
        try:
            query = lang_obj.query(query_string)
            return query.captures(tree.root_node) # type: ignore
        except Exception: # tree_sitter.TreeSitterError if query is bad, or other issues
            return []

    def _extract_python_ast(self, tree: Node, source_bytes: bytes) -> str:
        lang_py = self._get_language('python')
        if not lang_py: return "# Python AST language not available"
        
        query_str = """
        (import_statement) @import
        (import_from_statement) @import_from
        (function_definition name: (identifier) @name) @function
        (class_definition name: (identifier) @name) @class
        (assignment left: (identifier) @name value: (_)) @constant
        """
        # Filter constants to be module-level (heuristic: all caps)
        # (assignment left: (identifier) @name) @assignment
        # where @name matches `^[A-Z_][A-Z0-9_]*$`

        captures = self._query_ast(tree, lang_py, query_str)
        elements = []
        for node, name_tag in captures:
            if name_tag in ["import", "import_from"]:
                elements.append(self._node_text(node, source_bytes).strip())
            elif name_tag in ["function", "class"]:
                header = self._extract_definition_header(node, source_bytes, 'python')
                elements.append(f"{header} ...")
            elif name_tag == "constant":
                var_name_node = node.child_by_field_name('left') # type: ignore # tree-sitter specific
                if var_name_node and re.fullmatch(r'[A-Z_][A-Z0-9_]*', self._node_text(var_name_node, source_bytes)):
                    elements.append(self._node_text(node, source_bytes).strip())
        
        return "\n".join(elements) if elements else "# No Python structure (AST)"

    def _extract_js_ts_ast(self, tree: Node, source_bytes: bytes, language: str) -> str:
        lang_obj = self._get_language(language)
        if not lang_obj: return f"# {language} AST language not available"

        query_str = """
        (import_statement) @import
        (export_statement) @export
        (lexical_declaration (variable_declarator name: (identifier) value: [(arrow_function) (function)])) @func_const_let
        (function_declaration name: (identifier)) @function
        (method_definition name: (property_identifier)) @method
        (class_declaration name: (type_identifier)) @class
        (interface_declaration name: (type_identifier)) @interface
        (type_alias_declaration name: (type_identifier)) @type_alias
        """
        # Note: `(identifier)` might be too general for `value` in `lexical_declaration` if we only want functions.
        # `(arrow_function)` and `(function)` are more specific for function assignments.

        captures = self._query_ast(tree, lang_obj, query_str)
        elements = []
        processed_node_ids = set() # To avoid duplicates from overlapping captures

        for node, name_tag in captures:
            if node.id in processed_node_ids: continue
            processed_node_ids.add(node.id)

            if name_tag in ["import", "export"]:
                elements.append(self._node_text(node, source_bytes).strip().split(';')[0]) # Remove trailing semicolon
            elif name_tag in ["func_const_let", "function", "method", "class", "interface", "type_alias"]:
                header = self._extract_definition_header(node, source_bytes, language)
                # Add '...' but try to respect if body was already empty or on one line
                if header.endswith('{'): # For "class X {"
                    elements.append(header + " ... }")
                elif header.endswith(';'): # For "interface X;"
                     elements.append(header)
                else:
                    elements.append(f"{header} {{ ... }}") # For functions, etc.
            
        return "\n".join(elements) if elements else f"# No {language} structure (AST)"

    def _extract_generic_ast(self, tree: Node, source_bytes: bytes, language: str) -> str:
        # This is a very basic fallback if no specific AST extractor is available for the language
        # It tries to find common top-level definition-like nodes.
        lang_obj = self._get_language(language)
        if not lang_obj: return f"# {language} AST language not available for generic extraction"

        # Common node types across many languages (names vary by grammar!)
        # This list is illustrative and likely needs per-grammar refinement.
        # Check `node-types.json` in a tree-sitter grammar repo.
        possible_def_types = [
            "function_definition", "function_declaration", "method_definition", "subroutine_declaration",
            "class_definition", "class_declaration", "struct_definition", "struct_declaration", "module_definition",
            "interface_declaration", "enum_declaration", "type_definition", "type_alias_declaration",
            "import_statement", "export_statement", "package_declaration", "namespace_definition",
            # More specific ones found in various grammars
            "global_variable_declaration", "constant_declaration"
        ]
        query_str_parts = [f"({node_type}) @definition" for node_type in possible_def_types]
        
        elements = []
        if query_str_parts:
            captures = self._query_ast(tree, lang_obj, "\n".join(query_str_parts))
            processed_node_ids = set()
            for node, _ in captures:
                if node.id in processed_node_ids: continue
                processed_node_ids.add(node.id)
                header = self._extract_definition_header(node, source_bytes, language)
                elements.append(header + " ...") # Append ellipsis

        if not elements: # If query yielded nothing, try simple recursive scan for first few levels
            # This is less precise than queries.
            max_depth = 3 # How deep to scan from root
            
            def limited_traverse(current_node: Node, depth: int):
                if depth > max_depth: return
                # Check if node type seems like a definition based on its name
                if "definition" in current_node.type or "declaration" in current_node.type or \
                   current_node.type in ["import_statement", "export_statement"]:
                    header = self._extract_definition_header(current_node, source_bytes, language)
                    elements.append(header + " ...")
                
                for child in current_node.children: # type: ignore
                    limited_traverse(child, depth + 1)
            
            if tree.root_node: # type: ignore
                 limited_traverse(tree.root_node, 0) # type: ignore


        return "\n".join(elements) if elements else f"# No generic structure (AST, {language})"


class LanguageDetector:
    # Extended map, case-insensitive matching for suffix
    EXTENSION_MAP = {
        # Programming Languages
        '.py': 'python', '.pyw': 'python',
        '.js': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript',
        '.ts': 'typescript', '.tsx': 'typescript',
        '.java': 'java',
        '.kt': 'kotlin', '.kts': 'kotlin',
        '.scala': 'scala',
        '.swift': 'swift',
        '.rb': 'ruby', '.rbw': 'ruby',
        '.php': 'php', '.phtml': 'php', '.php3': 'php', '.php4': 'php', '.php5': 'php', '.phps': 'php',
        '.cs': 'csharp',
        '.c': 'c', '.h': 'c', # .h is ambiguous, default C, AST can clarify if C++ uses it
        '.cpp': 'cpp', '.hpp': 'cpp', '.cxx': 'cpp', '.hxx': 'cpp', '.cc': 'cpp', '.hh': 'cpp',
        '.go': 'go',
        '.rs': 'rust',
        '.pl': 'perl', '.pm': 'perl', '.t': 'perl', # .t for test files
        '.lua': 'lua',
        '.r': 'r', '.R': 'r',
        '.dart': 'dart',
        '.groovy': 'groovy', '.gvy': 'groovy', '.gy': 'groovy', '.gsh': 'groovy',
        '.hs': 'haskell', '.lhs': 'haskell',
        '.erl': 'erlang', '.hrl': 'erlang',
        '.elm': 'elm',
        '.clj': 'clojure', '.cljs': 'clojure', '.cljc': 'clojure', '.edn': 'clojure',
        '.fs': 'fsharp', '.fsi': 'fsharp', '.fsx': 'fsharp', '.fsscript': 'fsharp',
        '.ex': 'elixir', '.exs': 'elixir',
        '.zig': 'zig',
        '.nim': 'nim',
        '.cr': 'crystal',
        '.vb': 'vbnet', # Visual Basic .NET
        '.pas': 'pascal', '.pp': 'pascal', '.inc': 'pascal', # .inc also common in other langs
        '.lisp': 'lisp', '.lsp': 'lisp', '.cl': 'common-lisp',
        '.scm': 'scheme', '.ss': 'scheme',
        '.f': 'fortran', '.for': 'fortran', '.f77': 'fortran', '.f90': 'fortran', '.f95': 'fortran', '.f03': 'fortran',
        '.ada': 'ada', '.adb': 'ada', '.ads': 'ada',
        '.s': 'assembly', '.asm': 'assembly',
        '.d': 'd', '.di': 'd',
        '.cob': 'cobol', '.cbl': 'cobol',
        '.v': 'verilog', '.vh': 'verilog',
        '.vhd': 'vhdl', '.vhdl': 'vhdl',

        # Markup & Data Formats
        '.html': 'html', '.htm': 'html', '.xhtml': 'html',
        '.xml': 'xml', '.xsl': 'xml', '.xslt': 'xml', '.xsd': 'xml', '.rng': 'xml', '.plist': 'xml', '.csproj': 'xml', '.vbproj': 'xml', '.fsproj': 'xml', '.svg': 'xml', # SVG is XML
        '.json': 'json', '.jsonc': 'json', '.geojson': 'json', '.webmanifest': 'json', '.jsonld': 'json',
        '.yaml': 'yaml', '.yml': 'yaml',
        '.toml': 'toml',
        '.md': 'markdown', '.markdown': 'markdown', '.mdown': 'markdown', '.mkd': 'markdown',
        '.rst': 'rst', 
        '.tex': 'latex', '.ltx': 'latex', '.sty': 'latex', '.cls': 'latex',
        '.csv': 'csv',
        '.tsv': 'tsv',
        '.ini': 'ini',
        '.conf': 'config', '.cfg': 'config', '.config': 'config', '.cnf': 'config',
        '.properties': 'properties', '.props': 'properties',
        '.graphql': 'graphql', '.gql': 'graphql',
        '.proto': 'protobuf',
        '.tf': 'terraform', '.tfvars': 'terraform',

        # Shell & Scripting (non-primary languages)
        '.sh': 'bash', '.bash': 'bash', '.ksh': 'bash', '.zsh': 'bash', '.fish': 'fish',
        '.ps1': 'powershell', '.psm1': 'powershell', '.psd1': 'powershell',
        '.bat': 'batch', '.cmd': 'batch',
        '.vbs': 'vbscript',
        '.applescript': 'applescript', '.scpt': 'applescript',
        'makefile': 'makefile', 'gnumakefile': 'makefile', 'rakefile': 'ruby', # rakefile is ruby
        'dockerfile': 'dockerfile', 'containerfile': 'dockerfile',
        '.jenkinsfile': 'groovy', # Jenkinsfile is often Groovy
        'cmakelists.txt': 'cmake', '.cmake': 'cmake',
        '.sln': 'sln', # Visual Studio Solution (XML-like, but specific)
        
        # Stylesheets
        '.css': 'css',
        '.scss': 'scss', '.sass': 'sass',
        '.less': 'less',
        '.styl': 'stylus',

        # Build system specific (often data formats like JSON/XML/YAML, but can be special cased)
        'package.json': 'json', 'bower.json': 'json', 'composer.json': 'json',
        'gemfile': 'ruby', 'build.gradle': 'groovy', 'pom.xml': 'xml',
        'requirements.txt': 'pip-requirements', 'pipfile': 'toml', 'pyproject.toml': 'toml',

        # Text & Other
        '.txt': 'text', '.text': 'text',
        '.log': 'log',
        '.sql': 'sql', '.ddl': 'sql', '.dml': 'sql',
        '.patch': 'diff', '.diff': 'diff',
        '.crt': 'pem', '.pem': 'pem', '.key': 'pem', # Certificates
        '.asc': 'pgp', '.gpg': 'pgp', # PGP
        '.env': 'dotenv',
        '.gitattributes': 'gitattributes', '.gitignore': 'gitignore', '.gitmodules': 'gitmodules',
        '.editorconfig': 'editorconfig',
    }
    # Files that are identified by full name (case-insensitive)
    FILENAME_MAP = {
        'makefile': 'makefile',
        'gnumakefile': 'makefile',
        'dockerfile': 'dockerfile',
        'containerfile': 'dockerfile',
        'vagrantfile': 'ruby',
        'gemfile': 'ruby',
        'rakefile': 'ruby',
        'capfile': 'ruby',
        'cmakelists.txt': 'cmake',
        'package.json': 'json',
        'composer.json': 'json',
        'requirements.txt': 'pip-requirements',
        'pipfile': 'toml',
        'pyproject.toml': 'toml',
        'build.gradle': 'groovy', # could be .kts for Kotlin
        'pom.xml': 'xml',
        'project.clj': 'clojure', # Leiningen project file
        'nginx.conf': 'nginx',
        'httpd.conf': 'apacheconf',
        'apache2.conf': 'apacheconf',
        '.bashrc': 'bash',
        '.zshrc': 'bash', # zsh is mostly bash-compatible for syntax highlighting
        '.profile': 'bash',
        '.bash_profile': 'bash',
        '.gitconfig': 'ini', # Git config files are INI-like
        'robots.txt': 'text',
        'license': 'text', # Often plain text, sometimes MD
        'readme': 'markdown', # Assume READMEs are markdown unless specific ext
        'contributing': 'markdown',
        'changelog': 'markdown',
        'copying': 'text',
        'install': 'text',
        'authors': 'text',
        'news': 'text',
    }
    
    @classmethod
    def detect(cls, file_path: Path) -> str:
        filename_lower = file_path.name.lower()
        
        # 1. Check full filename map
        if filename_lower in cls.FILENAME_MAP:
            # Special case for build.gradle.kts
            if filename_lower == 'build.gradle' and file_path.suffix.lower() == '.kts':
                return 'kotlin'
            return cls.FILENAME_MAP[filename_lower]

        # 2. Check extension map
        suffix_lower = file_path.suffix.lower()
        if suffix_lower and suffix_lower in cls.EXTENSION_MAP:
            return cls.EXTENSION_MAP[suffix_lower]
        
        # 3. Ambiguous .h: if a corresponding .c/.cpp/.hpp etc. exists, lean towards that project's style.
        # This is complex. For now, if it's .h and no other rule matched, it defaults to 'c' from EXTENSION_MAP.

        # 4. Shebang check for executables without extension or with generic ones like .sh if needed
        # Only check if no specific type found yet, or if type is 'bash' but want more specific like 'python'
        current_lang_guess = 'generic' # Fallback if nothing else matches
        if not suffix_lower or cls.EXTENSION_MAP.get(suffix_lower, 'generic') in ['bash', 'sh', 'generic', 'text']:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    first_line = f.readline(256).strip() # Read a bit more for shebangs
                    if first_line.startswith('#!'):
                        if 'python3' in first_line: return 'python'
                        if 'python' in first_line: return 'python' # Covers python2 and generic python
                        if 'bash' in first_line: return 'bash'
                        if 'sh' in first_line: return 'bash' # Treat sh as bash for simplicity
                        if 'perl' in first_line: return 'perl'
                        if 'ruby' in first_line: return 'ruby'
                        if 'node' in first_line: return 'javascript'
                        if 'zsh' in first_line: return 'bash'
                        if 'ksh' in first_line: return 'bash'
                        if 'env php' in first_line: return 'php'
                        if 'env groovy' in first_line: return 'groovy'
                        # Add more common shebangs if needed
            except Exception: pass # Ignore errors reading shebang (e.g. binary file)
        
        # If still generic, try one last pass with stem for files like "README"
        if current_lang_guess == 'generic' and not suffix_lower: # No extension
            stem_lower = file_path.stem.lower()
            if stem_lower in cls.FILENAME_MAP: # e.g. "readme" without ".md"
                return cls.FILENAME_MAP[stem_lower]

        return current_lang_guess


class FilePrioritizer:
    HIGH_PRIORITY_SCORE = 25
    MEDIUM_PRIORITY_SCORE = 15
    LOW_PRIORITY_SCORE = 5
    NEUTRAL_SCORE = 10

    # Lowercase names/extensions/paths for matching
    CRITICAL_FILENAMES = { # Exact filenames, highest boost
        'package.json', 'composer.json', 'gemfile', 'build.gradle', 'pom.xml', 
        'pyproject.toml', 'pipfile', 'requirements.txt',
        'dockerfile', 'makefile', 'cmakelists.txt', 'kustomization.yaml', 'kustomization.yml',
        'main.py', 'main.js', 'main.ts', 'main.go', 'main.rs', 'main.java', 'main.kt', 'main.swift',
        'index.js', 'index.ts', 'index.html', 'app.py', 'app.js', 'app.ts', 'application.py',
        'manage.py', 'wsgi.py', 'asgi.py', 'vite.config.js', 'vite.config.ts', 'webpack.config.js',
        'next.config.js', 'nuxt.config.js', 'svelte.config.js', 'angular.json',
        '.env.example', '.env.template', 'settings.py', 'config.py', 'settings.yaml', 'config.yaml',
    }
    IMPORTANT_KEYWORDS_IN_PATH = { # Boost if these appear in path segments
        'src': 5, 'source': 5, 'app': 4, 'lib': 4, 'core': 6, 'server': 4, 'client': 3,
        'api': 5, 'routes': 4, 'controllers': 4, 'services': 4, 'handlers': 3, 'models': 4,
        'entities': 3, 'utils': 2, 'helpers': 2, 'common': 2, 'shared': 2, 'config': 6,
        'components': 3, 'widgets': 2, 'views': 3, 'templates': 2, 'schemas': 4,
        'migrations': 3, 'database': 4, 'store': 3, 'kernel': 5, 'entrypoint': 5,
        'workflow': 3, 'pipeline': 3, 'plugin': 3, 'module': 3, 'init': 4, '__init__.py': 6,
    }
    IMPORTANT_EXTENSIONS = { # General language priority
        # High
        '.py': 10, '.js': 9, '.ts': 10, '.java': 8, '.go': 9, '.rs': 10, '.rb': 7, '.php': 6, '.swift': 9, '.kt': 9, '.scala': 7,
        '.h': 6, '.hpp': 7, '.c': 5, '.cpp': 6, '.cs': 7,
        '.sql': 6, '.proto': 5, '.graphql': 5, '.tf': 5, # Definition/schema files
        # Medium
        '.html': 5, '.css': 4, '.jsx': 7, '.tsx': 8, '.vue': 7, '.svelte': 7, # Frontend (TSX higher due to TS)
        '.sh': 3, '.bash': 3, '.ps1': 3, # Scripts
        '.json': 2, '.xml': 1, '.yaml': 2, '.yml': 2, '.toml': 3, # Config/data (often less "core logic")
        '.md': 4, '.rst': 3, '.txt': 1, # Documentation
        '.ipynb': 3, # Notebooks
    }
    LOW_PRIORITY_PATTERNS = [ # Regex patterns for file paths that reduce score significantly
        r'[/\\]tests?[/\\]', r'[/\\]spec[/\\]', r'test_', r'_test\.', r'\.test\.', r'_spec\.', r'\.spec\.', # Test files
        r'[/\\]fixtures?[/\\]', r'[/\\]mocks?[/\\]', r'[/\\]doubles?[/\\]', # Test support
        r'[/\\]examples?[/\\]', r'[/\\]samples?[/\\]', r'[/\\]demos?[/\\]', # Examples
        r'[/\\]docs?[/\\]', r'[/\\]documentation[/\\]', # Doc folders (READMEs handled separately)
        r'changelog', r'contributing', r'license', r'code_of_conduct', r'security\.md', # Meta project files
        r'[/\\]vendor[/\\]', r'[/\\]third[-_]?party[/\\]', r'[/\\]external[/\\]', # Vendored code
        r'\.min\.(js|css)$', r'\.bundle\.(js|css)$', r'\.map$', # Minified/bundled/map files
        r'[/\\]assets?[/\\]', r'[/\\]static[/\\]', r'[/\\]public[/\\]', # Static assets (images, fonts often binary excluded)
        r'[/\\]data[/\\]', # Generic data folders, often not core logic
        r'^\.gitattributes$', r'^\.gitignore$', r'^\.gitmodules$', r'^\.npmignore$', r'^\.dockerignore$',
        r'^\.editorconfig$', r'^\.eslint', r'^\.prettier', r'^\.stylelint', r'^\.rubocop', r'^\.pylintrc$',
        r'^\.DS_Store$', r'^thumbs\.db$', r'\.bak$', r'\.tmp$', r'\.swp$', r'\.swo$', r'.*\.old$',
        r'.*\.log(\.\d*)?$', # Log files
        r'[/\\]benchmark[/\\]', r'[/\\]bench[/\\]', # Benchmarks
        r'[/\\]__snapshots__[/\\]', # Jest snapshots
        r'[/\\]scripts?[/\\]', # General scripts folder (can be important, but often utils)
        r'[/\\]tools?[/\\]', # Tooling scripts
    ]
    # Penalty for being very deep in the directory structure
    DEPTH_PENALTY_START = 4 # Start penalizing after this depth
    DEPTH_PENALTY_FACTOR = 1.5

    @classmethod
    def calculate_importance(cls, file_path: Path) -> int:
        score = float(cls.NEUTRAL_SCORE) # Start with a float for easier fractional adjustments
        
        filename_lower = file_path.name.lower()
        filepath_str_lower = str(file_path.as_posix()).lower() # Use POSIX for consistent /
        extension_lower = file_path.suffix.lower()
        
        # 1. Critical Filenames (Strongest Boost)
        if filename_lower in cls.CRITICAL_FILENAMES:
            score += cls.HIGH_PRIORITY_SCORE * 1.5 # Extra boost for these specific files
            # If it's a root-level critical file (e.g. ./package.json)
            if len(file_path.parts) <= (2 if file_path.is_absolute() else 1): # ./file.py or /abs/file.py
                score += 5 

        # 2. README files (High Importance)
        if filename_lower.startswith('readme'):
            score += cls.HIGH_PRIORITY_SCORE
            if len(file_path.parts) <= (2 if file_path.is_absolute() else 1): score += 3 # Root README more important

        # 3. Important Extensions
        score += cls.IMPORTANT_EXTENSIONS.get(extension_lower, 0)

        # 4. Keywords in Path (More subtle boost/penalty)
        for part in file_path.parts:
            part_lower = part.lower()
            if part_lower in cls.IMPORTANT_KEYWORDS_IN_PATH:
                score += cls.IMPORTANT_KEYWORDS_IN_PATH[part_lower]
            # Special case for __init__.py as it's very Python specific
            if part_lower == '__init__.py': score += cls.IMPORTANT_KEYWORDS_IN_PATH.get('__init__.py', 5)


        # 5. Depth Penalty
        depth = len(file_path.parts) -1 # 0-indexed depth
        if depth >= cls.DEPTH_PENALTY_START:
            score -= (depth - cls.DEPTH_PENALTY_START + 1) * cls.DEPTH_PENALTY_FACTOR
        
        # 6. Low Priority Patterns (Strongest Penalty)
        for pattern in cls.LOW_PRIORITY_PATTERNS:
            if re.search(pattern, filepath_str_lower):
                score -= cls.MEDIUM_PRIORITY_SCORE * 1.2 # Significant penalty
                # If it's a test file, penalize even more, but not below a certain threshold
                if 'test' in pattern or 'spec' in pattern: score -= 5 
                break # Apply first matching low-priority penalty

        # Clamp score to a reasonable positive range, e.g., 0 to 50
        final_score = max(0, min(int(round(score)), 50))
        
        return final_score


class RegexFilter:
    def __init__(self, pattern_str: str = ""): # Renamed from pattern to pattern_str
        self.pattern_str = pattern_str 
        self.compiled_pattern: Optional[re.Pattern[str]] = None
        self.is_valid = True
        
        if pattern_str: # Only compile if pattern is not empty
            try:
                self.compiled_pattern = re.compile(pattern_str)
            except re.error:
                self.is_valid = False # Caller (bash script or python main) should warn/error
    
    def matches(self, file_path_as_str: str) -> bool:
        if not self.pattern_str: # No pattern means match all
            return True
        if not self.is_valid or not self.compiled_pattern: # Invalid or uncompiled pattern means trouble
            return False # Or True, depending on desired behavior for invalid patterns. False is safer.
        
        return bool(self.compiled_pattern.search(file_path_as_str))


class SmartArchiver:
    # Glob-like patterns for exclusion. These are matched against Path.match().
    # These should be quite specific to avoid over-excluding.
    # Order can matter if more specific patterns should override general ones (not an issue here).
    SEMANTIC_EXCLUDES_GLOBS = {
        # Common IDE/OS files (usually at root or specific hidden dirs)
        '.idea/**', '.vscode/**', '.project', '.classpath', '.settings/**',
        '.DS_Store', 'Thumbs.db',
        # Version Control
        '.git/**', '.hg/**', '.svn/**',
        # Language specific cache/build
        '**/__pycache__/**', '*.pyc', '*.pyo',
        '**/node_modules/**', '**/bower_components/**', '**/jspm_packages/**',
        '**/target/**', # Java (Maven/Gradle), Rust (Cargo)
        '**/build/**', # Gradle, CMake, general build outputs
        '**/dist/**', # Common for distribution files
        '**/out/**', # Common for output files
        # Logs, temp files, lock files
        '*.log', '*.log.*', '*~', '*.swp', '*.swo', '*.tmp', '*.bak', '*.old',
        '*lock*', # e.g., package-lock.json, poetry.lock, Gemfile.lock, composer.lock
        # Minified/Bundled (often not useful for LLM context)
        '*.min.js', '*.min.css', '*.bundle.js', '*.bundle.css', '*.map',
        # Archives and heavy binaries (already handled by BINARY_EXTENSIONS, but good for explicit skip)
        '*.pak', '*.zip', '*.tar', '*.gz', '*.bz2', '*.rar', '*.7z', '*.jar', '*.war', '*.ear',
        '*.exe', '*.dll', '*.so', '*.dylib', '*.o', '*.obj', '*.a', '*.lib',
        # Vendored dependencies (if not covered by node_modules etc.)
        'vendor/**', 'vendors/**', 'third_party/**', 'external/**',
        # Generated code (if clearly marked, less common as a generic pattern)
        # '*generated*', # This might be too broad, use with caution. Specific paths are better.
    }
    
    BINARY_EXTENSIONS = { # Add more as needed
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp', '.ico', 
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.odp',
        '.mp3', '.wav', '.aac', '.ogg', '.flac', '.opus',
        '.mp4', '.avi', '.mov', '.wmv', '.mkv', '.webm', '.flv',
        '.db', '.sqlite', '.sqlite3', '.mdb', '.accdb', '.dat', # .dat is very generic
        '.woff', '.woff2', '.ttf', '.otf', '.eot',
        '.iso', '.img', '.bin', # Disk images, generic binary data
        '.psd', '.ai', '.indd', '.xd', # Adobe proprietary
        '.fig', '.sketch', # Design files
        '.class', # Java class files
        '.wasm', # WebAssembly
        # Already in SEMANTIC_EXCLUDES_GLOBS, but reinforces binary nature
        '.zip', '.tar', '.gz', '.bz2', '.rar', '.7z', '.jar', '.war', '.ear',
        '.exe', '.dll', '.so', '.dylib', '.o', '.obj', '.a', '.lib',
    }
    
    def __init__(self, config: ArchiveConfig):
        self.config = config
        self.total_token_count = 0 # Renamed from token_count for clarity
        self.archive_uuid = self._generate_archive_uuid() # Renamed from archive_id
        self.included_file_count = 0 # Renamed from file_count
        
        # Setup compression strategies
        ast_compressor = ASTCompression() if AST_AVAILABLE else AggressiveTextCompression()
        if AST_AVAILABLE and self.config.compression_level in ['aggressive', 'smart']:
            if not config.quiet: print("pak_core: AST compression enabled for 'aggressive'/'smart' modes.", file=sys.stderr)
        elif not AST_AVAILABLE and self.config.compression_level in ['aggressive', 'smart']:
            if not config.quiet: print("pak_core: AST not available. 'aggressive'/'smart' modes will use text-based methods.", file=sys.stderr)


        self.compression_strategies: Dict[str, CompressionStrategy] = {
            'none': NoneCompression(),
            'light': LightCompression(), 
            'medium': MediumCompression(),
            'aggressive': ast_compressor, # AST or Text-Aggressive based on AST_AVAILABLE
            # 'smart' mode will pick one of the above per file.
        }
    
    def _generate_archive_uuid(self) -> str:
        import uuid
        return str(uuid.uuid4())
    
    def create_archive(self) -> str:
        files_to_process = self._collect_files()
        
        if not files_to_process:
            if not self.config.quiet:
                print("pak_core: No files found matching include/exclude criteria.", file=sys.stderr)
            return ""
        
        if self.config.compression_level == 'smart':
            processed_entries = self._smart_process_files(files_to_process)
        else:
            # Get the single strategy for non-smart modes
            strategy = self.compression_strategies[self.config.compression_level]
            processed_entries = self._standard_process_files(files_to_process, strategy)
        
        self.included_file_count = len(processed_entries)
        return self._generate_archive_output_string(processed_entries)
    
    def _collect_files(self) -> List[Path]:
        collected_paths: Set[Path] = set()
        base_paths_for_relativization: List[Path] = [] # For making paths relative in archive

        # Determine base paths for relativization from targets
        for target_str in self.config.targets:
            target_p = Path(target_str)
            # If target is a file, its parent is a base. If a dir, it itself is a base.
            # Resolve to make them absolute for reliable common ancestor logic later.
            if target_p.is_file():
                base_paths_for_relativization.append(target_p.resolve().parent)
            elif target_p.is_dir():
                base_paths_for_relativization.append(target_p.resolve())
            # Silently ignore non-existent targets, or print warning if not quiet
            elif not self.config.quiet and not target_p.exists():
                print(f"pak_core: Warning: Target '{target_str}' not found.", file=sys.stderr)


        common_ancestor = Path(os.path.commonpath([p for p in base_paths_for_relativization if p.is_dir()])) if base_paths_for_relativization else Path.cwd().resolve()
        # If no common directories, CWD is a fallback common ancestor.
        if not common_ancestor.is_dir() or not base_paths_for_relativization : # Ensure common_ancestor is valid or fallback
            common_ancestor = Path.cwd().resolve()


        for target_str in self.config.targets:
            target_p = Path(target_str)
            if not target_p.exists(): continue # Already warned above if configured

            abs_target = target_p.resolve()
            
            if abs_target.is_file():
                if self._should_include_file(abs_target, common_ancestor) and abs_target not in collected_paths:
                    collected_paths.add(abs_target)
            elif abs_target.is_dir():
                for item in abs_target.rglob('*'):
                    if item.is_file() and self._should_include_file(item, common_ancestor) and item not in collected_paths:
                        collected_paths.add(item)
        
        # Store common_ancestor for use in _generate_archive_output_string
        self.common_ancestor_for_paths = common_ancestor
        return sorted(list(collected_paths))

    def _should_include_file(self, file_path: Path, common_ancestor: Path) -> bool:
        # Path must be absolute and resolved for reliable checks. file_path is assumed to be so.
        if file_path.suffix.lower() in self.BINARY_EXTENSIONS: return False

        # Semantic Exclusions (Globs) - match against path relative to common ancestor or full path
        # Path.match() is tricky with '**/' at the start if path isn't relative in the right way.
        # It's often easier to convert to string and use fnmatch or regex for complex patterns.
        # For SEMANTIC_EXCLUDES_GLOBS, we test against different relative versions.
        try:
            path_relative_to_common = file_path.relative_to(common_ancestor)
        except ValueError: # Not under common ancestor (e.g. /foo and /bar/baz)
            path_relative_to_common = None # Cannot make relative in a simple way

        for glob_pattern in self.SEMANTIC_EXCLUDES_GLOBS:
            if file_path.match(glob_pattern): return False # Match against full absolute path
            if path_relative_to_common and path_relative_to_common.match(glob_pattern): return False
            # A simple string check for parts of pattern if it's not a strict glob
            # e.g., if 'node_modules' should match '/path/to/node_modules/file'
            if glob_pattern.strip('*') in str(file_path.as_posix()): # Basic substring check for non-wildcard parts
                 # This check needs to be more robust or rely on well-formed globs like `**/node_modules/**`
                 # For example, `*lock*` should match `poetry.lock` or `package-lock.json`
                 if glob_pattern == '*lock*': # Special handling for common lock files
                     if 'lock' in file_path.name.lower(): return False
                 elif f"/{glob_pattern.strip('*')}/" in str(file_path.as_posix()): # e.g. /node_modules/
                     return False


        if self.config.include_extensions:
            # Ensure extensions in config start with a dot and are lowercased for comparison
            normalized_config_extensions = {
                (ext if ext.startswith('.') else '.' + ext).lower() 
                for ext in self.config.include_extensions
            }
            if file_path.suffix.lower() not in normalized_config_extensions:
                return False
        
        try:
            if file_path.stat().st_size > 75 * 1024 * 1024: # 75 MB limit for text files
                if not self.config.quiet:
                    print(f"pak_core: Skipping very large text file (>75MB): {file_path}", file=sys.stderr)
                return False
        except FileNotFoundError: return False
        return True
    
    def _estimate_tokens_from_str(self, content: str) -> int:
        return (len(content) + 3) // 4 
    
    def _process_file_entry(self, file_path: Path, chosen_strategy: CompressionStrategy, current_budget_remaining: Optional[int]) -> Optional[FileEntry]:
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            lang = LanguageDetector.detect(file_path)
            importance = FilePrioritizer.calculate_importance(file_path)
            original_tokens = self._estimate_tokens_from_str(content)

            compressed_content, method_desc = chosen_strategy.compress(content, file_path, lang)
            compressed_tokens = self._estimate_tokens_from_str(compressed_content)

            # If budget is constrained, check if this file fits
            if current_budget_remaining is not None and compressed_tokens > current_budget_remaining:
                if not self.config.quiet:
                    print(f"pak_core: Skipping {file_path} ({compressed_tokens} tokens) due to budget (rem: {current_budget_remaining}). Method: {method_desc}", file=sys.stderr)
                return None # File does not fit

            return FileEntry(
                path=file_path, language=lang, importance=importance,
                original_tokens=original_tokens,
                compressed_content=compressed_content, compressed_tokens=compressed_tokens,
                compression_method=method_desc,
                size=file_path.stat().st_size,
                lines=compressed_content.count('\n') + 1
            )
        except FileNotFoundError:
            if not self.config.quiet: print(f"pak_core: File not found during processing: {file_path}. Skipping.", file=sys.stderr)
        except Exception as e:
            if not self.config.quiet: print(f"pak_core: Error processing {file_path}: {e}. Skipping.", file=sys.stderr)
        return None

    def _smart_process_files(self, files: List[Path]) -> List[FileEntry]:
        # Create initial entries with importance and original tokens for sorting
        initial_entries: List[Tuple[Path, int, int]] = [] # path, importance, original_tokens
        for p in files:
            try:
                # Quick read for token estimate, full read later during compression
                # This avoids holding all file contents in memory if many large files.
                # However, for small files, reading twice is minor.
                # For simplicity in this stage, estimate tokens based on size as a proxy.
                # True token count comes later. Importance is key here.
                size_bytes = p.stat().st_size
                original_tokens_est = size_bytes // 4 # Very rough proxy for sorting
                importance = FilePrioritizer.calculate_importance(p)
                initial_entries.append((p, importance, original_tokens_est))
            except Exception: pass # Skip files that can't be stat'd

        initial_entries.sort(key=lambda x: (-x[1], x[2])) # Sort by importance (desc), then token_est (asc)
        
        processed_entries: List[FileEntry] = []
        current_total_tokens = 0
        
        for file_path, importance_score, _ in initial_entries:
            budget_remaining = (self.config.max_tokens - current_total_tokens) if self.config.max_tokens > 0 else None
            if budget_remaining is not None and budget_remaining <= 0: # No budget left
                if not self.config.quiet: print("pak_core: Token budget exhausted. Stopping.", file=sys.stderr)
                break

            # Determine compression strategy for this file
            comp_level_name = 'aggressive' # Default
            if importance_score >= FilePrioritizer.HIGH_PRIORITY_SCORE * 0.8: # e.g. >= 20 if max possible is ~25-30 from calc
                comp_level_name = 'light'
            elif importance_score >= FilePrioritizer.MEDIUM_PRIORITY_SCORE * 0.8: # e.g. >= 12
                comp_level_name = 'medium'
            
            chosen_strategy = self.compression_strategies[comp_level_name]
            
            # Process the file with the chosen strategy
            entry = self._process_file_entry(file_path, chosen_strategy, budget_remaining)

            if entry:
                # If budget is tight, and we didn't use aggressive, try aggressive
                if budget_remaining is not None and entry.compressed_tokens > budget_remaining and comp_level_name != 'aggressive':
                    if not self.config.quiet:
                        print(f"pak_core: Tight budget for {file_path} with {comp_level_name}. Retrying with aggressive.", file=sys.stderr)
                    aggressive_strategy = self.compression_strategies['aggressive']
                    revised_entry = self._process_file_entry(file_path, aggressive_strategy, budget_remaining)
                    if revised_entry and (revised_entry.compressed_tokens <= entry.compressed_tokens or revised_entry.compressed_tokens <= budget_remaining) :
                        entry = revised_entry # Use more compressed version if it helps or fits
                    # If aggressive still doesn't fit, it will be skipped by next budget check or by _process_file_entry returning None
                
                if entry and (budget_remaining is None or entry.compressed_tokens <= budget_remaining) :
                    processed_entries.append(entry)
                    current_total_tokens += entry.compressed_tokens
                # else: entry was None or still didn't fit after potential retry
            # else: file processing failed or skipped by budget inside _process_file_entry
        
        self.total_token_count = current_total_tokens
        return processed_entries

    def _standard_process_files(self, files: List[Path], strategy: CompressionStrategy) -> List[FileEntry]:
        processed_entries: List[FileEntry] = []
        current_total_tokens = 0
        # Files are already sorted by path from _collect_files

        for file_path in files:
            budget_remaining = (self.config.max_tokens - current_total_tokens) if self.config.max_tokens > 0 else None
            if budget_remaining is not None and budget_remaining <= 0:
                if not self.config.quiet: print("pak_core: Token budget exhausted. Stopping.", file=sys.stderr)
                break
            
            entry = self._process_file_entry(file_path, strategy, budget_remaining)
            if entry:
                processed_entries.append(entry)
                current_total_tokens += entry.compressed_tokens
        
        self.total_token_count = current_total_tokens
        return processed_entries

    def _generate_archive_output_string(self, entries: List[FileEntry]) -> str:
        archive_lines: List[str] = []
        
        archive_lines.append(f"__PAK_UUID__:{self.archive_uuid}")
        archive_lines.append(f"# Archive created with pak_core v{VERSION}")
        archive_lines.append(f"# Archive UUID: {self.archive_uuid}")
        archive_lines.append(f"# Compression Mode: {self.config.compression_level}")
        archive_lines.append(f"# AST Support: {'enabled' if AST_AVAILABLE else 'disabled'}")
        if self.config.include_extensions:
            archive_lines.append(f"# Extension Filter: {', '.join(self.config.include_extensions)}")
        if self.config.max_tokens > 0:
            archive_lines.append(f"# Token Limit: {self.config.max_tokens} (Estimated Total: {self.total_token_count})")
        else:
            archive_lines.append(f"# Estimated Total Tokens: {self.total_token_count}")
        archive_lines.append(f"# Total Files Included: {self.included_file_count}")
        archive_lines.append("") 
        
        for entry in entries:
            # Attempt to make path relative to the common ancestor found during collection
            try:
                display_path = entry.path.relative_to(self.common_ancestor_for_paths).as_posix()
            except (ValueError, AttributeError): # If common_ancestor_for_paths wasn't set or path not relative
                display_path = entry.path.as_posix() # Fallback to full path (POSIX style)
            
            # Ensure paths are not absolute in the archive unless intended (e.g. single abs file target)
            # If the original target was absolute and was the only one, display_path might be absolute.
            # This logic aims to keep paths relative to a sensible project root.
            if Path(display_path).is_absolute() and len(self.config.targets) > 1 : # Heuristic
                 # Try to use only the filename if it became unexpectedly absolute with multiple targets.
                 # This part needs careful thought on how to define "project root" for paths.
                 # For now, if it's still absolute, we use name, assuming user provided /abs/path/to/file.
                 if Path(display_path).name == display_path : # e.g. "/file.txt"
                     pass # It's a root file, that's okay.
                 else : # e.g. "/abs/path/file.txt" from multiple targets
                     display_path = entry.path.name # Just the filename as a fallback


            archive_lines.append(f"__PAK_FILE_{self.archive_uuid}_START__")
            archive_lines.append(f"Path: {display_path}")
            archive_lines.append(f"Language: {entry.language}")
            archive_lines.append(f"Importance: {entry.importance}") # Calculated score
            archive_lines.append(f"Size: {entry.size}") # Original size
            archive_lines.append(f"Original Tokens: {entry.original_tokens}")
            archive_lines.append(f"Compressed Lines: {entry.lines}") # Lines in compressed content
            archive_lines.append(f"Compressed Tokens: {entry.compressed_tokens}")
            archive_lines.append(f"Compression Method: {entry.compression_method}")
            archive_lines.append(f"__PAK_DATA_{self.archive_uuid}_START__")
            archive_lines.append(entry.compressed_content)
            # Ensure last line of content is followed by a newline before the END marker, if content not empty
            if entry.compressed_content and not entry.compressed_content.endswith('\n'):
                archive_lines.append("") 
            archive_lines.append(f"__PAK_DATA_{self.archive_uuid}_END__")
        
        if not self.config.quiet:
            print(f"pak_core: Archive content generation complete. Files: {self.included_file_count}, Total est. tokens: {self.total_token_count}.", file=sys.stderr)
        
        return '\n'.join(archive_lines)

# --- Standalone functions for extract/list, callable from Bash wrapper ---

def _get_archive_uuid_from_lines(content_lines: List[str]) -> Optional[str]:
    if not content_lines: return None
    first_line = content_lines[0]
    if first_line.startswith('__PAK_UUID__:'): return first_line[len('__PAK_UUID__:'):]
    if first_line.startswith('__PAK_ID__:'): return first_line[len('__PAK_ID__:'):] # Legacy
    return None

def extract_archive(archive_path: str, output_dir: str = ".", pattern: str = "") -> bool:
    archive_file = Path(archive_path)
    output_root = Path(output_dir)
    
    if not archive_file.is_file():
        print(f"Error: Archive file not found: {archive_path}", file=sys.stderr)
        return False
    
    try:
        output_root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error creating output directory '{output_root}': {e}", file=sys.stderr)
        return False

    full_content = archive_file.read_text(encoding='utf-8', errors='ignore')
    lines = full_content.splitlines() # Handles \n, \r\n, \r
    
    archive_uuid = _get_archive_uuid_from_lines(lines)
    if not archive_uuid:
        print("Error: Invalid pak archive format (missing __PAK_UUID__ or __PAK_ID__ header).", file=sys.stderr)
        return False

    regex_f = RegexFilter(pattern) # Renamed variable to avoid conflict
    if pattern and not regex_f.is_valid: # Check validity from RegexFilter
        print(f"Error: Invalid regex pattern '{pattern}'. Extraction aborted.", file=sys.stderr)
        return False

    # Get the quiet setting from an environment variable if possible, or default to False
    # This is a bit of a hack since extract_archive isn't part of the SmartArchiver class instance
    is_quiet = os.environ.get("PAK_CORE_QUIET_MODE", "false").lower() == "true"


    if not is_quiet:
        print(f"Extracting from: {archive_path} (UUID: {archive_uuid})")
        if pattern: print(f"Filter pattern: {regex_f.pattern_str}")

    current_file_rel_path: Optional[str] = None
    in_data = False
    data_buffer: List[str] = []
    extracted_c = 0
    total_in_archive = 0
    
    # Markers
    file_start_m = f"__PAK_FILE_{archive_uuid}_START__"
    data_start_m = f"__PAK_DATA_{archive_uuid}_START__"
    data_end_m = f"__PAK_DATA_{archive_uuid}_END__"

    for line_idx, line_text in enumerate(lines):
        if line_text == file_start_m:
            current_file_rel_path = None; in_data = False; data_buffer = []
            total_in_archive += 1
        elif line_text.startswith("Path: ") and not in_data:
            current_file_rel_path = line_text[len("Path: "):].strip()
        elif line_text == data_start_m:
            if current_file_rel_path: in_data = True; data_buffer = []
            else: print(f"Warning: Data section started at line {line_idx+1} without prior Path. Skipping.", file=sys.stderr)
        elif line_text == data_end_m:
            if current_file_rel_path and in_data:
                if regex_f.matches(current_file_rel_path):
                    # Ensure path is treated as relative to output_root
                    # Normalize path to prevent '..' escapes if any (though unlikely from good archives)
                    # Path.resolve() on a relative path makes it absolute from CWD.
                    # We want it relative to output_root.
                    path_to_extract = Path(current_file_rel_path)
                    # If path_to_extract is absolute (e.g. /foo/bar from archive), it overrides output_root.
                    # This can be a security risk. We should ensure it's relative.
                    # A simple way: if it's absolute, use its name only, or make it relative to a known root.
                    # For now, we assume paths in archive are intended to be relative.
                    # Convert to Path, then strip anchor if absolute to make it relative.
                    if path_to_extract.is_absolute():
                         # This behavior might need adjustment based on how paths are stored.
                         # If they are truly absolute from a different system, this will put them in output_root/name
                         if not is_quiet: print(f"Warning: Absolute path '{path_to_extract}' in archive. Extracting as '{path_to_extract.name}' in output dir.", file=sys.stderr)
                         path_to_extract = Path(path_to_extract.name)


                    final_output_path = (output_root / path_to_extract).resolve()
                    
                    # Security: Check if the resolved path is still within the intended output directory
                    if not str(final_output_path).startswith(str(output_root.resolve())):
                        print(f"Security Error: Path '{current_file_rel_path}' would write outside target '{output_root}'. Skipping.", file=sys.stderr)
                    else:
                        try:
                            final_output_path.parent.mkdir(parents=True, exist_ok=True)
                            # Join lines with '\n' because splitlines() removes them.
                            # This ensures consistent \n line endings in extracted files.
                            final_output_path.write_text('\n'.join(data_buffer), encoding='utf-8')
                            if not is_quiet : print(f"Extracted: {final_output_path.relative_to(output_root.resolve())}")
                            extracted_c += 1
                        except Exception as e_write:
                            print(f"Error writing file {final_output_path}: {e_write}", file=sys.stderr)
            in_data = False; current_file_rel_path = None
        elif in_data:
            data_buffer.append(line_text)
    
    if not is_quiet: print(f"\nExtraction complete: {extracted_c} of {total_in_archive} files extracted to '{output_root}'.")
    return True


def list_archive_contents(archive_path: str, pattern: str = "") -> bool:
    archive_file = Path(archive_path)
    if not archive_file.is_file():
        print(f"Error: Archive file not found: {archive_path}", file=sys.stderr)
        return False

    full_content = archive_file.read_text(encoding='utf-8', errors='ignore')
    lines = full_content.splitlines()

    archive_uuid = _get_archive_uuid_from_lines(lines)
    if not archive_uuid:
        print("Error: Invalid pak archive format (missing __PAK_UUID__ or __PAK_ID__ header).", file=sys.stderr)
        return False

    regex_f = RegexFilter(pattern)
    if pattern and not regex_f.is_valid:
        print(f"Error: Invalid regex pattern '{pattern}'. Listing aborted.", file=sys.stderr)
        return False

    # Get quiet mode for list function as well
    is_quiet = os.environ.get("PAK_CORE_QUIET_MODE", "false").lower() == "true"

    if not is_quiet:
        print(f"Archive: {archive_path} (UUID: {archive_uuid})")
        if pattern: print(f"Filter: {regex_f.pattern_str}")
        header_format = "{path:<55.55} {size:>10} {imp:>4} {tok_c:>8} {meth:<22.22}"
        print(header_format.format(path="Path", size="Size (B)", imp="Imp", tok_c="Tok (C)", meth="Method"))
        print("-" * (55 + 1 + 10 + 1 + 4 + 1 + 8 + 1 + 22))

    # Metadata parsing state
    meta: Dict[str, Optional[str]] = {'path':None, 'size':None, 'imp':None, 'tok_c':None, 'meth':None}
    in_file_meta_section = False
    listed_c = 0
    total_in_archive = 0

    file_start_m = f"__PAK_FILE_{archive_uuid}_START__"
    data_start_m = f"__PAK_DATA_{archive_uuid}_START__"

    for line_text in lines:
        if line_text == file_start_m:
            meta = {k: None for k in meta} # Reset metadata for new file
            in_file_meta_section = True
            total_in_archive += 1
        elif in_file_meta_section:
            if line_text.startswith("Path: "): meta['path'] = line_text[len("Path: "):].strip()
            elif line_text.startswith("Size: "): meta['size'] = line_text[len("Size: "):].strip()
            elif line_text.startswith("Importance: "): meta['imp'] = line_text[len("Importance: "):].strip()
            elif line_text.startswith("Compressed Tokens: "): meta['tok_c'] = line_text[len("Compressed Tokens: "):].strip()
            elif line_text.startswith("Compression Method: "): meta['meth'] = line_text[len("Compression Method: "):].strip()
            elif line_text.startswith("Method: "): meta['meth'] = line_text[len("Method: "):].strip() # Legacy
            
            elif line_text == data_start_m:
                in_file_meta_section = False # Meta section for this file ends
                if meta['path'] and regex_f.matches(meta['path']):
                    if not is_quiet:
                        display_path = meta['path']
                        if len(display_path) > 53: display_path = ".." + display_path[-51:]
                        
                        print(header_format.format(
                            path=display_path, 
                            size=meta['size'] or '?', 
                            imp=meta['imp'] or '?', 
                            tok_c=meta['tok_c'] or '?',
                            meth=meta['meth'] or 'unknown'
                        ))
                    listed_c += 1
    
    if not is_quiet:
        print("-" * (55 + 1 + 10 + 1 + 4 + 1 + 8 + 1 + 22))
        if pattern:
            print(f"Listed {listed_c} of {total_in_archive} files matching pattern.")
        else:
            print(f"Total files in archive: {total_in_archive}.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description=f"pak_core v{VERSION} - Python backend for pak3 file archiving.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('targets', nargs='*', default=['.'],
                       help='File(s) and/or director(y/ies) to archive. Default: current directory.')
    
    pack_opts = parser.add_argument_group('Packing Options')
    pack_opts.add_argument('--compression-level', '-c', default='none',
                       choices=['none', 'light', 'medium', 'aggressive', 'smart'],
                       help='Compression strategy:\n'
                            '  none: Raw content.\n'
                            '  light: Basic whitespace/empty line removal.\n'
                            '  medium: Light + basic comment removal.\n'
                            '  aggressive: AST-based (if available) or advanced text-based structure extraction.\n'
                            '  smart: Adaptive compression based on file importance & token budget.')
    pack_opts.add_argument('--max-tokens', '-m', type=int, default=0,
                       help='Approximate maximum total tokens for the archive (0 = unlimited).')
    pack_opts.add_argument('--ext', nargs='+', default=[],
                       help='Include only files with these extensions (e.g., .py .md .txt). Dot is optional.')
    
    parser.add_argument('--quiet', '-q', action='store_true', help='Suppress non-error messages to stderr.')
    parser.add_argument('--version', action='version', 
                        version=f'%(prog)s {VERSION} (AST Support: {"Enabled" if AST_AVAILABLE else "Disabled"})')

    args = parser.parse_args()
    
    # Propagate quiet mode to standalone functions if called via main (though usually not)
    if args.quiet:
        os.environ["PAK_CORE_QUIET_MODE"] = "true"
    else:
        os.environ.pop("PAK_CORE_QUIET_MODE", None)


    # Normalize extensions to ensure they start with a dot
    normalized_extensions = []
    if args.ext:
        for ext_arg in args.ext:
            normalized_extensions.append(ext_arg if ext_arg.startswith('.') else '.' + ext_arg)

    archiver_config = ArchiveConfig(
        compression_level=args.compression_level,
        max_tokens=args.max_tokens,
        include_extensions=normalized_extensions,
        targets=[Path(t) for t in args.targets], # Ensure targets are Path objects
        quiet=args.quiet
    )
    
    archiver_instance = SmartArchiver(archiver_config)
    generated_archive_content = archiver_instance.create_archive()
    
    if generated_archive_content:
        print(generated_archive_content, end='') # Print to stdout, no extra newline from print()
    else:
        # SmartArchiver already prints reasons if not quiet.
        # Exit with an error code if no content was produced.
        sys.exit(1)

if __name__ == '__main__':
    # This allows pak_core.py to be run as a script, primarily for packing.
    # The bash wrapper (pak3) will call specific functions like list_archive_contents or extract_archive directly.
    main()
