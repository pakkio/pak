# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pak is a semantic compression tool family designed to solve the copy-paste workflow problem when working with LLMs. It packages multiple files into LLM-friendly formats and extracts modified code back to proper file structures.

The repository contains two main variants:
- **pak** (Bash script) - Simple, zero-dependency solution for basic operations
- **pak.py** (Python CLI) - Full-featured with semantic LLM compression and method-level diff support

## Core Architecture

### Main Components

**pak.py** - Primary Python CLI containing:
- `SmartArchiver` class: Main orchestration for file collection, compression, and archive generation
- Multiple compression strategies: None, Light, Medium, Aggressive (AST-based), and Semantic (LLM-based)
- `FilePrioritizer`: Assigns importance scores to files for smart compression
- `LanguageDetector`: Maps file extensions to language identifiers
- Archive format handlers for listing and extraction
- **Method-level diff system**: Generate, verify, and apply granular code changes

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

### Setup and Dependencies
```bash
# Install Python dependencies via Poetry (includes pytest)
poetry install

# Make bash scripts executable
chmod +x pak pak3 pak4

# Setup environment for semantic compression (optional)
cp .env.sample .env  # Configure OPENROUTER_API_KEY if needed

# Verify installation and check tree-sitter availability
./pak4 --version
python3 pak_core.py --version

# Verify pytest setup
poetry run pytest --version
```

### Running pak.py (Main Python CLI)
```bash
# Basic packing (default command)
./pak.py src/ -c smart -m 8000
# or
python3 pak.py src/ -c smart -m 8000

# List and extract operations
./pak.py -l archive.pak
./pak.py -x archive.pak -d output/

# Method diff workflow
./pak.py --diff original.py modified.py -o changes.diff  # Generate diff
./pak.py -vd changes.diff                               # Verify diff
./pak.py -ad changes.diff target_project/               # Apply diff

# With semantic compression (requires .env setup)
PAK_DEBUG=true ./pak.py -c semantic src/

# Legacy syntax (backward compatible)
./pak --compress-level smart --max-tokens 8000 src/
./pak --ext .py .md --compress-level semantic .

# Version and help
./pak.py --version
./pak.py --help
```

### Testing Commands
```bash
# Run main integration test suite (method diff functionality)
python3 test_method_diff.py

# Run pytest-based unit tests for individual modules
poetry run pytest tests/ -v

# Test semantic compressor with mock LLM (no API calls)
python3 test_semantic_compressor.py <file_path> semantic <language>

# Format code with Black
black .

# Test individual components manually
./pak.py test_method_diff/ -c smart -m 5000    # Test with small dataset
./pak.py -l archive.pak                        # Verify archive format
./pak.py -vd changes.diff                      # Verify diff syntax
```

### Script Variants
```bash
# pak - Simple bash version (zero dependencies)
./pak src/ --compress-level medium

# pak.py - Full featured Python CLI (recommended)
./pak.py . -c smart -m 8000 -o project.pak

# Legacy pak3/pak4 bash scripts (deprecated)
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

## Testing Architecture

The project uses a **mixed testing approach** combining integration tests and unit tests:

### Test Structure
- **`test_method_diff.py`** - Main integration test suite for pak4 method diff system (creates real test files, runs CLI commands, verifies results)
- **`test_method_diff/`** - Directory with original/modified/target test files and generated diffs for testing
- **`test_pak_core_integration.py`** - Integration tests for pak_core.py Python backend (tests all CLI commands end-to-end)
- **`test_pak4_integration.py`** - Integration tests for pak4 bash script driving pak_core.py (tests full user workflow)
- **`tests/`** - pytest-based unit tests for the 6 core modules:
  - `test_pak_analyzer.py` - Tests language detection and analysis
  - `test_pak_archive_manager.py` - Tests archive format handling
  - `test_pak_compressor.py` - Tests compression strategies and token counting
  - `test_pak_differ.py` - Tests method diff extraction and application
  - `test_pak_utils.py` - Tests file collection utilities
  - `test_llm_wrapper.py` - Tests LLM API integration
- **`test_semantic_compressor.py`** - Mock LLM for testing semantic compression without API calls

### Testing Patterns
1. **Integration Testing**: Create test files, run actual pak CLI commands, verify end-to-end workflows
2. **Unit Testing**: pytest-based tests for individual modules and functions
3. **Round-trip Testing**: pack → extract → compare workflows to ensure data integrity
4. **Mock Testing**: Use fake semantic compressor to test compression logic without API costs
5. **Multi-language Testing**: Test method diff system across Python, JavaScript, and Java

### Development Testing Workflow
```bash
# Primary integration tests
python3 test_method_diff.py                      # Original method diff integration test
python3 test_pak_core_integration.py             # pak_core.py CLI integration tests
python3 test_pak4_integration.py                 # pak_core.py integration tests (updated)

# Unit tests for the 6 core modules
poetry run pytest tests/ -v                      # Run all module tests
poetry run pytest tests/test_pak_differ.py -v    # Test method diff functionality
poetry run pytest tests/test_pak_compressor.py -v # Test compression strategies
poetry run pytest tests/test_pak_analyzer.py -v   # Test language detection

# Manual verification with debug output
PAK_DEBUG=true ./pak.py test_method_diff/ -c smart -m 5000

# Test archive integrity
./pak.py -v archive.pak

# Test specific method diff workflow
./pak.py --diff original.py modified.py -o test.diff
./pak.py -vd test.diff
./pak.py -ad test.diff target_file.py

# Run all tests in sequence
poetry run pytest tests/ -v && python3 test_pak_core_integration.py && python3 test_pak4_integration.py
```

## Environment Variables and Configuration

- `OPENROUTER_API_KEY`: API key for LLM-based semantic compression (in .env file)
- `SEMANTIC_COMPRESSOR_PATH`: Path to semantic_compressor.py for LLM compression
- `PAK_DEBUG`: Enable detailed debug output for semantic compression
- `PAK_QUIET`: Suppress stderr messages during compression
- Tree-sitter requires proper Python environment with required packages

### Configuration Files
- **`.env`** - Environment variables for API keys (copy from .env.sample)
- **`pyproject.toml`** - Python dependencies managed by Poetry
- **No formal linting config** - Black is available but runs manually

## Integration Points

- **LLM Integration**: Uses `llm_wrapper.py` for API calls to external LLM services
- **Tree-sitter**: Optional dependency for AST analysis (automatically falls back to text-based compression if unavailable)
- **CLI Integration**: `pak.py` is the main Python CLI entry point
- **Archive Format**: Custom JSON-based format with UUID markers designed for LLM consumption and human readability
- **Multi-language Support**: Python, JavaScript, Java method extraction and diff application

## Development Notes

### Code Quality
- Use `black .` for code formatting before commits
- Run both integration tests (`python3 test_method_diff.py`) and unit tests for the 6 core modules (`poetry run pytest tests/ -v`) 
- No automated CI/CD - testing is manual
- Debug mode available via `PAK_DEBUG=true` environment variable

### Module Architecture
The codebase follows a modular pattern where `pak.py` orchestrates specialized modules:
- **pak_compressor.py** - Compression strategies and token management
- **pak_differ.py** - Method-level diff extraction and application  
- **pak_archive_manager.py** - Archive format handling
- **pak_utils.py** - File collection and utilities
- **pak_analyzer.py** - Language-specific analysis

### Architecture Simplification (v5.0.0)
**IMPORTANT**: The pak tool family has been consolidated to two main variants:

- **pak** (Bash script) - Simple, zero-dependency solution for basic tasks
- **pak.py** (Python CLI) - Full-featured with semantic compression and method diff support

**Benefits of the simplification:**
- Eliminates confusing multiple variants (pak3, pak4 bash wrapper)
- Single Python entry point (`pak.py`) for all advanced features
- Direct Python execution is more reliable and debuggable
- Unified CLI interface with consistent argument handling
- Better error messages and help system

### Version Management
- `pak` (bash) and `pak.py` (Python) are the two supported variants
- pak.py is version 5.0.0+ with full feature set and backward compatibility
- Legacy pak3/pak4 bash scripts are deprecated
- Backward compatibility maintained across versions

## Standalone Executables

From version 5, you can use `pak` and `ast_helper` as standalone executables (no Python required) by copying them to `~/bin`:

```bash
cp dist/pak ~/bin/
cp dist/ast_helper ~/bin/
```
Ensure `~/bin` is in your `$PATH`.

You can now run:

```bash
pak ...
ast_helper ...
```

These executables bundle all dependencies (including tree-sitter for AST analysis) and work on any compatible Linux system.

### Build & Deployment

To build the standalone executables, use Poetry and PyInstaller:

```bash
poetry run pyinstaller --onefile pak.py
poetry run pyinstaller --onefile ast_helper.py
```
The executables will be created in the `dist/` directory. Copy them to `~/bin` as shown above.

### Troubleshooting
- Make sure the files are executable: `chmod +x ~/bin/pak ~/bin/ast_helper`
- Check that `~/bin` is in your `$PATH`
- If you encounter issues with PyInstaller, rebuild as above
