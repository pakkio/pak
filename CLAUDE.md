# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pak is a semantic compression tool family designed to solve the copy-paste workflow problem when working with LLMs. It packages multiple files into LLM-friendly formats and extracts modified code back to proper file structures.

The repository contains multiple variants:
- **pak** (Bash script) - Simple, zero-dependency solution
- **pak3** (Bash + Python) - Enhanced with AST analysis
- **pak4** (Python core) - Full-featured with semantic LLM compression

## Core Architecture

### Main Components

**pak_core.py** - Primary Python backend containing:
- `SmartArchiver` class: Main orchestration for file collection, compression, and archive generation
- Multiple compression strategies: None, Light, Medium, Aggressive (AST-based), and Semantic (LLM-based)
- `FilePrioritizer`: Assigns importance scores to files for smart compression
- `LanguageDetector`: Maps file extensions to language identifiers
- Archive format handlers for listing and extraction

**Compression Strategy Pattern**:
- `CompressionStrategy` (ABC) with implementations for different levels
- `ASTCompression`: Uses tree-sitter for syntax-aware compression
- `SemanticCompression`: Leverages LLM for intelligent content reduction

**Supporting Modules**:
- `semantic_compressor.py`: LLM-based semantic compression using external API
- `ast_helper.py`: Tree-sitter AST analysis helper
- `python_extractor.py`: Python-specific structure extraction
- `llm_wrapper.py`: LLM API abstraction layer

### Archive Format

Pak uses a custom text-based format with UUID markers:
```
__PAK_UUID__:<uuid>
__PAK_FILE_<uuid>_START__
Path: <relative_path>
Language: <detected_language>
...metadata...
__PAK_DATA_<uuid>_START__
<compressed_content>
__PAK_DATA_<uuid>_END__
```

## Common Development Commands

### Running pak4/pak_core.py
```bash
# Basic packing (default pack command)
python3 pak_core.py src/ --compression-level smart --max-tokens 8000

# Using subcommands
python3 pak_core.py pack src/ -c smart -m 8000
python3 pak_core.py list archive.pak
python3 pak_core.py extract archive.pak -d output/

# With semantic compression (requires LLM setup)
SEMANTIC_COMPRESSOR_PATH=/path/to/semantic_compressor.py python3 pak_core.py -c semantic src/
```

### Development and Testing
```bash
# Install dependencies
poetry install

# Run with debug output
PAK_DEBUG=true python3 pak_core.py -c semantic test_file.py

# Test AST availability
python3 pak_core.py --version
```

### Bash Scripts
```bash
# Make scripts executable
chmod +x pak pak3 pak4

# Run bash version (simple)
./pak src/ --compress-level medium

# Run enhanced version
./pak3 --compress-level smart --max-tokens 8000 src/
```

## Key Development Patterns

### Adding New Compression Strategies
1. Create class inheriting from `CompressionStrategy`
2. Implement `compress(content, file_path, language)` method
3. Register in `SmartArchiver.compression_strategies` dict
4. Add to CLI choices in `main()`

### Language Support
- Extend `LanguageDetector.EXTENSION_MAP` for new file types
- Add language support in `ASTCompression._get_language()`
- Update `ast_helper.py` for language-specific AST handling

### File Prioritization
- Modify `FilePrioritizer` class constants for importance scoring
- Add patterns to `LOW_PRIORITY_PATTERNS` for exclusions
- Update `CRITICAL_FILENAMES` for special files

## Testing Notes

The project includes test files but uses ad-hoc testing rather than a formal framework. When testing:

1. Use small test directories with known file structures
2. Verify archive format with `pak_core.py list` command
3. Test round-trip: pack → extract → compare
4. Check token estimation accuracy with `--max-tokens`

## Environment Variables

- `SEMANTIC_COMPRESSOR_PATH`: Path to semantic_compressor.py for LLM compression
- `PAK_DEBUG`: Enable detailed debug output for semantic compression
- `PAK_QUIET`: Suppress stderr messages during compression
- Tree-sitter requires proper Python environment with required packages

## Integration Points

- **LLM Integration**: Uses `llm_wrapper.py` for API calls
- **Tree-sitter**: Optional dependency for AST analysis
- **Shell Integration**: Bash scripts provide CLI interface to Python core
- **Archive Format**: Text-based format designed for LLM consumption and human readability