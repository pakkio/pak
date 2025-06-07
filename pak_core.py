"""
pak_core.py - Python business logic for pak4
Enhanced pak3 core with LLM semantic compression support + full command support + METHOD DIFF
Consolidates AST analysis, smart compression, semantic LLM compression, listing, extraction, and method-level diffs
MODIFIED: Added method diff extraction, verification, and application
FIXED: Tree-sitter API compatibility - query.captures() now returns dict format
"""

import sys
import os
import re
import argparse
import tempfile
import subprocess
import hashlib
import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set, Any
from abc import ABC, abstractmethod

try:
    from tree_sitter import Language, Parser, Node, Query # type: ignore
    import tree_sitter_languages # type: ignore
    try:
        import tree_sitter_python # type: ignore
    except ImportError:
        tree_sitter_python = None # type: ignore
    AST_AVAILABLE = True
except ImportError:
    AST_AVAILABLE = False
    Node = Any # type: ignore
    Query = Any # type: ignore
    Language = Any # type: ignore
    Parser = Any # type: ignore

VERSION = "4.1.0-method-diff"

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
    output_file: Optional[str] = None # For cache file generation

# NEW: Method diff data structures
@dataclass
class MethodDiff:
    file_path: str
    find_method: str  # Method signature to find (can be empty for append)
    until_exclude: str  # Method signature to stop before (can be empty)
    replace_with: str  # New method content (can be empty for deletion)
    
@dataclass
class DiffParseResult:
    diffs: List[MethodDiff]
    errors: List[str]
    is_valid: bool

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
        lines = content.splitlines()
        compressed_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped:  # Skip empty lines
                if line.startswith((' ', '\t')): # Check if line had leading whitespace
                    indent_len = len(line) - len(line.lstrip())
                    num_indents = indent_len // 4
                    remainder_spaces = indent_len % 4
                    normalized_indent = ('  ' * num_indents) + (' ' * remainder_spaces)
                    compressed_lines.append(normalized_indent + stripped)
                else:
                    compressed_lines.append(stripped)
        return '\n'.join(compressed_lines), "text-light (whitespace/empty lines)"

class MediumCompression(CompressionStrategy):
    def compress(self, content: str, file_path: Path, language:str) -> Tuple[str, str]:
        content, _ = LightCompression().compress(content, file_path, language)
        
        code_like_languages = {'python', 'javascript', 'typescript', 'java', 'c', 'cpp', 'go', 'rust', 'csharp', 'ruby', 'php', 'swift', 'kotlin', 'scala'}
        
        if language in code_like_languages:
            lines = content.splitlines()
            filtered_lines = []
            in_multiline_comment = False
            
            comment_patterns = {
                'python': r'^\s*#.*$',
                'ruby': r'^\s*#.*$',
                'javascript': r'^\s*//.*$',
                'typescript': r'^\s*//.*$',
                'java': r'^\s*//.*$',
                'c': r'^\s*//.*$',
                'cpp': r'^\s*//.*$',
                'go': r'^\s*//.*$',
                'rust': r'^\s*//.*$',
                'csharp': r'^\s*//.*$',
                'php': r'^\s*(#|//).*$',
                'swift': r'^\s*//.*$',
                'kotlin': r'^\s*//.*$',
                'scala': r'^\s*//.*$',
            }
            
            block_comment_start = {'c', 'cpp', 'java', 'javascript', 'typescript', 'css', 'csharp', 'go', 'rust', 'swift', 'kotlin', 'scala'}
            block_comment_end_pattern = r'\*/\s*$'
            
            for line in lines:
                stripped_line = line.strip()
                
                if language in block_comment_start:
                    if in_multiline_comment:
                        if re.search(block_comment_end_pattern, stripped_line):
                            in_multiline_comment = False
                        continue
                    elif stripped_line.startswith('/*'):
                        if re.search(block_comment_end_pattern, stripped_line) and not stripped_line.endswith('/**/'):
                            if not (stripped_line.count('/*') == 1 and stripped_line.count('*/') == 1 and stripped_line.find('/*') < stripped_line.find('*/')):
                                in_multiline_comment = True
                        else:
                            if not (stripped_line.count('/*') == 1 and stripped_line.count('*/') == 1 and stripped_line.find('/*') < stripped_line.find('*/')):
                                in_multiline_comment = True
                        if in_multiline_comment and not re.search(block_comment_end_pattern, stripped_line):
                            continue
                
                if language in comment_patterns and re.match(comment_patterns[language], stripped_line):
                    continue
                
                if language in block_comment_start and stripped_line.startswith('/*') and stripped_line.endswith('*/'):
                    if stripped_line.count('/*') == 1 and stripped_line.count('*/') == 1:
                        continue
                
                filtered_lines.append(line)
            
            content = '\n'.join(filtered_lines)
        
        return content, "text-medium (light+comments)"

class AggressiveTextCompression(CompressionStrategy):
    def compress(self, content: str, file_path: Path, language: str) -> Tuple[str, str]:
        method_suffix = "text-aggressive"
        
        if language == 'python':
            compressed = self._extract_python_structure_text(content)
            method_suffix += "-py"
        elif language in ['javascript', 'typescript']:
            compressed = self._extract_js_ts_structure_text(content)
            method_suffix += "-js"
        else:
            content, _ = MediumCompression().compress(content, file_path, language)
            lines = content.splitlines()
            if len(lines) > 40:
                compressed = "\n".join(lines[:20]) + "\n...\n" + "\n".join(lines[-20:])
            else:
                compressed = content
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
            if not stripped or stripped.startswith('#'):
                continue
            
            if stripped.startswith('import ') or stripped.startswith('from '):
                result.append(stripped)
                continue
            
            if stripped.startswith('class '):
                if in_class_block and class_methods_buffer:
                    result.append(current_class_header)
                    result.extend([f"    {m}" for m in class_methods_buffer])
                    result.append("")
                current_class_header = stripped.split(':')[0] + ":" if ':' in stripped else stripped + ":"
                in_class_block = True
                class_methods_buffer = []
                continue
            
            if stripped.startswith('def '):
                if not line_content.startswith((' ', '\t')) and in_class_block:
                    if class_methods_buffer:
                        result.append(current_class_header)
                        result.extend([f"    {m}" for m in class_methods_buffer])
                        result.append("")
                    in_class_block = False
                    class_methods_buffer = []
                
                match = re.match(r'def\s+([^(]+\([^)]*\))', stripped)
                if match:
                    signature = match.group(1)
                    if '->' in stripped:
                        return_type_match = re.search(r'->\s*([^:]+):', stripped)
                        if return_type_match:
                            signature += f" -> {return_type_match.group(1).strip()}"
                    signature += ": ..."
                    if in_class_block:
                        class_methods_buffer.append(signature)
                    else:
                        result.append(signature)
                continue
            
            if not in_class_block and re.match(r'^[A-Z_][A-Z0-9_]*\s*=', stripped):
                result.append(stripped)
                continue
        
        if in_class_block and class_methods_buffer:
            result.append(current_class_header)
            result.extend([f"    {m}" for m in class_methods_buffer])
        
        return '\n'.join(result) if result else "# No Python structure found (text-aggressive)"

    def _extract_js_ts_structure_text(self, content: str) -> str:
        lines = content.splitlines()
        result = []
        
        structure_pattern = re.compile(
            r'^\s*(?:import|export|class|interface|type|function|const|let|var|async\s+function|\w+\s*=\s*async\s*\(|\w+\s*:\s*async\s*\()'
        )
        signature_end_pattern = re.compile(r'(\)\s*(?::\s*\w+)?\s*(?:=>)?\s*\{?)')
        
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('//') or stripped.startswith('/*'):
                continue
            
            if structure_pattern.match(stripped):
                sig_match = signature_end_pattern.search(stripped)
                if sig_match:
                    end_pos = sig_match.start(1)
                    line_to_add = stripped[:end_pos] + (") ..." if not stripped[end_pos-1] == ')' else " ...")
                else:
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
        
        if not AST_AVAILABLE:
            return None
        
        try:
            lang_obj = None
            if lang_name == 'python' and tree_sitter_python:
                lang_obj = Language(tree_sitter_python.language())
            elif lang_name in ['javascript', 'js']:
                lang_obj = tree_sitter_languages.get_language('javascript')
            elif lang_name == 'typescript':
                lang_obj = tree_sitter_languages.get_language('typescript')
            elif lang_name == 'java':
                lang_obj = tree_sitter_languages.get_language('java')
            elif lang_name == 'rust':
                lang_obj = tree_sitter_languages.get_language('rust')
            elif lang_name == 'c':
                lang_obj = tree_sitter_languages.get_language('c')
            elif lang_name == 'cpp':
                lang_obj = tree_sitter_languages.get_language('cpp')
            elif lang_name == 'go':
                lang_obj = tree_sitter_languages.get_language('go')
            elif lang_name == 'ruby':
                lang_obj = tree_sitter_languages.get_language('ruby')
            elif lang_name == 'php':
                lang_obj = tree_sitter_languages.get_language('php')
            elif lang_name == 'csharp':
                lang_obj = tree_sitter_languages.get_language('c_sharp')
            
            if lang_obj:
                self._languages[lang_name] = lang_obj
                return lang_obj
            return None
        except Exception:
            return None

    def _get_parser(self, language_name: str) -> Optional[Parser]:
        if language_name in self._parsers:
            return self._parsers[language_name]
        
        if not AST_AVAILABLE:
            return None
        
        lang_obj = self._get_language(language_name)
        if lang_obj:
            parser = Parser(lang_obj)
            self._parsers[language_name] = parser
            return parser
        return None

    def compress(self, content: str, file_path: Path, language: str) -> Tuple[str, str]:
        if not self.ast_available:
            return AggressiveTextCompression().compress(content, file_path, language)
        
        parser = self._get_parser(language)
        if not parser:
            return AggressiveTextCompression().compress(content, file_path, language)
        
        try:
            source_bytes = content.encode('utf-8')
            tree = parser.parse(source_bytes)
            
            compressed_content = ""
            if language == 'python':
                compressed_content = self._extract_python_ast(tree, source_bytes)
            elif language in ['javascript', 'typescript', 'js']:
                compressed_content = self._extract_js_ts_ast(tree, source_bytes, language)
            else:
                compressed_content = self._extract_generic_ast(tree, source_bytes, language)
            
            return compressed_content, "AST-aggressive"
        except Exception as e:
            return AggressiveTextCompression().compress(content, file_path, language)

    def _node_text(self, node: Node, source_bytes: bytes) -> str:
        return source_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')

    def _extract_definition_header(self, node: Node, source_bytes: bytes, language: str) -> str:
        """Extracts the header of a definition (e.g., function/class signature)."""
        full_node_text = self._node_text(node, source_bytes)
        first_line = full_node_text.splitlines()[0] if full_node_text else ""
        
        if language == 'python':
            if ':' in first_line:
                return first_line.split(':', 1)[0].strip() + ":"
            return first_line.strip()
        elif language in ['javascript', 'typescript', 'java', 'c', 'cpp', 'csharp', 'rust', 'go', 'swift', 'kotlin', 'scala']:
            if '{' in first_line:
                return first_line.split('{', 1)[0].strip()
            if ';' in first_line:
                return first_line.split(';', 1)[0].strip() + ";"
            return first_line.strip()
        
        return first_line.strip()

    def _query_ast(self, tree: Node, lang_obj: Language, query_string: str) -> Dict[str, List[Node]]:
        """FIXED: Returns dict format from modern tree-sitter API"""
        try:
            query = lang_obj.query(query_string)
            return query.captures(tree.root_node) # type: ignore
        except Exception:
            return {}  # Return empty dict instead of empty list

    def _extract_python_ast(self, tree: Node, source_bytes: bytes) -> str:
        lang_py = self._get_language('python')
        if not lang_py:
            return "# Python AST language not available"
        
        query_str = """
        (import_statement) @import
        (import_from_statement) @import_from
        (function_definition) @function
        (class_definition) @class
        (assignment) @assignment
        """
        
        captures = self._query_ast(tree, lang_py, query_str)
        elements = []
        
        for capture_name, nodes in captures.items():
            for node in nodes:
                if capture_name in ["import", "import_from"]:
                    elements.append(self._node_text(node, source_bytes).strip())
                elif capture_name in ["function", "class"]:
                    header = self._extract_definition_header(node, source_bytes, 'python')
                    elements.append(f"{header} ...")
                elif capture_name == "assignment":
                    assignment_text = self._node_text(node, source_bytes).strip()
                    if re.match(r'^[A-Z_][A-Z0-9_]*\s*=', assignment_text):
                        elements.append(assignment_text)
        
        return "\n".join(elements) if elements else "# No Python structure (AST)"

    def _extract_js_ts_ast(self, tree: Node, source_bytes: bytes, language: str) -> str:
        lang_obj = self._get_language(language)
        if not lang_obj:
            return f"# {language} AST language not available"
        
        query_str = """
        (import_statement) @import
        (export_statement) @export
        (lexical_declaration) @variable_declaration
        (function_declaration) @function
        (method_definition) @method
        (class_declaration) @class
        (interface_declaration) @interface
        (type_alias_declaration) @type_alias
        """
        
        captures = self._query_ast(tree, lang_obj, query_str)
        elements = []
        processed_node_ids = set()
        
        for capture_name, nodes in captures.items():
            for node in nodes:
                if node.id in processed_node_ids:
                    continue
                processed_node_ids.add(node.id)
                
                if capture_name in ["import", "export"]:
                    elements.append(self._node_text(node, source_bytes).strip().split(';')[0])
                elif capture_name in ["variable_declaration", "function", "method", "class", "interface", "type_alias"]:
                    header = self._extract_definition_header(node, source_bytes, language)
                    if header.endswith('{'):
                        elements.append(header + " ... }")
                    elif header.endswith(';'):
                        elements.append(header)
                    else:
                        elements.append(f"{header} {{ ... }}")
        
        return "\n".join(elements) if elements else f"# No {language} structure (AST)"

    def _extract_generic_ast(self, tree: Node, source_bytes: bytes, language: str) -> str:
        lang_obj = self._get_language(language)
        if not lang_obj:
            return f"# {language} AST language not available for generic extraction"
        
        possible_def_types = [
            "function_definition", "function_declaration", "method_definition", "subroutine_declaration",
            "class_definition", "class_declaration", "struct_definition", "struct_declaration", "module_definition",
            "interface_declaration", "enum_declaration", "type_definition", "type_alias_declaration",
            "import_statement", "export_statement", "package_declaration", "namespace_definition",
            "global_variable_declaration", "constant_declaration"
        ]
        
        query_str_parts = [f"({node_type}) @definition" for node_type in possible_def_types]
        elements = []
        
        if query_str_parts:
            captures = self._query_ast(tree, lang_obj, "\n".join(query_str_parts))
            processed_node_ids = set()
            
            for capture_name, nodes in captures.items():
                for node in nodes:
                    if node.id in processed_node_ids:
                        continue
                    processed_node_ids.add(node.id)
                    
                    header = self._extract_definition_header(node, source_bytes, language)
                    elements.append(header + " ...")
        
        if not elements:
            max_depth = 3
            def limited_traverse(current_node: Node, depth: int):
                if depth > max_depth:
                    return
                
                if "definition" in current_node.type or "declaration" in current_node.type or \
                   current_node.type in ["import_statement", "export_statement"]:
                    header = self._extract_definition_header(current_node, source_bytes, language)
                    elements.append(header + " ...")
                
                for child in current_node.children: # type: ignore
                    limited_traverse(child, depth + 1)
            
            if tree.root_node: # type: ignore
                limited_traverse(tree.root_node, 0) # type: ignore
        
        return "\n".join(elements) if elements else f"# No generic structure (AST, {language})"

# NEW: Method Diff System
class MethodSignatureExtractor:
    """Extracts method signatures for different programming languages"""
    
    METHOD_PATTERNS = {
        'python': [
            r'^\s*(def\s+\w+\s*\([^)]*\)(?:\s*->\s*[^:]+)?)\s*:',
            r'^\s*(async\s+def\s+\w+\s*\([^)]*\)(?:\s*->\s*[^:]+)?)\s*:'
        ],
        'java': [
            r'^\s*(?:public|private|protected)?\s*(?:static)?\s*(?:final)?\s*\w+\s+(\w+\s*\([^)]*\))\s*(?:throws\s+[^{]+)?\s*\{',
            r'^\s*(?:public|private|protected)?\s*(\w+\s*\([^)]*\))\s*(?:throws\s+[^{]+)?\s*\{'
        ],
        'javascript': [
            r'^\s*(function\s+\w+\s*\([^)]*\))\s*\{',
            r'^\s*(\w+)\s*:\s*function\s*\([^)]*\)\s*\{',
            r'^\s*(?:async\s+)?(\w+)\s*\([^)]*\)\s*(?:=>\s*)?\{',
            r'^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>'
        ],
        'typescript': [
            r'^\s*(?:public|private|protected)?\s*(?:async\s+)?(\w+)\s*\([^)]*\)\s*(?::\s*[^{]+)?\s*\{',
            r'^\s*(function\s+\w+\s*\([^)]*\)(?:\s*:\s*[^{]+)?)\s*\{',
            r'^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*(?::\s*[^=]+)?\s*=>'
        ],
        'csharp': [
            r'^\s*(?:public|private|protected|internal)?\s*(?:static)?\s*(?:virtual|override)?\s*\w+\s+(\w+\s*\([^)]*\))\s*\{',
            r'^\s*(?:public|private|protected|internal)?\s*(\w+\s*\([^)]*\))\s*\{'
        ],
        'go': [
            r'^\s*(func\s+(?:\(\w+\s+\*?\w+\)\s+)?\w+\s*\([^)]*\)(?:\s*[^{]+)?)\s*\{',
        ],
        'rust': [
            r'^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+\s*\([^)]*\)(?:\s*->\s*[^{]+)?)\s*\{',
        ]
    }
    
    @classmethod
    def extract_signatures(cls, content: str, language: str) -> List[Tuple[str, int, int]]:
        """Extract method signatures with their line positions.
        Returns list of (signature, start_line, body_start_line)"""
        patterns = cls.METHOD_PATTERNS.get(language, cls.METHOD_PATTERNS.get('python', []))
        signatures = []
        lines = content.splitlines()
        
        for i, line in enumerate(lines):
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    sig = match.group(1) if match.groups() else match.group(0)
                    # Find where the method body starts (after the signature line)
                    body_start = i + 1
                    # For languages with opening braces, body starts on the same line
                    if language in ['java', 'javascript', 'typescript', 'csharp', 'go', 'rust'] and '{' in line:
                        body_start = i
                    signatures.append((sig.strip(), i, body_start))
                    break
        
        return signatures

class MethodDiffExtractor:
    """Extracts differences between files at method level"""
    
    def __init__(self):
        self.signature_extractor = MethodSignatureExtractor()
    
    def extract_diff_between_files(self, original_file: Path, modified_file: Path) -> List[MethodDiff]:
        """Extract method-level differences between two files"""
        if not original_file.exists() or not modified_file.exists():
            return []
        
        orig_content = original_file.read_text(encoding='utf-8', errors='ignore')
        mod_content = modified_file.read_text(encoding='utf-8', errors='ignore')
        
        language = LanguageDetector.detect(original_file)
        
        orig_methods = self._extract_methods_with_content(orig_content, language)
        mod_methods = self._extract_methods_with_content(mod_content, language)
        
        diffs = []
        file_path = str(modified_file)
        
        # Find modified methods
        for mod_sig, mod_content in mod_methods.items():
            if mod_sig in orig_methods:
                if orig_methods[mod_sig] != mod_content:
                    # Method was modified
                    next_method = self._find_next_method(mod_sig, list(mod_methods.keys()))
                    diffs.append(MethodDiff(
                        file_path=file_path,
                        find_method=mod_sig,
                        until_exclude=next_method,
                        replace_with=mod_content
                    ))
            else:
                # New method - append to end
                diffs.append(MethodDiff(
                    file_path=file_path,
                    find_method="",
                    until_exclude="",
                    replace_with=mod_content
                ))
        
        # Find deleted methods
        for orig_sig in orig_methods:
            if orig_sig not in mod_methods:
                next_method = self._find_next_method(orig_sig, list(orig_methods.keys()))
                diffs.append(MethodDiff(
                    file_path=file_path,
                    find_method=orig_sig,
                    until_exclude=next_method,
                    replace_with=""  # Empty = deletion
                ))
        
        return diffs
    
    def _extract_methods_with_content(self, content: str, language: str) -> Dict[str, str]:
        """Extract methods with their full content"""
        signatures = self.signature_extractor.extract_signatures(content, language)
        lines = content.splitlines()
        methods = {}
        
        for i, (sig, start_line, body_start) in enumerate(signatures):
            # Find the end of this method (start of next method or end of file)
            if i + 1 < len(signatures):
                end_line = signatures[i + 1][1]
            else:
                end_line = len(lines)
            
            # Extract the complete method
            method_lines = lines[start_line:end_line]
            # Remove trailing empty lines
            while method_lines and not method_lines[-1].strip():
                method_lines.pop()
            
            methods[sig] = '\n'.join(method_lines)
        
        return methods
    
    def _find_next_method(self, current_sig: str, all_signatures: List[str]) -> str:
        """Find the next method signature after the current one"""
        try:
            current_idx = all_signatures.index(current_sig)
            if current_idx + 1 < len(all_signatures):
                return all_signatures[current_idx + 1]
        except ValueError:
            pass
        return ""

class MethodDiffParser:
    """Parses method diff files"""
    
    @staticmethod
    def parse_diff_file(diff_content: str) -> DiffParseResult:
        """Parse a method diff file and return structured data"""
        lines = diff_content.splitlines()
        diffs = []
        errors = []
        
        current_diff = None
        in_replace_with = False
        replace_with_lines = []
        
        for line_num, line in enumerate(lines, 1):
            line = line.rstrip()
            
            if line.startswith('FILE: '):
                # Finalize previous diff if any
                if current_diff is not None:
                    if in_replace_with:
                        current_diff.replace_with = '\n'.join(replace_with_lines)
                    diffs.append(current_diff)
                
                file_path = line[6:].strip()
                current_diff = MethodDiff(file_path=file_path, find_method="", until_exclude="", replace_with="")
                in_replace_with = False
                replace_with_lines = []
                
            elif line.startswith('FIND_METHOD: '):
                if current_diff is None:
                    errors.append(f"Line {line_num}: FIND_METHOD without FILE declaration")
                    continue
                current_diff.find_method = line[13:].strip()
                
            elif line.startswith('UNTIL_EXCLUDE: '):
                if current_diff is None:
                    errors.append(f"Line {line_num}: UNTIL_EXCLUDE without FILE declaration")
                    continue
                current_diff.until_exclude = line[15:].strip()
                
            elif line.startswith('REPLACE_WITH:'):
                if current_diff is None:
                    errors.append(f"Line {line_num}: REPLACE_WITH without FILE declaration")
                    continue
                in_replace_with = True
                replace_with_lines = []
                # Check if there's content on the same line
                content_on_same_line = line[13:].strip()
                if content_on_same_line:
                    replace_with_lines.append(content_on_same_line)
                
            elif in_replace_with:
                replace_with_lines.append(line)
            
            elif line.strip() and current_diff is None:
                errors.append(f"Line {line_num}: Content outside of FILE block: {line}")
        
        # Finalize last diff
        if current_diff is not None:
            if in_replace_with:
                current_diff.replace_with = '\n'.join(replace_with_lines)
            diffs.append(current_diff)
        
        is_valid = len(errors) == 0 and len(diffs) > 0
        return DiffParseResult(diffs=diffs, errors=errors, is_valid=is_valid)

class MethodDiffApplier:
    """Applies method diffs to files"""
    
    def __init__(self):
        self.signature_extractor = MethodSignatureExtractor()
    
    def apply_diff(self, diff: MethodDiff, target_dir: Path) -> Tuple[bool, str]:
        """Apply a single method diff to the target file.
        Returns (success, error_message)"""
        target_file = target_dir / diff.file_path
        
        if not target_file.exists():
            return False, f"Target file does not exist: {target_file}"
        
        try:
            content = target_file.read_text(encoding='utf-8', errors='ignore')
            language = LanguageDetector.detect(target_file)
            
            if not diff.find_method:
                # Append new method to end of file
                new_content = content.rstrip() + '\n\n' + diff.replace_with + '\n'
            elif not diff.replace_with:
                # Delete method
                new_content = self._delete_method(content, diff.find_method, diff.until_exclude, language)
            else:
                # Replace method
                new_content = self._replace_method(content, diff.find_method, diff.until_exclude, diff.replace_with, language)
            
            # Write back to file
            target_file.write_text(new_content, encoding='utf-8')
            return True, ""
            
        except Exception as e:
            return False, f"Error applying diff to {target_file}: {str(e)}"
    
    def _find_method_boundaries(self, content: str, method_sig: str, until_exclude: str, language: str) -> Tuple[int, int]:
        """Find start and end line numbers for a method.
        Returns (start_line, end_line) or (-1, -1) if not found"""
        lines = content.splitlines()
        signatures = self.signature_extractor.extract_signatures(content, language)
        
        start_line = -1
        end_line = len(lines)
        
        # Find the target method
        for i, (sig, sig_start_line, body_start) in enumerate(signatures):
            if self._signature_matches(sig, method_sig):
                start_line = sig_start_line
                
                # Find end: either next method or until_exclude method
                if until_exclude:
                    # Look for until_exclude method
                    for j in range(i + 1, len(signatures)):
                        next_sig, next_start, _ = signatures[j]
                        if self._signature_matches(next_sig, until_exclude):
                            end_line = next_start
                            break
                elif i + 1 < len(signatures):
                    # Use next method as boundary
                    end_line = signatures[i + 1][1]
                
                break
        
        return start_line, end_line
    
    def _signature_matches(self, extracted_sig: str, target_sig: str) -> bool:
        """Check if two method signatures match (with some flexibility)"""
        # Normalize whitespace and compare
        extracted_norm = re.sub(r'\s+', ' ', extracted_sig.strip())
        target_norm = re.sub(r'\s+', ' ', target_sig.strip())
        
        # Exact match
        if extracted_norm == target_norm:
            return True
        
        # Check if target is a substring of extracted (partial matching)
        if target_norm in extracted_norm:
            return True
        
        # Extract just the method name and parameters for looser matching
        extract_name = self._extract_method_name(extracted_norm)
        target_name = self._extract_method_name(target_norm)
        
        return extract_name == target_name
    
    def _extract_method_name(self, signature: str) -> str:
        """Extract just the method name and basic parameters"""
        # Simple regex to extract method name pattern
        match = re.search(r'(\w+)\s*\([^)]*\)', signature)
        return match.group(0) if match else signature
    
    def _delete_method(self, content: str, method_sig: str, until_exclude: str, language: str) -> str:
        """Delete a method from the content"""
        lines = content.splitlines()
        start_line, end_line = self._find_method_boundaries(content, method_sig, until_exclude, language)
        
        if start_line == -1:
            return content  # Method not found, return unchanged
        
        # Remove the method lines
        new_lines = lines[:start_line] + lines[end_line:]
        return '\n'.join(new_lines)
    
    def _replace_method(self, content: str, method_sig: str, until_exclude: str, new_method: str, language: str) -> str:
        """Replace a method in the content"""
        lines = content.splitlines()
        start_line, end_line = self._find_method_boundaries(content, method_sig, until_exclude, language)
        
        if start_line == -1:
            # Method not found, append to end
            return content.rstrip() + '\n\n' + new_method + '\n'
        
        # Replace the method
        new_method_lines = new_method.splitlines()
        new_lines = lines[:start_line] + new_method_lines + lines[end_line:]
        return '\n'.join(new_lines)

# Continue with existing classes (SemanticCache, SemanticCompression, etc.)
class SemanticCache:
    """Manages SHA-256 based caching for semantic compression results"""
    
    def __init__(self, cache_file_path: Optional[str] = None):
        self.cache_file_path = cache_file_path
        self.cache_data: Dict[str, Dict[str, Any]] = {}
        self.cache_modified = False
        if cache_file_path:
            self._load_cache()
    
    def _load_cache(self) -> None:
        """Load existing cache from file"""
        if not self.cache_file_path or not Path(self.cache_file_path).exists():
            return
        
        try:
            with open(self.cache_file_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
                if isinstance(loaded_data, dict) and 'entries' in loaded_data:
                    self.cache_data = loaded_data['entries']
                    if not os.environ.get('PAK_QUIET', '').lower() == 'true':
                        print(f"pak_core: Loaded semantic cache with {len(self.cache_data)} entries", file=sys.stderr)
        except (json.JSONDecodeError, IOError) as e:
            if not os.environ.get('PAK_QUIET', '').lower() == 'true':
                print(f"pak_core: Warning: Could not load cache file {self.cache_file_path}: {e}", file=sys.stderr)
            self.cache_data = {}
    
    def _save_cache(self) -> None:
        """Save cache to file if modified"""
        if not self.cache_modified or not self.cache_file_path:
            return
        
        try:
            cache_output = {
                "cache_version": "1.0",
                "created": datetime.now().isoformat(),
                "entries": self.cache_data
            }
            Path(self.cache_file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file_path, 'w', encoding='utf-8') as f:
                json.dump(cache_output, f, indent=2, ensure_ascii=False)
            if not os.environ.get('PAK_QUIET', '').lower() == 'true':
                print(f"pak_core: Saved semantic cache with {len(self.cache_data)} entries", file=sys.stderr)
        except IOError as e:
            if not os.environ.get('PAK_QUIET', '').lower() == 'true':
                print(f"pak_core: Warning: Could not save cache file {self.cache_file_path}: {e}", file=sys.stderr)
    
    def _calculate_file_hash(self, content: str) -> str:
        """Calculate SHA-256 hash of file content"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def get_cached_result(self, file_path: str, content: str) -> Optional[Tuple[str, str]]:
        """Get cached compression result if file hasn't changed"""
        if not self.cache_file_path:
            return None
        
        file_hash = self._calculate_file_hash(content)
        cache_key = str(Path(file_path).as_posix())  # Normalize path
        
        if cache_key in self.cache_data:
            cached_entry = self.cache_data[cache_key]
            if cached_entry.get('sha256') == file_hash:
                if not os.environ.get('PAK_QUIET', '').lower() == 'true':
                    print(f"pak_core: Using cached semantic result for {Path(file_path).name}", file=sys.stderr)
                return cached_entry['semantic_result'], cached_entry['method']
        
        return None
    
    def store_result(self, file_path: str, content: str, semantic_result: str, method: str) -> None:
        """Store compression result in cache"""
        if not self.cache_file_path:
            return
        
        file_hash = self._calculate_file_hash(content)
        cache_key = str(Path(file_path).as_posix())  # Normalize path
        
        self.cache_data[cache_key] = {
            'sha256': file_hash,
            'semantic_result': semantic_result,
            'method': method + ' (cached)',
            'timestamp': datetime.now().isoformat(),
            'file_size': len(content)
        }
        self.cache_modified = True
    
    def finalize(self) -> None:
        """Save cache if needed (call at end of processing)"""
        if self.cache_modified:
            self._save_cache()

class SemanticCompression(CompressionStrategy):
    """LLM-based semantic compression using external semantic_compressor.py
    MODIFIED: Now ALWAYS applies semantic compression regardless of efficiency.
    ENHANCED: Added SHA-256 based caching to avoid repeated LLM calls."""
    
    def __init__(self, cache: Optional[SemanticCache] = None):
        self.compressor_path = os.environ.get('SEMANTIC_COMPRESSOR_PATH')
        self.fallback_strategy = ASTCompression() if AST_AVAILABLE else AggressiveTextCompression()
        self.cache = cache
    
    def compress(self, content: str, file_path: Path, language: str) -> Tuple[str, str]:
        if not self.compressor_path or not Path(self.compressor_path).exists():
            if not os.environ.get('PAK_QUIET', '').lower() == 'true':
                print("pak_core: Semantic compressor not found, falling back to AST/aggressive", file=sys.stderr)
            return self.fallback_strategy.compress(content, file_path, language)
        
        if not content.strip():
            return content, "semantic-skip (empty)"
        
        # Check cache first
        if self.cache:
            cached_result = self.cache.get_cached_result(str(file_path), content)
            if cached_result:
                return cached_result
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{language}', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            try:
                result = subprocess.run([
                    'python3', self.compressor_path,
                    temp_file_path, 'semantic', language
                ], capture_output=True, text=True, timeout=180)  # 3 minute timeout
                
                if result.returncode == 0:
                    compressed_content = result.stdout
                    original_size = len(content)
                    compressed_size = len(compressed_content)
                    
                    if compressed_size > 0:
                        compression_ratio = original_size / compressed_size
                        result_tuple = (compressed_content, f"semantic-llm ({compression_ratio:.1f}x ratio, always-applied)")
                        
                        # Store in cache
                        if self.cache:
                            self.cache.store_result(str(file_path), content, compressed_content, result_tuple[1])
                        
                        return result_tuple
                    else:
                        return self.fallback_strategy.compress(content, file_path, language)
                else:
                    error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                    if not os.environ.get('PAK_QUIET', '').lower() == 'true':
                        print(f"pak_core: Semantic compression failed for {file_path.name}: {error_msg}", file=sys.stderr)
                    return self.fallback_strategy.compress(content, file_path, language)
            
            finally:
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    pass
        
        except subprocess.TimeoutExpired:
            if not os.environ.get('PAK_QUIET', '').lower() == 'true':
                print(f"pak_core: Semantic compression timeout for {file_path.name}, using fallback", file=sys.stderr)
            return self.fallback_strategy.compress(content, file_path, language)
        except Exception as e:
            if not os.environ.get('PAK_QUIET', '').lower() == 'true':
                print(f"pak_core: Semantic compression error for {file_path.name}: {e}", file=sys.stderr)
            return self.fallback_strategy.compress(content, file_path, language)

# Continue with remaining classes (LanguageDetector, FilePrioritizer, etc.)
class LanguageDetector:
    EXTENSION_MAP = {
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
        '.c': 'c', '.h': 'c',
        '.cpp': 'cpp', '.hpp': 'cpp', '.cxx': 'cpp', '.hxx': 'cpp', '.cc': 'cpp', '.hh': 'cpp',
        '.go': 'go',
        '.rs': 'rust',
        '.pl': 'perl', '.pm': 'perl', '.t': 'perl',
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
        '.vb': 'vbnet',
        '.pas': 'pascal', '.pp': 'pascal', '.inc': 'pascal',
        '.lisp': 'lisp', '.lsp': 'lisp', '.cl': 'common-lisp',
        '.scm': 'scheme', '.ss': 'scheme',
        '.f': 'fortran', '.for': 'fortran', '.f77': 'fortran', '.f90': 'fortran', '.f95': 'fortran', '.f03': 'fortran',
        '.ada': 'ada', '.adb': 'ada', '.ads': 'ada',
        '.s': 'assembly', '.asm': 'assembly',
        '.d': 'd', '.di': 'd',
        '.cob': 'cobol', '.cbl': 'cobol',
        '.v': 'verilog', '.vh': 'verilog',
        '.vhd': 'vhdl', '.vhdl': 'vhdl',
        '.html': 'html', '.htm': 'html', '.xhtml': 'html',
        '.xml': 'xml', '.xsl': 'xml', '.xslt': 'xml', '.xsd': 'xml', '.rng': 'xml', '.plist': 'xml', '.csproj': 'xml', '.vbproj': 'xml', '.fsproj': 'xml', '.svg': 'xml',
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
        '.sh': 'bash', '.bash': 'bash', '.ksh': 'bash', '.zsh': 'bash', '.fish': 'fish',
        '.ps1': 'powershell', '.psm1': 'powershell', '.psd1': 'powershell',
        '.bat': 'batch', '.cmd': 'batch',
        '.vbs': 'vbscript',
        '.applescript': 'applescript', '.scpt': 'applescript',
        'makefile': 'makefile', 'gnumakefile': 'makefile', 'rakefile': 'ruby',
        'dockerfile': 'dockerfile', 'containerfile': 'dockerfile',
        '.jenkinsfile': 'groovy',
        'cmakelists.txt': 'cmake', '.cmake': 'cmake',
        '.sln': 'sln',
        '.css': 'css',
        '.scss': 'scss', '.sass': 'sass',
        '.less': 'less',
        '.styl': 'stylus',
        'package.json': 'json', 'bower.json': 'json', 'composer.json': 'json',
        'gemfile': 'ruby', 'build.gradle': 'groovy', 'pom.xml': 'xml',
        'requirements.txt': 'pip-requirements', 'pipfile': 'toml', 'pyproject.toml': 'toml',
        '.txt': 'text', '.text': 'text',
        '.log': 'log',
        '.sql': 'sql', '.ddl': 'sql', '.dml': 'sql',
        '.patch': 'diff', '.diff': 'diff',
        '.crt': 'pem', '.pem': 'pem', '.key': 'pem',
        '.asc': 'pgp', '.gpg': 'pgp',
        '.env': 'dotenv',
        '.gitattributes': 'gitattributes', '.gitignore': 'gitignore', '.gitmodules': 'gitmodules',
        '.editorconfig': 'editorconfig',
    }
    
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
        'build.gradle': 'groovy',
        'pom.xml': 'xml',
        'project.clj': 'clojure',
        'nginx.conf': 'nginx',
        'httpd.conf': 'apacheconf',
        'apache2.conf': 'apacheconf',
        '.bashrc': 'bash',
        '.zshrc': 'bash',
        '.profile': 'bash',
        '.bash_profile': 'bash',
        '.gitconfig': 'ini',
        'robots.txt': 'text',
        'license': 'text',
        'readme': 'markdown',
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
        
        if filename_lower in cls.FILENAME_MAP:
            if filename_lower == 'build.gradle' and file_path.suffix.lower() == '.kts':
                return 'kotlin'
            return cls.FILENAME_MAP[filename_lower]
        
        suffix_lower = file_path.suffix.lower()
        if suffix_lower and suffix_lower in cls.EXTENSION_MAP:
            return cls.EXTENSION_MAP[suffix_lower]
        
        current_lang_guess = 'generic'
        
        if not suffix_lower or cls.EXTENSION_MAP.get(suffix_lower, 'generic') in ['bash', 'sh', 'generic', 'text']:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    first_line = f.readline(256).strip()
                    if first_line.startswith('#!'):
                        if 'python3' in first_line:
                            return 'python'
                        if 'python' in first_line:
                            return 'python'
                        if 'bash' in first_line:
                            return 'bash'
                        if 'sh' in first_line:
                            return 'bash'
                        if 'perl' in first_line:
                            return 'perl'
                        if 'ruby' in first_line:
                            return 'ruby'
                        if 'node' in first_line:
                            return 'javascript'
                        if 'zsh' in first_line:
                            return 'bash'
                        if 'ksh' in first_line:
                            return 'bash'
                        if 'env php' in first_line:
                            return 'php'
                        if 'env groovy' in first_line:
                            return 'groovy'
            except Exception:
                pass
        
        if current_lang_guess == 'generic' and not suffix_lower:
            stem_lower = file_path.stem.lower()
            if stem_lower in cls.FILENAME_MAP:
                return cls.FILENAME_MAP[stem_lower]
        
        return current_lang_guess

class FilePrioritizer:
    HIGH_PRIORITY_SCORE = 25
    MEDIUM_PRIORITY_SCORE = 15
    LOW_PRIORITY_SCORE = 5
    NEUTRAL_SCORE = 10
    
    CRITICAL_FILENAMES = {
        'package.json', 'composer.json', 'gemfile', 'build.gradle', 'pom.xml',
        'pyproject.toml', 'pipfile', 'requirements.txt',
        'dockerfile', 'makefile', 'cmakelists.txt', 'kustomization.yaml', 'kustomization.yml',
        'main.py', 'main.js', 'main.ts', 'main.go', 'main.rs', 'main.java', 'main.kt', 'main.swift',
        'index.js', 'index.ts', 'index.html', 'app.py', 'app.js', 'app.ts', 'application.py',
        'manage.py', 'wsgi.py', 'asgi.py', 'vite.config.js', 'vite.config.ts', 'webpack.config.js',
        'next.config.js', 'nuxt.config.js', 'svelte.config.js', 'angular.json',
        '.env.example', '.env.template', 'settings.py', 'config.py', 'settings.yaml', 'config.yaml',
    }
    
    IMPORTANT_KEYWORDS_IN_PATH = {
        'src': 5, 'source': 5, 'app': 4, 'lib': 4, 'core': 6, 'server': 4, 'client': 3,
        'api': 5, 'routes': 4, 'controllers': 4, 'services': 4, 'handlers': 3, 'models': 4,
        'entities': 3, 'utils': 2, 'helpers': 2, 'common': 2, 'shared': 2, 'config': 6,
        'components': 3, 'widgets': 2, 'views': 3, 'templates': 2, 'schemas': 4,
        'migrations': 3, 'database': 4, 'store': 3, 'kernel': 5, 'entrypoint': 5,
        'workflow': 3, 'pipeline': 3, 'plugin': 3, 'module': 3, 'init': 4, '__init__.py': 6,
    }
    
    IMPORTANT_EXTENSIONS = {
        '.py': 10, '.js': 9, '.ts': 10, '.java': 8, '.go': 9, '.rs': 10, '.rb': 7, '.php': 6, '.swift': 9, '.kt': 9, '.scala': 7,
        '.h': 6, '.hpp': 7, '.c': 5, '.cpp': 6, '.cs': 7,
        '.sql': 6, '.proto': 5, '.graphql': 5, '.tf': 5,
        '.html': 5, '.css': 4, '.jsx': 7, '.tsx': 8, '.vue': 7, '.svelte': 7,
        '.sh': 3, '.bash': 3, '.ps1': 3,
        '.json': 2, '.xml': 1, '.yaml': 2, '.yml': 2, '.toml': 3,
        '.md': 4, '.rst': 3, '.txt': 1,
        '.ipynb': 3,
    }
    
    LOW_PRIORITY_PATTERNS = [
        r'[/\\]tests?[/\\]', r'[/\\]spec[/\\]', r'test_', r'_test\.', r'\.test\.', r'_spec\.', r'\.spec\.',
        r'[/\\]fixtures?[/\\]', r'[/\\]mocks?[/\\]', r'[/\\]doubles?[/\\]',
        r'[/\\]examples?[/\\]', r'[/\\]samples?[/\\]', r'[/\\]demos?[/\\]',
        r'[/\\]docs?[/\\]', r'[/\\]documentation[/\\]',
        r'changelog', r'contributing', r'license', r'code_of_conduct', r'security\.md',
        r'[/\\]vendor[/\\]', r'[/\\]third[-_]?party[/\\]', r'[/\\]external[/\\]',
        r'\.min\.(js|css)$', r'\.bundle\.(js|css)$', r'\.map$',
        r'[/\\]assets?[/\\]', r'[/\\]static[/\\]', r'[/\\]public[/\\]',
        r'[/\\]data[/\\]',
        r'^\.gitattributes$', r'^\.gitignore$', r'^\.gitmodules$', r'^\.npmignore$', r'^\.dockerignore$',
        r'^\.editorconfig$', r'^\.eslint', r'^\.prettier', r'^\.stylelint', r'^\.rubocop', r'^\.pylintrc$',
        r'^\.DS_Store$', r'^thumbs\.db$', r'\.bak$', r'\.tmp$', r'\.swp$', r'\.swo$', r'.*\.old$',
        r'.*\.log(\.\d*)?$',
        r'[/\\]benchmark[/\\]', r'[/\\]bench[/\\]',
        r'[/\\]__snapshots__[/\\]',
        r'[/\\]scripts?[/\\]',
        r'[/\\]tools?[/\\]',
    ]
    
    DEPTH_PENALTY_START = 4
    DEPTH_PENALTY_FACTOR = 1.5
    
    @classmethod
    def calculate_importance(cls, file_path: Path) -> int:
        score = float(cls.NEUTRAL_SCORE)
        filename_lower = file_path.name.lower()
        filepath_str_lower = str(file_path.as_posix()).lower()
        extension_lower = file_path.suffix.lower()
        
        if filename_lower in cls.CRITICAL_FILENAMES:
            score += cls.HIGH_PRIORITY_SCORE * 1.5
            if len(file_path.parts) <= (2 if file_path.is_absolute() else 1):
                score += 5
        
        if filename_lower.startswith('readme'):
            score += cls.HIGH_PRIORITY_SCORE
            if len(file_path.parts) <= (2 if file_path.is_absolute() else 1):
                score += 3
        
        score += cls.IMPORTANT_EXTENSIONS.get(extension_lower, 0)
        
        for part in file_path.parts:
            part_lower = part.lower()
            if part_lower in cls.IMPORTANT_KEYWORDS_IN_PATH:
                score += cls.IMPORTANT_KEYWORDS_IN_PATH[part_lower]
            if part_lower == '__init__.py':
                score += cls.IMPORTANT_KEYWORDS_IN_PATH.get('__init__.py', 5)
        
        depth = len(file_path.parts) - 1
        if depth >= cls.DEPTH_PENALTY_START:
            score -= (depth - cls.DEPTH_PENALTY_START + 1) * cls.DEPTH_PENALTY_FACTOR
        
        for pattern in cls.LOW_PRIORITY_PATTERNS:
            if re.search(pattern, filepath_str_lower):
                score -= cls.MEDIUM_PRIORITY_SCORE * 1.2
                if 'test' in pattern or 'spec' in pattern:
                    score -= 5
                break
        
        final_score = max(0, min(int(round(score)), 50))
        return final_score

class RegexFilter:
    def __init__(self, pattern_str: str = ""):
        self.pattern_str = pattern_str
        self.compiled_pattern: Optional[re.Pattern[str]] = None
        self.is_valid = True
        if pattern_str:
            try:
                self.compiled_pattern = re.compile(pattern_str)
            except re.error:
                self.is_valid = False

    def matches(self, file_path_as_str: str) -> bool:
        if not self.pattern_str:
            return True
        if not self.is_valid or not self.compiled_pattern:
            return False
        return bool(self.compiled_pattern.search(file_path_as_str))

class SmartArchiver:
    SEMANTIC_EXCLUDES_GLOBS = {
        '.idea/**', '.vscode/**', '.project', '.classpath', '.settings/**',
        '.DS_Store', 'Thumbs.db',
        '.git/**', '.hg/**', '.svn/**',
        '**/__pycache__/**', '*.pyc', '*.pyo',
        '**/node_modules/**', '**/bower_components/**', '**/jspm_packages/**',
        '**/target/**',
        '**/build/**',
        '**/dist/**',
        '**/out/**',
        '*.log', '*.log.*', '*~', '*.swp', '*.swo', '*.tmp', '*.bak', '*.old',
        '*lock*',
        '*.min.js', '*.min.css', '*.bundle.js', '*.bundle.css', '*.map',
        '*.pak', '*.zip', '*.tar', '*.gz', '*.bz2', '*.rar', '*.7z', '*.jar', '*.war', '*.ear',
        '*.exe', '*.dll', '*.so', '*.dylib', '*.o', '*.obj', '*.a', '*.lib',
        'vendor/**', 'vendors/**', 'third_party/**', 'external/**',
    }
    
    BINARY_EXTENSIONS = {
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp', '.ico',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.odp',
        '.mp3', '.wav', '.aac', '.ogg', '.flac', '.opus',
        '.mp4', '.avi', '.mov', '.wmv', '.mkv', '.webm', '.flv',
        '.db', '.sqlite', '.sqlite3', '.mdb', '.accdb', '.dat',
        '.woff', '.woff2', '.ttf', '.otf', '.eot',
        '.iso', '.img', '.bin',
        '.psd', '.ai', '.indd', '.xd',
        '.fig', '.sketch',
        '.class',
        '.wasm',
        '.zip', '.tar', '.gz', '.bz2', '.rar', '.7z', '.jar', '.war', '.ear',
        '.exe', '.dll', '.so', '.dylib', '.o', '.obj', '.a', '.lib',
    }
    
    def __init__(self, config: ArchiveConfig):
        self.config = config
        self.total_token_count = 0
        self.archive_uuid = self._generate_archive_uuid()
        self.included_file_count = 0
        
        # Set up caching for semantic compression
        cache_file_path = None
        if config.output_file and config.compression_level in ['semantic', 'smart']:
            cache_file_path = config.output_file + '.cache'
        self.semantic_cache = SemanticCache(cache_file_path) if cache_file_path else None
        
        # Set up compression strategies
        ast_compressor = ASTCompression() if AST_AVAILABLE else AggressiveTextCompression()
        semantic_compressor = SemanticCompression(self.semantic_cache)
        
        if AST_AVAILABLE and self.config.compression_level in ['aggressive', 'smart']:
            if not config.quiet:
                print("pak_core: AST compression enabled for 'aggressive'/'smart' modes.", file=sys.stderr)
        elif not AST_AVAILABLE and self.config.compression_level in ['aggressive', 'smart']:
            if not config.quiet:
                print("pak_core: AST not available. 'aggressive'/'smart' modes will use text-based methods.", file=sys.stderr)
        
        self.compression_strategies: Dict[str, CompressionStrategy] = {
            'none': NoneCompression(),
            'light': LightCompression(),
            'medium': MediumCompression(),
            'aggressive': ast_compressor,
            'semantic': semantic_compressor,  # New semantic compression level
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
            strategy = self.compression_strategies[self.config.compression_level]
            processed_entries = self._standard_process_files(files_to_process, strategy)
        
        self.included_file_count = len(processed_entries)
        
        # Finalize cache
        if self.semantic_cache:
            self.semantic_cache.finalize()
        
        return self._generate_archive_output_string(processed_entries)

    def _collect_files(self) -> List[Path]:
        collected_paths: Set[Path] = set()
        base_paths_for_relativization: List[Path] = []
        
        # Determine base paths for relativization
        for target_str in self.config.targets:
            target_p = Path(target_str)
            if target_p.is_file():
                base_paths_for_relativization.append(target_p.resolve().parent)
            elif target_p.is_dir():
                base_paths_for_relativization.append(target_p.resolve())
            elif not self.config.quiet and not target_p.exists():
                print(f"pak_core: Warning: Target '{target_str}' not found.", file=sys.stderr)
        
        # Find common ancestor for path relativization
        common_ancestor = Path(os.path.commonpath([p for p in base_paths_for_relativization if p.is_dir()])) if base_paths_for_relativization else Path.cwd().resolve()
        if not common_ancestor.is_dir() or not base_paths_for_relativization:
            common_ancestor = Path.cwd().resolve()
        
        # Collect files from all targets
        for target_str in self.config.targets:
            target_p = Path(target_str)
            if not target_p.exists():
                continue
            
            abs_target = target_p.resolve()
            if abs_target.is_file():
                if self._should_include_file(abs_target, common_ancestor) and abs_target not in collected_paths:
                    collected_paths.add(abs_target)
            elif abs_target.is_dir():
                for item in abs_target.rglob('*'):
                    if item.is_file() and self._should_include_file(item, common_ancestor) and item not in collected_paths:
                        collected_paths.add(item)
        
        self.common_ancestor_for_paths = common_ancestor
        return sorted(list(collected_paths))

    def _should_include_file(self, file_path: Path, common_ancestor: Path) -> bool:
        # Check for binary files
        if file_path.suffix.lower() in self.BINARY_EXTENSIONS:
            return False
        
        # Get relative path for pattern matching
        try:
            path_relative_to_common = file_path.relative_to(common_ancestor)
        except ValueError:
            path_relative_to_common = None
        
        # Check semantic exclusion patterns
        for glob_pattern in self.SEMANTIC_EXCLUDES_GLOBS:
            if file_path.match(glob_pattern):
                return False
            if path_relative_to_common and path_relative_to_common.match(glob_pattern):
                return False
            # Special handling for patterns with wildcards
            if glob_pattern.strip('*') in str(file_path.as_posix()):
                if glob_pattern == '*lock*':
                    if 'lock' in file_path.name.lower():
                        return False
                elif f"/{glob_pattern.strip('*')}/" in str(file_path.as_posix()):
                    return False
        
        # Check extension filter
        if self.config.include_extensions:
            normalized_config_extensions = {
                (ext if ext.startswith('.') else '.' + ext).lower()
                for ext in self.config.include_extensions
            }
            if file_path.suffix.lower() not in normalized_config_extensions:
                return False
        
        # Check file size (75MB limit)
        try:
            if file_path.stat().st_size > 75 * 1024 * 1024:  # 75MB limit
                if not self.config.quiet:
                    print(f"pak_core: Skipping very large text file (>75MB): {file_path}", file=sys.stderr)
                return False
        except FileNotFoundError:
            return False
        
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
            
            if not self.config.quiet:
                compression_ratio = original_tokens / compressed_tokens if compressed_tokens > 0 else 1.0
                print(f"pak_core: {file_path.name} ({original_tokens} → {compressed_tokens} tokens, {compression_ratio:.1f}x, {method_desc})", file=sys.stderr)
            
            # Check budget
            if current_budget_remaining is not None and compressed_tokens > current_budget_remaining:
                if not self.config.quiet:
                    print(f"pak_core: Skipping {file_path} ({compressed_tokens} tokens) due to budget (rem: {current_budget_remaining})", file=sys.stderr)
                return None
            
            return FileEntry(
                path=file_path, language=lang, importance=importance,
                original_tokens=original_tokens,
                compressed_content=compressed_content, compressed_tokens=compressed_tokens,
                compression_method=method_desc,
                size=file_path.stat().st_size,
                lines=compressed_content.count('\n') + 1
            )
        
        except FileNotFoundError:
            if not self.config.quiet:
                print(f"pak_core: File not found during processing: {file_path}. Skipping.", file=sys.stderr)
        except Exception as e:
            if not self.config.quiet:
                print(f"pak_core: Error processing {file_path}: {e}. Skipping.", file=sys.stderr)
        
        return None

    def _smart_process_files(self, files: List[Path]) -> List[FileEntry]:
        # Create initial entries with importance scoring
        initial_entries: List[Tuple[Path, int, int]] = []
        for p in files:
            try:
                size_bytes = p.stat().st_size
                original_tokens_est = size_bytes // 4
                importance = FilePrioritizer.calculate_importance(p)
                initial_entries.append((p, importance, original_tokens_est))
            except Exception:
                pass
        
        # Sort by importance (desc) and size (asc) for better prioritization
        initial_entries.sort(key=lambda x: (-x[1], x[2]))
        
        processed_entries: List[FileEntry] = []
        current_total_tokens = 0
        
        for file_path, importance_score, _ in initial_entries:
            budget_remaining = (self.config.max_tokens - current_total_tokens) if self.config.max_tokens > 0 else None
            
            if budget_remaining is not None and budget_remaining <= 0:
                if not self.config.quiet:
                    print("pak_core: Token budget exhausted. Stopping.", file=sys.stderr)
                break
            
            # Choose compression level based on importance
            comp_level_name = 'semantic'  # Default to semantic for smart mode
            if importance_score >= FilePrioritizer.HIGH_PRIORITY_SCORE * 0.8:
                comp_level_name = 'light'
            elif importance_score >= FilePrioritizer.MEDIUM_PRIORITY_SCORE * 0.8:
                comp_level_name = 'medium'
            elif importance_score >= FilePrioritizer.LOW_PRIORITY_SCORE:
                comp_level_name = 'aggressive'
            
            chosen_strategy = self.compression_strategies[comp_level_name]
            entry = self._process_file_entry(file_path, chosen_strategy, budget_remaining)
            
            if entry:
                # If budget is tight and compression wasn't semantic, try semantic
                if budget_remaining is not None and entry.compressed_tokens > budget_remaining and comp_level_name != 'semantic':
                    if not self.config.quiet:
                        print(f"pak_core: Tight budget for {file_path} with {comp_level_name}. Retrying with semantic.", file=sys.stderr)
                    semantic_strategy = self.compression_strategies['semantic']
                    revised_entry = self._process_file_entry(file_path, semantic_strategy, budget_remaining)
                    if revised_entry and (revised_entry.compressed_tokens <= entry.compressed_tokens or revised_entry.compressed_tokens <= budget_remaining):
                        entry = revised_entry
                
                if entry and (budget_remaining is None or entry.compressed_tokens <= budget_remaining):
                    processed_entries.append(entry)
                    current_total_tokens += entry.compressed_tokens
        
        self.total_token_count = current_total_tokens
        return processed_entries

    def _standard_process_files(self, files: List[Path], strategy: CompressionStrategy) -> List[FileEntry]:
        processed_entries: List[FileEntry] = []
        current_total_tokens = 0
        
        for file_path in files:
            budget_remaining = (self.config.max_tokens - current_total_tokens) if self.config.max_tokens > 0 else None
            
            if budget_remaining is not None and budget_remaining <= 0:
                if not self.config.quiet:
                    print("pak_core: Token budget exhausted. Stopping.", file=sys.stderr)
                break
            
            entry = self._process_file_entry(file_path, strategy, budget_remaining)
            if entry:
                processed_entries.append(entry)
                current_total_tokens += entry.compressed_tokens
        
        self.total_token_count = current_total_tokens
        return processed_entries

    def _generate_archive_output_string(self, entries: List[FileEntry]) -> str:
        archive_lines: List[str] = []
        
        # Header
        archive_lines.append(f"__PAK_UUID__:{self.archive_uuid}")
        archive_lines.append(f"# Archive created with pak_core v{VERSION}")
        archive_lines.append(f"# Archive UUID: {self.archive_uuid}")
        archive_lines.append(f"# Compression Mode: {self.config.compression_level}")
        archive_lines.append(f"# AST Support: {'enabled' if AST_AVAILABLE else 'disabled'}")
        
        if self.config.compression_level == 'semantic':
            semantic_compressor_available = bool(os.environ.get('SEMANTIC_COMPRESSOR_PATH'))
            archive_lines.append(f"# LLM Semantic Compression: {'enabled' if semantic_compressor_available else 'fallback'}")
        
        if self.config.include_extensions:
            archive_lines.append(f"# Extension Filter: {', '.join(self.config.include_extensions)}")
        
        if self.config.max_tokens > 0:
            archive_lines.append(f"# Token Limit: {self.config.max_tokens} (Estimated Total: {self.total_token_count})")
        else:
            archive_lines.append(f"# Estimated Total Tokens: {self.total_token_count}")
        
        archive_lines.append(f"# Total Files Included: {self.included_file_count}")
        archive_lines.append("")
        
        # File entries
        for entry in entries:
            # Generate relative path for display
            try:
                display_path = entry.path.relative_to(self.common_ancestor_for_paths).as_posix()
            except (ValueError, AttributeError):
                display_path = entry.path.as_posix()
            
            # Handle multiple targets case
            if Path(display_path).is_absolute() and len(self.config.targets) > 1:
                if Path(display_path).name == display_path:
                    pass  # Keep as is
                else:
                    display_path = entry.path.name
            
            archive_lines.append(f"__PAK_FILE_{self.archive_uuid}_START__")
            archive_lines.append(f"Path: {display_path}")
            archive_lines.append(f"Language: {entry.language}")
            archive_lines.append(f"Importance: {entry.importance}")
            archive_lines.append(f"Size: {entry.size}")
            archive_lines.append(f"Original Tokens: {entry.original_tokens}")
            archive_lines.append(f"Compressed Lines: {entry.lines}")
            archive_lines.append(f"Compressed Tokens: {entry.compressed_tokens}")
            archive_lines.append(f"Compression Method: {entry.compression_method}")
            archive_lines.append(f"__PAK_DATA_{self.archive_uuid}_START__")
            archive_lines.append(entry.compressed_content)
            if entry.compressed_content and not entry.compressed_content.endswith('\n'):
                archive_lines.append("")
            archive_lines.append(f"__PAK_DATA_{self.archive_uuid}_END__")
        
        if not self.config.quiet:
            print(f"pak_core: Archive content generation complete. Files: {self.included_file_count}, Total est. tokens: {self.total_token_count}.", file=sys.stderr)
        
        return '\n'.join(archive_lines)

# Archive utility functions
def _get_archive_uuid_from_lines(content_lines: List[str]) -> Optional[str]:
    if not content_lines:
        return None
    
    first_line = content_lines[0]
    if first_line.startswith('__PAK_UUID__:'):
        return first_line[len('__PAK_UUID__:'):]
    if first_line.startswith('__PAK_ID__:'):
        return first_line[len('__PAK_ID__:'):]
    
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
    lines = full_content.splitlines()
    
    archive_uuid = _get_archive_uuid_from_lines(lines)
    if not archive_uuid:
        print("Error: Invalid pak archive format (missing __PAK_UUID__ or __PAK_ID__ header).", file=sys.stderr)
        return False
    
    regex_f = RegexFilter(pattern)
    if pattern and not regex_f.is_valid:
        print(f"Error: Invalid regex pattern '{pattern}'. Extraction aborted.", file=sys.stderr)
        return False
    
    is_quiet = os.environ.get("PAK_CORE_QUIET_MODE", "false").lower() == "true"
    if not is_quiet:
        print(f"Extracting from: {archive_path} (UUID: {archive_uuid})")
        if pattern:
            print(f"Filter pattern: {regex_f.pattern_str}")
    
    current_file_rel_path: Optional[str] = None
    in_data = False
    data_buffer: List[str] = []
    extracted_c = 0
    total_in_archive = 0
    
    file_start_m = f"__PAK_FILE_{archive_uuid}_START__"
    data_start_m = f"__PAK_DATA_{archive_uuid}_START__"
    data_end_m = f"__PAK_DATA_{archive_uuid}_END__"
    
    for line_idx, line_text in enumerate(lines):
        if line_text == file_start_m:
            current_file_rel_path = None
            in_data = False
            data_buffer = []
            total_in_archive += 1
        elif line_text.startswith("Path: ") and not in_data:
            current_file_rel_path = line_text[len("Path: "):].strip()
        elif line_text == data_start_m:
            if current_file_rel_path:
                in_data = True
                data_buffer = []
            else:
                print(f"Warning: Data section started at line {line_idx+1} without prior Path. Skipping.", file=sys.stderr)
        elif line_text == data_end_m:
            if current_file_rel_path and in_data:
                if regex_f.matches(current_file_rel_path):
                    path_to_extract = Path(current_file_rel_path)
                    
                    # Security: handle absolute paths
                    if path_to_extract.is_absolute():
                        if not is_quiet:
                            print(f"Warning: Absolute path '{path_to_extract}' in archive. Extracting as '{path_to_extract.name}' in output dir.", file=sys.stderr)
                        path_to_extract = Path(path_to_extract.name)
                    
                    final_output_path = (output_root / path_to_extract).resolve()
                    
                    # Security: ensure path doesn't escape output directory
                    if not str(final_output_path).startswith(str(output_root.resolve())):
                        print(f"Security Error: Path '{current_file_rel_path}' would write outside target '{output_root}'. Skipping.", file=sys.stderr)
                    else:
                        try:
                            final_output_path.parent.mkdir(parents=True, exist_ok=True)
                            final_output_path.write_text('\n'.join(data_buffer), encoding='utf-8')
                            if not is_quiet:
                                print(f"Extracted: {final_output_path.relative_to(output_root.resolve())}")
                            extracted_c += 1
                        except Exception as e_write:
                            print(f"Error writing file {final_output_path}: {e_write}", file=sys.stderr)
            
            in_data = False
            current_file_rel_path = None
        elif in_data:
            data_buffer.append(line_text)
    
    if not is_quiet:
        print(f"\nExtraction complete: {extracted_c} of {total_in_archive} files extracted to '{output_root}'.")
    
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
    
    is_quiet = os.environ.get("PAK_CORE_QUIET_MODE", "false").lower() == "true"
    if not is_quiet:
        print(f"Archive: {archive_path} (UUID: {archive_uuid})")
        if pattern:
            print(f"Filter: {regex_f.pattern_str}")
        
        header_format = "{path:<55.55} {size:>10} {imp:>4} {tok_c:>8} {meth:<22.22}"
        print(header_format.format(path="Path", size="Size (B)", imp="Imp", tok_c="Tok (C)", meth="Method"))
        print("-" * (55 + 1 + 10 + 1 + 4 + 1 + 8 + 1 + 22))
    
    meta: Dict[str, Optional[str]] = {'path': None, 'size': None, 'imp': None, 'tok_c': None, 'meth': None}
    in_file_meta_section = False
    listed_c = 0
    total_in_archive = 0
    
    file_start_m = f"__PAK_FILE_{archive_uuid}_START__"
    data_start_m = f"__PAK_DATA_{archive_uuid}_START__"
    
    for line_text in lines:
        if line_text == file_start_m:
            meta = {k: None for k in meta}
            in_file_meta_section = True
            total_in_archive += 1
        elif in_file_meta_section:
            if line_text.startswith("Path: "):
                meta['path'] = line_text[len("Path: "):].strip()
            elif line_text.startswith("Size: "):
                meta['size'] = line_text[len("Size: "):].strip()
            elif line_text.startswith("Importance: "):
                meta['imp'] = line_text[len("Importance: "):].strip()
            elif line_text.startswith("Compressed Tokens: "):
                meta['tok_c'] = line_text[len("Compressed Tokens: "):].strip()
            elif line_text.startswith("Compression Method: "):
                meta['meth'] = line_text[len("Compression Method: "):].strip()
            elif line_text.startswith("Method: "):
                meta['meth'] = line_text[len("Method: "):].strip()
            elif line_text == data_start_m:
                in_file_meta_section = False
                if meta['path'] and regex_f.matches(meta['path']):
                    if not is_quiet:
                        display_path = meta['path']
                        if len(display_path) > 53:
                            display_path = ".." + display_path[-51:]
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

def list_archive_contents_detailed(archive_path: str, pattern: str = "") -> bool:
    """NEW: Enhanced listing with content preview (first 200 chars of compressed content)"""
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
    
    is_quiet = os.environ.get("PAK_CORE_QUIET_MODE", "false").lower() == "true"
    if not is_quiet:
        print(f"Archive (Detailed): {archive_path} (UUID: {archive_uuid})")
        if pattern:
            print(f"Filter: {regex_f.pattern_str}")
        print()
    
    meta: Dict[str, Optional[str]] = {'path': None, 'size': None, 'imp': None, 'tok_c': None, 'meth': None}
    in_file_meta_section = False
    in_data_section = False
    content_buffer: List[str] = []
    listed_c = 0
    total_in_archive = 0
    
    file_start_m = f"__PAK_FILE_{archive_uuid}_START__"
    data_start_m = f"__PAK_DATA_{archive_uuid}_START__"
    data_end_m = f"__PAK_DATA_{archive_uuid}_END__"
    
    for line_text in lines:
        if line_text == file_start_m:
            meta = {k: None for k in meta}
            in_file_meta_section = True
            in_data_section = False
            content_buffer = []
            total_in_archive += 1
        elif in_file_meta_section:
            if line_text.startswith("Path: "):
                meta['path'] = line_text[len("Path: "):].strip()
            elif line_text.startswith("Size: "):
                meta['size'] = line_text[len("Size: "):].strip()
            elif line_text.startswith("Importance: "):
                meta['imp'] = line_text[len("Importance: "):].strip()
            elif line_text.startswith("Compressed Tokens: "):
                meta['tok_c'] = line_text[len("Compressed Tokens: "):].strip()
            elif line_text.startswith("Compression Method: "):
                meta['meth'] = line_text[len("Compression Method: "):].strip()
            elif line_text.startswith("Method: "):
                meta['meth'] = line_text[len("Method: "):].strip()
            elif line_text == data_start_m:
                in_file_meta_section = False
                in_data_section = True
                content_buffer = []
        elif in_data_section:
            if line_text == data_end_m:
                in_data_section = False
                if meta['path'] and regex_f.matches(meta['path']):
                    if not is_quiet:
                        print(f"📁 Path: {meta['path']}")
                        print(f"   Size: {meta['size']} bytes | Tokens: {meta['tok_c']} | Importance: {meta['imp']} | Method: {meta['meth']}")
                        content_preview = '\n'.join(content_buffer)[:200]
                        if len('\n'.join(content_buffer)) > 200:
                            content_preview += "..."
                        preview_lines = content_preview.split('\n')
                        print(f"   Preview:")
                        for i, preview_line in enumerate(preview_lines[:5]):  # Max 5 lines preview
                            print(f"     {preview_line}")
                        if len(preview_lines) > 5:
                            print("     ...")
                        print()  # Empty line separator
                    listed_c += 1
            else:
                content_buffer.append(line_text)
    
    if not is_quiet:
        print(f"{'='*60}")
        if pattern:
            print(f"Listed {listed_c} of {total_in_archive} files matching pattern.")
        else:
            print(f"Total files in archive: {total_in_archive}.")
    
    return True

# NEW: Method diff command functions
def extract_method_diff_command(targets: List[str], output_file: Optional[str] = None, quiet: bool = False) -> bool:
    """Extract method-level diff between files"""
    if len(targets) < 2:
        print("Error: Need at least 2 files to extract method diff", file=sys.stderr)
        return False
    
    extractor = MethodDiffExtractor()
    all_diffs = []
    
    for i in range(1, len(targets)):
        original_file = Path(targets[0])
        modified_file = Path(targets[i])
        
        if not original_file.exists():
            print(f"Error: Original file not found: {original_file}", file=sys.stderr)
            return False
        if not modified_file.exists():
            print(f"Error: Modified file not found: {modified_file}", file=sys.stderr)
            return False
        
        diffs = extractor.extract_diff_between_files(original_file, modified_file)
        all_diffs.extend(diffs)
        
        if not quiet:
            print(f"pak_core: Extracted {len(diffs)} method diffs from {modified_file.name}", file=sys.stderr)
    
    # Generate diff output
    diff_lines = []
    for diff in all_diffs:
        diff_lines.append(f"FILE: {diff.file_path}")
        diff_lines.append(f"FIND_METHOD: {diff.find_method}")
        diff_lines.append(f"UNTIL_EXCLUDE: {diff.until_exclude}")
        diff_lines.append(f"REPLACE_WITH:")
        if diff.replace_with:
            diff_lines.append(diff.replace_with)
        else:
            diff_lines.append("# Method deleted")
        diff_lines.append("")  # Empty line separator
    
    diff_content = '\n'.join(diff_lines)
    
    if output_file:
        try:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            Path(output_file).write_text(diff_content, encoding='utf-8')
            if not quiet:
                print(f"pak_core: Method diff written to {output_file}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing diff file: {e}", file=sys.stderr)
            return False
    else:
        print(diff_content, end='')
    
    return True

def verify_method_diff_command(diff_file: str, quiet: bool = False) -> bool:
    """Verify method diff file syntax"""
    if not Path(diff_file).exists():
        print(f"Error: Diff file not found: {diff_file}", file=sys.stderr)
        return False
    
    try:
        content = Path(diff_file).read_text(encoding='utf-8')
        result = MethodDiffParser.parse_diff_file(content)
        
        if result.is_valid:
            if not quiet:
                print(f"✓ Method diff file is valid: {len(result.diffs)} diffs found")
                for diff in result.diffs:
                    print(f"  - {diff.file_path}: {diff.find_method or '[new method]'}")
        else:
            print(f"✗ Method diff file has errors:")
            for error in result.errors:
                print(f"  {error}")
        
        return result.is_valid
    
    except Exception as e:
        print(f"Error reading diff file: {e}", file=sys.stderr)
        return False

def apply_method_diff_command(diff_file: str, target_dir: str = ".", quiet: bool = False) -> bool:
    """Apply method diff to target files"""
    if not Path(diff_file).exists():
        print(f"Error: Diff file not found: {diff_file}", file=sys.stderr)
        return False
    
    target_path = Path(target_dir)
    if not target_path.exists():
        print(f"Error: Target directory not found: {target_dir}", file=sys.stderr)
        return False
    
    try:
        content = Path(diff_file).read_text(encoding='utf-8')
        result = MethodDiffParser.parse_diff_file(content)
        
        if not result.is_valid:
            print("Error: Cannot apply invalid diff file. Run verify-diff first.", file=sys.stderr)
            return False
        
        applier = MethodDiffApplier()
        success_count = 0
        
        for diff in result.diffs:
            success, error = applier.apply_diff(diff, target_path)
            if success:
                success_count += 1
                if not quiet:
                    operation = "Added" if not diff.find_method else ("Deleted" if not diff.replace_with else "Modified")
                    method_name = diff.find_method or "[new method]"
                    print(f"✓ {operation} method in {diff.file_path}: {method_name}")
            else:
                print(f"✗ Failed to apply diff to {diff.file_path}: {error}", file=sys.stderr)
        
        if not quiet:
            print(f"\nApplied {success_count} of {len(result.diffs)} method diffs")
        
        return success_count == len(result.diffs)
    
    except Exception as e:
        print(f"Error applying diff: {e}", file=sys.stderr)
        return False

def main():
    """Enhanced main() with subcommand support and method diff commands"""
    known_subcommands = {'list', 'list-detailed', 'extract', 'verify', 'pack', 'extract-diff', 'verify-diff', 'apply-diff'}
    use_subcommands = len(sys.argv) > 1 and sys.argv[1] in known_subcommands
    
    if use_subcommands:
        parser = argparse.ArgumentParser(
            description=f"pak_core v{VERSION} - Python backend for pak4 file archiving with semantic compression + method diff support.",
            formatter_class=argparse.RawTextHelpFormatter
        )
        subparsers = parser.add_subparsers(dest='command', help='Commands')
        
        # Pack command
        pack_parser = subparsers.add_parser('pack', help='Pack files into archive')
        pack_parser.add_argument('targets', nargs='*', default=['.'],
                     help='File(s) and/or director(y/ies) to archive. Default: current directory.')
        pack_opts = pack_parser.add_argument_group('Packing Options')
        pack_opts.add_argument('--compression-level', '-c', default='none',
                     choices=['none', 'light', 'medium', 'aggressive', 'smart', 'semantic'],
                     help='Compression strategy')
        pack_opts.add_argument('--max-tokens', '-m', type=int, default=0,
                     help='Approximate maximum total tokens for the archive (0 = unlimited).')
        pack_opts.add_argument('--ext', nargs='+', default=[],
                     help='Include only files with these extensions (e.g., .py .md .txt). Dot is optional.')
        pack_parser.add_argument('--quiet', '-q', action='store_true',
                     help='Suppress non-error messages to stderr.')
        pack_parser.add_argument('--output', '-o',
                     help='Output file path (enables caching for semantic compression)')
        
        # Archive manipulation commands
        list_parser = subparsers.add_parser('list', help='List archive contents')
        list_parser.add_argument('archive', help='Archive file to list')
        list_parser.add_argument('-p', '--pattern', default='', help='Filter files matching regex pattern')
        
        listd_parser = subparsers.add_parser('list-detailed', help='List archive contents with content preview')
        listd_parser.add_argument('archive', help='Archive file to list')
        listd_parser.add_argument('-p', '--pattern', default='', help='Filter files matching regex pattern')
        
        extract_parser = subparsers.add_parser('extract', help='Extract archive contents')
        extract_parser.add_argument('archive', help='Archive file to extract')
        extract_parser.add_argument('-d', '--outdir', default='.', help='Output directory (default: current)')
        extract_parser.add_argument('-p', '--pattern', default='', help='Filter files matching regex pattern')
        
        verify_parser = subparsers.add_parser('verify', help='Verify archive integrity')
        verify_parser.add_argument('archive', help='Archive file to verify')
        
        # NEW: Method diff commands
        extract_diff_parser = subparsers.add_parser('extract-diff', help='Extract method-level differences between files')
        extract_diff_parser.add_argument('targets', nargs='+', help='Files to compare (first is original, rest are modified)')
        extract_diff_parser.add_argument('--output', '-o', help='Output diff file')
        extract_diff_parser.add_argument('--quiet', '-q', action='store_true', help='Suppress non-error messages')
        
        verify_diff_parser = subparsers.add_parser('verify-diff', help='Verify method diff file syntax')
        verify_diff_parser.add_argument('diff_file', help='Method diff file to verify')
        verify_diff_parser.add_argument('--quiet', '-q', action='store_true', help='Suppress non-error messages')
        
        apply_diff_parser = subparsers.add_parser('apply-diff', help='Apply method diff to target files')
        apply_diff_parser.add_argument('diff_file', help='Method diff file to apply')
        apply_diff_parser.add_argument('--target', default='.', help='Target directory (default: current)')
        apply_diff_parser.add_argument('--quiet', '-q', action='store_true', help='Suppress non-error messages')
        
        args = parser.parse_args()
    else:
        # Default pack mode for backward compatibility
        parser = argparse.ArgumentParser(
            description=f"pak_core v{VERSION} - Python backend for pak4 file archiving",
            formatter_class=argparse.RawTextHelpFormatter
        )
        parser.add_argument('targets', nargs='*', default=['.'],
                  help='File(s) and/or director(y/ies) to archive. Default: current directory.')
        parser.add_argument('--compression-level', '-c', default='none',
                  choices=['none', 'light', 'medium', 'aggressive', 'smart', 'semantic'],
                  help='Compression strategy')
        parser.add_argument('--max-tokens', '-m', type=int, default=0,
                  help='Approximate maximum total tokens for the archive (0 = unlimited).')
        parser.add_argument('--ext', nargs='+', default=[],
                  help='Include only files with these extensions.')
        parser.add_argument('--quiet', '-q', action='store_true',
                  help='Suppress non-error messages to stderr.')
        parser.add_argument('--output', '-o',
                  help='Output file path (enables caching for semantic compression)')
        parser.add_argument('--version', action='version',
                  version=f'%(prog)s {VERSION} (AST Support: {"Enabled" if AST_AVAILABLE else "Disabled"})')
        
        args = parser.parse_args()
        args.command = None  # Mark as default pack
    
    # Set quiet mode environment variable
    if hasattr(args, 'quiet') and args.quiet:
        os.environ["PAK_CORE_QUIET_MODE"] = "true"
    else:
        os.environ.pop("PAK_CORE_QUIET_MODE", None)
    
    # Execute commands
    if args.command == 'list':
        return list_archive_contents(args.archive, args.pattern)
    elif args.command == 'list-detailed':
        return list_archive_contents_detailed(args.archive, args.pattern)
    elif args.command == 'extract':
        return extract_archive(args.archive, args.outdir, args.pattern)
    elif args.command == 'verify':
        archive_file = Path(args.archive)
        if not archive_file.is_file():
            print(f"Error: Archive file not found: {args.archive}", file=sys.stderr)
            return False
        with open(args.archive, 'r') as f:
            first_line = f.readline().strip()
        if first_line.startswith('__PAK_UUID__:') or first_line.startswith('__PAK_ID__:'):
            print(f"✓ Valid pak archive format: {args.archive}")
            return True
        else:
            print(f"✗ Invalid pak archive format: {args.archive}")
            return False
    
    # NEW: Method diff commands
    elif args.command == 'extract-diff':
        return extract_method_diff_command(args.targets, args.output, args.quiet)
    elif args.command == 'verify-diff':
        return verify_method_diff_command(args.diff_file, args.quiet)
    elif args.command == 'apply-diff':
        return apply_method_diff_command(args.diff_file, args.target, args.quiet)
    
    else:
        # Default pack command
        normalized_extensions = []
        if hasattr(args, 'ext') and args.ext:
            for ext_arg in args.ext:
                normalized_extensions.append(ext_arg if ext_arg.startswith('.') else '.' + ext_arg)
        
        archiver_config = ArchiveConfig(
            compression_level=args.compression_level,
            max_tokens=args.max_tokens,
            include_extensions=normalized_extensions,
            targets=[Path(t) for t in args.targets],
            quiet=args.quiet,
            output_file=getattr(args, 'output', None)
        )
        
        archiver_instance = SmartArchiver(archiver_config)
        generated_archive_content = archiver_instance.create_archive()
        
        if generated_archive_content:
            if hasattr(args, 'output') and args.output:
                try:
                    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
                    with open(args.output, 'w', encoding='utf-8') as f:
                        f.write(generated_archive_content)
                    if not args.quiet:
                        print(f"pak_core: Archive written to {args.output}", file=sys.stderr)
                except IOError as e:
                    print(f"Error writing to output file {args.output}: {e}", file=sys.stderr)
                    return False
            else:
                print(generated_archive_content, end='')
            return True
        else:
            return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)