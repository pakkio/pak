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
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from abc import ABC, abstractmethod

# Tree-sitter imports (optional)
try:
    from tree_sitter import Language, Parser
    import tree_sitter_languages
    import tree_sitter_python
    AST_AVAILABLE = True
except ImportError:
    AST_AVAILABLE = False

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
    size: int = 0
    lines: int = 0

@dataclass 
class ArchiveConfig:
    compression_level: str = "none"
    max_tokens: int = 0
    include_extensions: List[str] = field(default_factory=list)
    targets: List[Path] = field(default_factory=list)
    quiet: bool = False

class CompressionStrategy(ABC):
    @abstractmethod
    def compress(self, content: str, file_path: Path, language: str) -> Tuple[str, str]:
        """Return (compressed_content, method_description)"""
        pass

class NoneCompression(CompressionStrategy):
    def compress(self, content: str, file_path: Path, language: str) -> Tuple[str, str]:
        return content, "raw"

class LightCompression(CompressionStrategy):
    def compress(self, content: str, file_path: Path, language: str) -> Tuple[str, str]:
        # Remove excessive whitespace and empty lines
        lines = content.split('\n')
        compressed_lines = []
        
        for line in lines:
            stripped = line.strip()
            if stripped:  # Skip empty lines
                # Normalize whitespace but preserve indentation structure
                if line.startswith((' ', '\t')):
                    # Keep relative indentation
                    indent = len(line) - len(line.lstrip())
                    normalized_indent = '  ' * (indent // 4) + ' ' * (indent % 4)
                    compressed_lines.append(normalized_indent + stripped)
                else:
                    compressed_lines.append(stripped)
        
        return '\n'.join(compressed_lines), "text-based (light)"

class MediumCompression(CompressionStrategy):
    def compress(self, content: str, file_path: Path, language: str) -> Tuple[str, str]:
        # Light compression + comment removal for code files
        content, _ = LightCompression().compress(content, file_path, language)
        
        if language in ['python', 'javascript', 'typescript', 'java', 'c', 'cpp', 'go', 'rust']:
            lines = content.split('\n')
            filtered_lines = []
            
            for line in lines:
                stripped = line.strip()
                # Remove single-line comments (basic patterns)
                if language == 'python' and stripped.startswith('#'):
                    continue
                elif language in ['javascript', 'typescript', 'java', 'c', 'cpp'] and stripped.startswith('//'):
                    continue
                elif stripped.startswith('/*') and stripped.endswith('*/'):
                    continue
                    
                filtered_lines.append(line)
            
            content = '\n'.join(filtered_lines)
        
        return content, "text-based (medium)"

class AggressiveCompression(CompressionStrategy):
    def compress(self, content: str, file_path: Path, language: str) -> Tuple[str, str]:
        if language == 'python':
            return self._extract_python_structure(content), "text-based (aggressive-py)"
        elif language in ['javascript', 'typescript']:
            return self._extract_js_structure(content), "text-based (aggressive-js)"
        else:
            # Fallback to medium compression
            return MediumCompression().compress(content, file_path, language)
    
    def _extract_python_structure(self, content: str) -> str:
        """Enhanced Python structure extraction"""
        lines = content.split('\n')
        result = []

        # Extract imports
        for line in lines:
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                result.append(line)

        if result:
            result.append('')  # Separator

        # Extract classes with methods
        in_class = False
        current_class = ''
        class_methods = []

        for line in lines:
            stripped = line.strip()

            # Class definition
            if stripped.startswith('class '):
                if in_class and class_methods:
                    result.append(f'class {current_class}:')
                    for method in class_methods:
                        result.append(f'    {method}')
                    result.append('')

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

        # Finish last class
        if in_class and class_methods:
            result.append(f'class {current_class}:')
            for method in class_methods:
                result.append(f'    {method}')

        return '\n'.join(result)

    def _extract_js_structure(self, content: str) -> str:
        """Basic JavaScript/TypeScript structure extraction"""
        lines = content.split('\n')
        result = []
        
        for line in lines:
            stripped = line.strip()
            
            # Imports/exports
            if (stripped.startswith('import ') or stripped.startswith('export ') or
                stripped.startswith('const ') or stripped.startswith('let ') or
                stripped.startswith('var ') or stripped.startswith('function ')):
                result.append(stripped)
            
            # Class definitions
            elif stripped.startswith('class '):
                result.append(stripped)
            
            # Interface definitions (TypeScript)
            elif stripped.startswith('interface ') or stripped.startswith('type '):
                result.append(stripped)
        
        return '\n'.join(result)

class ASTCompression(CompressionStrategy):
    def __init__(self):
        self.ast_available = AST_AVAILABLE
        self._parsers = {}
    
    def compress(self, content: str, file_path: Path, language: str) -> Tuple[str, str]:
        if not self.ast_available:
            # Fallback to aggressive text-based
            return AggressiveCompression().compress(content, file_path, language)
        
        try:
            parser = self._get_parser(language)
            if not parser:
                return AggressiveCompression().compress(content, file_path, language)
            
            source_bytes = content.encode('utf-8')
            tree = parser.parse(source_bytes)
            
            if language == 'python':
                compressed = self._extract_python_ast(tree, source_bytes)
            else:
                # Generic AST extraction
                compressed = self._extract_generic_ast(tree, source_bytes, language)
            
            return compressed, "AST-enhanced"
            
        except Exception as e:
            # Fallback on any AST error
            return AggressiveCompression().compress(content, file_path, language)
    
    def _get_parser(self, language: str) -> Optional[Parser]:
        if language in self._parsers:
            return self._parsers[language]
        
        try:
            if language == 'python':
                lang_obj = Language(tree_sitter_python.language())
            elif language in ['javascript', 'js']:
                lang_obj = tree_sitter_languages.get_language('javascript')
            elif language == 'typescript':
                lang_obj = tree_sitter_languages.get_language('typescript')
            elif language == 'java':
                lang_obj = tree_sitter_languages.get_language('java')
            elif language == 'rust':
                lang_obj = tree_sitter_languages.get_language('rust')
            elif language in ['c', 'cpp']:
                lang_obj = tree_sitter_languages.get_language('c' if language == 'c' else 'cpp')
            elif language == 'go':
                lang_obj = tree_sitter_languages.get_language('go')
            else:
                return None
            
            parser = Parser(lang_obj)
            self._parsers[language] = parser
            return parser
            
        except Exception:
            return None
    
    def _extract_python_ast(self, tree, source_bytes: bytes) -> str:
        """AST-based Python extraction"""
        api_elements = []
        
        def traverse_node(node):
            node_type = node.type
            
            if node_type in ["import_statement", "import_from_statement"]:
                api_elements.append(node.text.decode('utf8').strip())
            
            elif node_type == "class_definition":
                # Get class header
                header_text = self._extract_definition_header(node, source_bytes)
                api_elements.append(header_text + " ...")
            
            elif node_type == "function_definition":
                # Get function header  
                header_text = self._extract_definition_header(node, source_bytes)
                api_elements.append(header_text + " ...")
            
            # Recurse
            for child in node.children:
                traverse_node(child)
        
        if tree and tree.root_node:
            traverse_node(tree.root_node)
        
        return '\n'.join(api_elements) if api_elements else "# No extractable structure found"
    
    def _extract_definition_header(self, node, source_bytes: bytes) -> str:
        """Extract just the definition line (until colon for Python)"""
        # Find the colon that ends the definition
        for child in node.children:
            if child.type == ':':
                return source_bytes[node.start_byte:child.end_byte].decode('utf-8', errors='ignore').strip()
        
        # Fallback: take first line
        full_text = node.text.decode('utf-8', errors='ignore')
        return full_text.split('\n')[0].strip()
    
    def _extract_generic_ast(self, tree, source_bytes: bytes, language: str) -> str:
        """Generic AST extraction for other languages"""
        # Basic implementation - could be enhanced per language
        important_nodes = []
        
        def traverse_node(node):
            # Common important node types across languages
            if node.type in ['function_definition', 'class_definition', 'method_definition',
                           'interface_declaration', 'struct_declaration', 'enum_declaration']:
                # Take first line of definition
                text = node.text.decode('utf-8', errors='ignore')
                first_line = text.split('\n')[0].strip()
                important_nodes.append(first_line)
            
            for child in node.children:
                traverse_node(child)
        
        if tree and tree.root_node:
            traverse_node(tree.root_node)
        
        return '\n'.join(important_nodes) if important_nodes else "# No extractable structure found"

class LanguageDetector:
    EXTENSION_MAP = {
        '.py': 'python',
        '.js': 'javascript', 
        '.mjs': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.rs': 'rust',
        '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp',
        '.c': 'c',
        '.h': 'c',
        '.hpp': 'cpp',
        '.go': 'go',
        '.rb': 'ruby',
        '.php': 'php',
        '.cs': 'csharp',
        '.md': 'markdown',
        '.rst': 'markdown',
        '.txt': 'text',
        '.json': 'json',
        '.yaml': 'yaml', '.yml': 'yaml',
        '.toml': 'toml',
        '.xml': 'xml',
        '.html': 'html',
        '.css': 'css',
        '.sh': 'bash',
        '.bash': 'bash'
    }
    
    @classmethod
    def detect(cls, file_path: Path) -> str:
        suffix = file_path.suffix.lower()
        
        if suffix in cls.EXTENSION_MAP:
            return cls.EXTENSION_MAP[suffix]
        
        # Check shebang for executable files
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline().strip()
                if first_line.startswith('#!'):
                    if 'python' in first_line:
                        return 'python'
                    elif 'bash' in first_line or 'sh' in first_line:
                        return 'bash'
        except:
            pass
        
        return 'generic'

class FilePrioritizer:
    """Determines file importance for smart compression"""
    
    HIGH_PRIORITY_NAMES = {
        'readme', 'main', 'index', 'app', 'core', 'setup', 'config',
        'dockerfile', 'makefile', 'requirements', 'package.json', 
        'gemfile', 'build.gradle'
    }
    
    HIGH_PRIORITY_EXTENSIONS = {'.py', '.js', '.ts', '.cpp', '.h', '.java', '.go', '.rs'}
    MEDIUM_PRIORITY_EXTENSIONS = {'.md', '.rst', '.sh', '.bash'}
    
    @classmethod
    def calculate_importance(cls, file_path: Path) -> int:
        score = 0
        filename = file_path.name.lower()
        extension = file_path.suffix.lower()
        
        # Extension-based scoring
        if extension in cls.HIGH_PRIORITY_EXTENSIONS:
            score += 10
        elif extension in cls.MEDIUM_PRIORITY_EXTENSIONS:
            score += 5
        else:
            score += 1
        
        # Filename-based scoring  
        name_without_ext = file_path.stem.lower()
        if name_without_ext in cls.HIGH_PRIORITY_NAMES:
            score += 7
        
        # Special boost for README files
        if filename.startswith('readme'):
            score += 8
            
        # Penalty for test files
        if any(test_indicator in filename for test_indicator in ['test', 'spec', 'mock', 'fixture']):
            score -= 3
            
        return max(0, score)

class RegexFilter:
    """Handles regex-based file path filtering"""
    
    def __init__(self, pattern: str = ""):
        self.pattern = pattern
        self.compiled_pattern = None
        self.is_valid = True
        
        if pattern:
            try:
                self.compiled_pattern = re.compile(pattern)
            except re.error as e:
                print(f"Warning: Invalid regex pattern '{pattern}': {e}", file=sys.stderr)
                self.is_valid = False
    
    def matches(self, file_path: str) -> bool:
        """Check if file path matches the regex pattern"""
        if not self.pattern or not self.is_valid:
            return True  # No filter or invalid pattern = match all
        
        return bool(self.compiled_pattern.search(file_path))
    
    def filter_paths(self, paths: List[str]) -> List[str]:
        """Filter a list of paths based on the regex pattern"""
        if not self.pattern or not self.is_valid:
            return paths
        
        return [path for path in paths if self.matches(path)]

class SmartArchiver:
    """Main archiver with smart compression and prioritization"""
    
    SEMANTIC_EXCLUDES = {
        '*.min.js', '*.min.css', '*.bundle.*', '*lock*', '*.log', '*cache*',
        '*dist/*', '*build/*', '*.pyc', '*__pycache__*', '*generated*',
        '*vendor/*', '*node_modules/*', '*.pak', '*/.git/*', '.git',
        '*/.hg/*', '.hg', '*/.svn/*', '.svn'
    }
    
    BINARY_EXTENSIONS = {
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.ico', '.svg',
        '.zip', '.tar', '.gz', '.bz2', '.rar', '.7z', '.pdf', '.doc', '.docx',
        '.xls', '.xlsx', '.ppt', '.pptx', '.o', '.a', '.so', '.dll', '.exe',
        '.jar', '.class', '.mp3', '.mp4', '.avi', '.mov', '.wav', '.webm',
        '.db', '.sqlite', '.sqlite3', '.woff', '.woff2', '.ttf', '.eot'
    }
    
    def __init__(self, config: ArchiveConfig):
        self.config = config
        self.token_count = 0
        self.archive_id = self._generate_archive_id()
        
        # Initialize compression strategy
        self.compression_strategies = {
            'none': NoneCompression(),
            'light': LightCompression(), 
            'medium': MediumCompression(),
            'aggressive': AggressiveCompression() if not AST_AVAILABLE else ASTCompression(),
            'smart': None  # Will be determined per file
        }
    
    def _generate_archive_id(self) -> str:
        import random
        import string
        return ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    
    def create_archive(self) -> str:
        """Create pak archive and return as string"""
        # Collect all files
        files = self._collect_files()
        
        if not files:
            if not self.config.quiet:
                print("pak_core: No files found matching criteria", file=sys.stderr)
            return ""
        
        # Process files based on compression level
        if self.config.compression_level == 'smart':
            processed_files = self._smart_process_files(files)
        else:
            processed_files = self._standard_process_files(files)
        
        # Generate archive
        return self._generate_archive_content(processed_files)
    
    def _collect_files(self) -> List[Path]:
        """Collect all files to be archived"""
        files = []
        
        for target in self.config.targets:
            if target.is_file():
                if self._should_include_file(target):
                    files.append(target)
            elif target.is_dir():
                for file_path in target.rglob('*'):
                    if file_path.is_file() and self._should_include_file(file_path):
                        files.append(file_path)
        
        return files
    
    def _should_include_file(self, file_path: Path) -> bool:
        """Check if file should be included in archive"""
        # Extension filter
        if self.config.include_extensions:
            if not any(str(file_path).endswith(ext) for ext in self.config.include_extensions):
                return False
        
        # Semantic exclusions
        file_str = str(file_path)
        for pattern in self.SEMANTIC_EXCLUDES:
            # Simple glob-like matching
            if '*' in pattern:
                pattern_regex = pattern.replace('*', '.*')
                if re.search(pattern_regex, file_str):
                    return False
            elif pattern in file_str:
                return False
        
        # Binary file exclusion
        if file_path.suffix.lower() in self.BINARY_EXTENSIONS:
            return False
            
        return True
    
    def _estimate_tokens(self, content: str) -> int:
        """Rough token estimation"""
        return len(content) // 4
    
    def _smart_process_files(self, files: List[Path]) -> List[FileEntry]:
        """Process files with smart prioritization and adaptive compression"""
        file_entries = []
        
        # Calculate importance and sort
        for file_path in files:
            language = LanguageDetector.detect(file_path)
            importance = FilePrioritizer.calculate_importance(file_path)
            
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                original_tokens = self._estimate_tokens(content)
                
                entry = FileEntry(
                    path=file_path,
                    language=language,
                    importance=importance,
                    original_tokens=original_tokens,
                    size=file_path.stat().st_size
                )
                file_entries.append(entry)
            except Exception as e:
                if not self.config.quiet:
                    print(f"pak_core: Skipping {file_path}: {e}", file=sys.stderr)
        
        # Sort by importance (high to low) then by original tokens (low to high)
        file_entries.sort(key=lambda x: (-x.importance, x.original_tokens))
        
        # Process files with adaptive compression
        processed_files = []
        for entry in file_entries:
            # Determine compression level based on importance and remaining budget
            compression_level = self._determine_adaptive_compression(entry)
            
            # Compress the file
            strategy = self.compression_strategies[compression_level]
            content = entry.path.read_text(encoding='utf-8', errors='ignore')
            compressed_content, method = strategy.compress(content, entry.path, entry.language)
            
            entry.compressed_content = compressed_content
            entry.compressed_tokens = self._estimate_tokens(compressed_content)
            entry.compression_method = method
            entry.lines = len(compressed_content.split('\n'))
            
            # Check token budget
            if (self.config.max_tokens > 0 and 
                self.token_count + entry.compressed_tokens > self.config.max_tokens):
                if not self.config.quiet:
                    print(f"pak_core: Token budget reached, stopping at {entry.path}", file=sys.stderr)
                break
                
            self.token_count += entry.compressed_tokens
            processed_files.append(entry)
        
        return processed_files
    
    def _determine_adaptive_compression(self, entry: FileEntry) -> str:
        """Determine compression level based on importance and token budget"""
        if self.config.max_tokens == 0:
            # No budget constraint, use importance-based compression
            if entry.importance >= 10:
                return 'light'
            elif entry.importance >= 5:
                return 'medium'
            else:
                return 'aggressive'
        
        # Budget-constrained logic
        remaining_budget = self.config.max_tokens - self.token_count
        
        if remaining_budget <= 0:
            return 'aggressive'
        
        # High importance files get better treatment
        if entry.importance >= 10:
            return 'light'
        elif entry.importance >= 7:
            # Check if we can afford medium compression
            estimated_medium_tokens = entry.original_tokens // 2  # Rough estimate
            if estimated_medium_tokens <= remaining_budget // 3:
                return 'medium'
            else:
                return 'aggressive'
        else:
            return 'aggressive'
    
    def _standard_process_files(self, files: List[Path]) -> List[FileEntry]:
        """Process files with uniform compression level"""
        processed_files = []
        strategy = self.compression_strategies[self.config.compression_level]
        
        for file_path in files:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                language = LanguageDetector.detect(file_path)
                
                compressed_content, method = strategy.compress(content, file_path, language)
                compressed_tokens = self._estimate_tokens(compressed_content)
                
                # Check token budget
                if (self.config.max_tokens > 0 and 
                    self.token_count + compressed_tokens > self.config.max_tokens):
                    if not self.config.quiet:
                        print(f"pak_core: Token budget reached, stopping at {file_path}", file=sys.stderr)
                    break
                
                entry = FileEntry(
                    path=file_path,
                    language=language,
                    importance=FilePrioritizer.calculate_importance(file_path),
                    original_tokens=self._estimate_tokens(content),
                    compressed_content=compressed_content,
                    compressed_tokens=compressed_tokens,
                    compression_method=method,
                    size=file_path.stat().st_size,
                    lines=len(compressed_content.split('\n'))
                )
                
                self.token_count += compressed_tokens
                processed_files.append(entry)
                
            except Exception as e:
                if not self.config.quiet:
                    print(f"pak_core: Skipping {file_path}: {e}", file=sys.stderr)
        
        return processed_files
    
    def _generate_archive_content(self, files: List[FileEntry]) -> str:
        """Generate the final archive content"""
        lines = []
        
        # Header
        lines.append(f"__PAK_ID__:{self.archive_id}")
        lines.append(f"# Archive created with pak v{VERSION}")
        lines.append(f"# Archive ID: {self.archive_id}")
        lines.append(f"# Compression Mode: {self.config.compression_level}")
        lines.append(f"# AST Support: {'enabled' if AST_AVAILABLE else 'disabled'}")
        
        if self.config.include_extensions:
            lines.append(f"# Extension Filter: {' '.join(self.config.include_extensions)}")
        
        if self.config.max_tokens > 0:
            lines.append(f"# Token Limit: {self.config.max_tokens}")
        
        lines.append("")
        
        # Files
        for entry in files:
            lines.append(f"__PAK_FILE_{self.archive_id}_START__")
            lines.append(f"Path: {entry.path}")
            lines.append(f"Language: {entry.language}")
            lines.append(f"Size: {entry.size}")
            lines.append(f"Lines: {entry.lines}")
            lines.append(f"Tokens: {entry.compressed_tokens}")
            lines.append(f"Compression: {self.config.compression_level}")
            lines.append(f"Method: {entry.compression_method}")
            lines.append(f"__PAK_DATA_{self.archive_id}_START__")
            lines.append(entry.compressed_content)
            if not entry.compressed_content.endswith('\n'):
                lines.append("")
            lines.append(f"__PAK_DATA_{self.archive_id}_END__")
        
        if not self.config.quiet:
            print(f"pak_core: Archive complete. Files: {len(files)}, Total tokens: {self.token_count}", file=sys.stderr)
        
        return '\n'.join(lines)

def extract_archive(archive_path: str, output_dir: str = ".", pattern: str = ""):
    """Extract pak archive to directory with optional regex filtering"""
    archive_file = Path(archive_path)
    output_path = Path(output_dir)
    
    if not archive_file.exists():
        print(f"Error: Archive file not found: {archive_path}", file=sys.stderr)
        return False
    
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize regex filter
    regex_filter = RegexFilter(pattern)
    if pattern and not regex_filter.is_valid:
        print(f"Error: Invalid regex pattern, extraction aborted", file=sys.stderr)
        return False
    
    try:
        content = archive_file.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        # Extract archive ID
        if not lines or not lines[0].startswith('__PAK_ID__:'):
            print("Error: Invalid pak archive format", file=sys.stderr)
            return False
        
        archive_id = lines[0][11:]  # Remove __PAK_ID__: prefix
        
        # Parse files
        current_file_path = None
        in_data_section = False
        file_content_lines = []
        extracted_count = 0
        total_count = 0
        
        if pattern:
            print(f"Extracting files matching pattern: {pattern}")
        
        for line in lines[1:]:
            if line == f"__PAK_FILE_{archive_id}_START__":
                current_file_path = None
                in_data_section = False
                file_content_lines = []
                
            elif line.startswith("Path: "):
                current_file_path = line[6:]  # Remove "Path: " prefix
                
            elif line == f"__PAK_DATA_{archive_id}_START__":
                in_data_section = True
                file_content_lines = []
                
            elif line == f"__PAK_DATA_{archive_id}_END__":
                if current_file_path and in_data_section:
                    total_count += 1
                    
                    # Apply regex filter
                    if regex_filter.matches(current_file_path):
                        # Write file
                        output_file_path = output_path / current_file_path
                        output_file_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        content = '\n'.join(file_content_lines)
                        output_file_path.write_text(content, encoding='utf-8')
                        print(f"Extracted: {output_file_path}")
                        extracted_count += 1
                    else:
                        print(f"Skipped (pattern): {current_file_path}")
                
                in_data_section = False
                current_file_path = None
                file_content_lines = []
                
            elif in_data_section:
                file_content_lines.append(line)
        
        if pattern:
            print(f"\nExtraction complete: {extracted_count}/{total_count} files extracted")
        else:
            print(f"\nExtraction complete: {extracted_count} files extracted")
            
        return True
        
    except Exception as e:
        print(f"Error extracting archive: {e}", file=sys.stderr)
        return False

def list_archive_contents(archive_path: str, pattern: str = ""):
    """List pak archive contents with optional regex filtering"""
    archive_file = Path(archive_path)
    
    if not archive_file.exists():
        print(f"Error: Archive file not found: {archive_path}", file=sys.stderr)
        return False
    
    # Initialize regex filter
    regex_filter = RegexFilter(pattern)
    if pattern and not regex_filter.is_valid:
        print(f"Error: Invalid regex pattern", file=sys.stderr)
        return False
    
    try:
        content = archive_file.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        # Extract archive ID
        if not lines or not lines[0].startswith('__PAK_ID__:'):
            print("Error: Invalid pak archive format", file=sys.stderr)
            return False
        
        archive_id = lines[0][11:]  # Remove __PAK_ID__: prefix
        
        print(f"Archive: {archive_path} (ID: {archive_id})")
        if pattern:
            print(f"Filter: {pattern}")
        print()
        
        # Parse files for listing
        current_file_path = None
        file_size = None
        file_tokens = None
        file_method = None
        matched_count = 0
        total_count = 0
        
        for line in lines[1:]:
            if line == f"__PAK_FILE_{archive_id}_START__":
                current_file_path = None
                file_size = None
                file_tokens = None
                file_method = None
                
            elif line.startswith("Path: "):
                current_file_path = line[6:]  # Remove "Path: " prefix
                
            elif line.startswith("Size: "):
                file_size = line[6:]  # Remove "Size: " prefix
                
            elif line.startswith("Tokens: "):
                file_tokens = line[8:]  # Remove "Tokens: " prefix
                
            elif line.startswith("Method: "):
                file_method = line[8:]  # Remove "Method: " prefix
                
            elif line == f"__PAK_DATA_{archive_id}_START__":
                if current_file_path:
                    total_count += 1
                    
                    # Apply regex filter
                    if regex_filter.matches(current_file_path):
                        size_str = file_size or "?"
                        tokens_str = file_tokens or "?"
                        method_str = file_method or "unknown"
                        
                        print(f"{current_file_path:<50} {size_str:>8} bytes {tokens_str:>6} tokens [{method_str}]")
                        matched_count += 1
        
        if pattern:
            print(f"\nMatched {matched_count}/{total_count} files")
        else:
            print(f"\nTotal: {matched_count} files")
            
        return True
        
    except Exception as e:
        print(f"Error listing archive: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description=f"pak_core v{VERSION} - Python business logic")
    parser.add_argument('targets', nargs='*', help='Files/directories to archive')
    parser.add_argument('--compression-level', '-c', default='none',
                       choices=['none', 'light', 'medium', 'aggressive', 'smart'],
                       help='Compression level')
    parser.add_argument('--max-tokens', '-m', type=int, default=0,
                       help='Maximum tokens (0 = unlimited)')
    parser.add_argument('--ext', nargs='+', default=[],
                       help='Include only files with these extensions')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Quiet mode')
    
    args = parser.parse_args()
    
    if not args.targets:
        args.targets = ['.']
    
    config = ArchiveConfig(
        compression_level=args.compression_level,
        max_tokens=args.max_tokens,
        include_extensions=args.ext,
        targets=[Path(t) for t in args.targets],
        quiet=args.quiet
    )
    
    archiver = SmartArchiver(config)
    archive_content = archiver.create_archive()
    
    if archive_content:
        print(archive_content)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()