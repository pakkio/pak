# Pak: The Ultimate LLM Code Context Tool

## The Problem We All Face (But Rarely Admit)

You're a developer in 2025. You use Claude, ChatGPT, or any other LLM for practically every development task. And every single time, it's the same **comedy of errors**:

- You need to share 5-10 files with the LLM for proper context
- Open first file → Ctrl+A → Ctrl+C → go to chat → add "File: path/file.py" → Ctrl+V
- Repeat for every single file, praying you don't mess up the order
- After 15 minutes you have a prompt that looks like university notes collage
- The LLM responds with modified code in separate blocks
- **The real nightmare**: now you have to copy each piece back from the LLM and save it to the right file
- You make mistakes, overwrite something important, and curse in your native dialect

**This little theater 20 times a day.**

If this workflow sounds familiar, Pak was born for you.

## The Solution: One Tool, Multiple Approaches, Zero Compromises

Pak is a **semantic compression tool** that packages multiple files into LLM-friendly formats and extracts modified code back to proper file structures. It's evolved from a simple bash script into a sophisticated Python CLI with advanced features.

### Key Features

- **Semantic Compression**: Uses AST analysis and even LLM-based compression to understand code structure
- **Method-Level Diffs**: Generate, verify, and apply granular code changes with global section support
- **Smart Prioritization**: Automatically distinguishes between critical files and less important ones
- **Token Budget Management**: Rigorous token counting with adaptive compression
- **Multi-Language Support**: Python, JavaScript, Java, and more
- **Backward Compatibility**: Supports both modern and legacy syntax

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/pak.git
cd pak

# Install dependencies
poetry install

# Make scripts executable
chmod +x pak.py install.sh

# Install standalone executables (optional)
./install.sh
```

### Basic Usage

```bash
# Pack current directory with smart compression
./pak.py . -c smart -m 8000 -o project.pak

# Using installed executable (after ./install.sh)
pak . -c smart -m 8000 -o project.pak

# List archive contents
./pak.py -l project.pak

# Extract archive
./pak.py -x project.pak -d output/

# Method diff workflow
./pak.py --diff original.py modified.py -o changes.diff
./pak.py -vd changes.diff  # Verify diff
./pak.py -ad changes.diff target_file.py  # Apply diff
```

## Compression Levels

| Level | Description | Use Case |
|-------|-------------|----------|
| `0/none` | Raw content | When you need exact files |
| `1/light` | Basic whitespace removal | Quick cleanup |
| `2/medium` | Light + comment removal | Balanced approach |
| `3/aggressive` | AST-based structure extraction | Maximum compression |
| `4/semantic` | LLM-based semantic compression | AI-powered optimization |
| `s/smart` | Adaptive compression with fallback | Recommended for most cases |

## Advanced Features

### Semantic Compression

Pak can use external LLM services to intelligently compress code while maintaining semantic meaning:

```bash
# Setup (one time)
cp .env.sample .env
# Edit .env and add your OPENROUTER_API_KEY

# Use semantic compression
./pak.py src/ -c semantic -m 8000
```

### Method-Level Diffs (v4.3.0)

Extract and apply changes at the method/function level rather than entire files. Now supports global sections for imports, constants, and module-level changes across multiple programming languages:

```bash
# Extract differences between files
./pak.py --diff original.py modified.py -o changes.diff

# Verify the diff file (supports GLOBAL_PREAMBLE sections)
./pak.py -vd changes.diff

# Apply changes to target files (handles decorators correctly)
./pak.py -ad changes.diff target_directory/
```

**Enhanced v4.3.0 features:**
- **Multi-language support**: Python, C++, Java, Go, Rust, configuration files
- **GLOBAL_PREAMBLE sections**: Handle imports, includes, constants, and module-level variables
- **Decorator handling**: Proper removal/addition of decorators like `@property` with boundary detection
- **Mixed changes**: Combine global and method changes in single diff files
- **Automatic boundary detection**: Smart detection of section boundaries when UNTIL_EXCLUDE is omitted
- **LLM integration prompts**: Self-documenting format with embedded analysis templates
- **Configuration file support**: Section-based changes for INI, YAML, and other config formats

### File Filtering

```bash
# Include only specific file types
./pak.py src/ -t py,js,md -c medium

# Legacy extension syntax
./pak --ext .py .js .md --compress-level medium src/
```

## Examples

### Scenario 1: Quick Bug Fix

Your Node.js server has an authentication bug:

```bash
# Modern syntax
./pak.py server.js routes/auth.js middleware/ -c smart -o bug-context.pak

# Legacy syntax
./pak --compress-level smart server.js routes/auth.js middleware/ > bug-context.pak
```

### Scenario 2: Large Project Refactoring

Working with a complex Python project:

```bash
# Smart compression with token limit
./pak.py src/ tests/ -t py,md -c smart -m 12000 -o refactor-context.pak

# Extract method-level changes after LLM suggestions
./pak.py --diff src/old_module.py src/new_module.py -o refactor.diff
./pak.py -ad refactor.diff target_project/src/
```

### Scenario 3: Documentation and Code Review

Preparing context for documentation generation:

```bash
# Include documentation and core files
./pak.py README.md docs/ src/core/ -c semantic -m 16000 -o docs-context.pak
```

## Architecture

### Core Components

- **pak.py**: Main Python CLI with full feature set
- **Compression Strategies**: Modular compression system with multiple algorithms
- **Method Diff System**: Granular change extraction and application
- **Archive Format**: Custom JSON-based format optimized for LLM consumption

### Modules

- `pak_compressor.py`: Compression strategies and token management
- `pak_differ.py`: Method-level diff extraction and application
- `pak_archive_manager.py`: Archive format handling
- `pak_utils.py`: File collection and utilities
- `pak_analyzer.py`: Language-specific analysis
- `semantic_compressor.py`: LLM-based semantic compression
- `ast_helper.py`: Tree-sitter AST analysis helper

## Configuration

### Environment Variables

- `OPENROUTER_API_KEY`: API key for LLM-based semantic compression
- `PAK_DEBUG`: Enable detailed debug output
- `PAK_QUIET`: Suppress stderr messages

### Configuration Files

- `.env`: Environment variables (copy from `.env.sample`)
- `pyproject.toml`: Python dependencies managed by Poetry

## Testing

```bash
# Run integration tests
python3 test_method_diff.py
python3 test_pak_core_integration.py

# Run unit tests for all modules
poetry run pytest tests/ -v

# Run pakdiff multi-language integration tests
poetry run pytest tests/integration/test_pakdiff_multilang.py -v

# Run all pakdiff-related tests
poetry run pytest tests/ -k "pakdiff or differ" -v

# Test with debug output
PAK_DEBUG=true ./pak.py test_files/ -c smart -m 5000
```

## Standalone Executables

Build standalone executables that work without Python:

```bash
# Simple build (recommended - uses install.sh)
./install.sh

# Manual build
poetry run pyinstaller --onefile pak.py
poetry run pyinstaller --onefile ast_helper.py

# Use anywhere
pak src/ -c smart -m 8000 -o project.pak
ast_helper analyze_file.py
```

### PyInstaller Notes

**WSL/Virtual Environment Fix**: If you encounter shared library errors like `Failed to load Python shared library`, the build process automatically includes the required `libpython3.12.so` using:

```bash
poetry run pyinstaller --onefile --add-binary "/usr/lib/x86_64-linux-gnu/libpython3.12.so.1.0:." pak.py
```

This fix is already integrated into `pak.spec` and `install.sh`. The issue occurs when:
- Using Poetry virtual environments (which lack the shared Python library)
- Building on WSL or similar environments  
- PyInstaller can't find the Python shared library at runtime

**Build artifacts**: The `build/` and `dist/` directories are created during compilation and can be ignored (add to `.gitignore`).

## Migration from Legacy

If you're upgrading from the bash `pak` script, all your existing commands will work:

```bash
# These commands are equivalent:
./pak --compress-level smart --max-tokens 8000 src/     # Legacy
./pak.py -c smart -m 8000 src/                         # Modern

# Extension filtering:
./pak --ext .py .js .md src/                           # Legacy  
./pak.py -t py,js,md src/                              # Modern
```

## Performance Tips

1. **Use Smart Compression**: `-c smart` automatically chooses the best strategy
2. **Set Token Limits**: Use `-m` to stay within LLM context windows
3. **Filter File Types**: Use `-t` to include only relevant extensions
4. **Enable Caching**: Semantic compression results are automatically cached
5. **Prioritize Files**: Critical files (README, main modules) get higher priority

## Troubleshooting

### Common Issues

**Semantic compression not working?**
- Check that `.env` file exists with valid `OPENROUTER_API_KEY`
- Install required dependencies: `poetry install`

**AST compression failing?**
- Ensure tree-sitter packages are installed
- Falls back to text-based compression automatically

**Token counts seem wrong?**
- Token estimation uses 3 chars = 1 token approximation
- For exact counts, integrate with tiktoken

### Debug Mode

```bash
PAK_DEBUG=true ./pak.py src/ -c semantic -m 8000
```

## Contributing

1. Follow the existing code style (use `black .` for formatting)
2. Run both integration and unit tests
3. Update documentation for new features
4. Test backward compatibility with legacy syntax

## License

[Your License Here]

## Version History

- **v5.0**: Consolidated pak4.py → pak.py, full backward compatibility
- **v4.3**: Enhanced pakdiff format with GLOBAL_PREAMBLE sections and decorator bug fixes
- **v4.2**: Method diff system, semantic compression, AST analysis  
- **v3.x**: Original Python implementation with advanced features
- **v2.x**: Bash script with basic compression
- **v1.x**: Initial implementation

---

*Pak: Because life's too short for copy-paste workflows.*