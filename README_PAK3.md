# Pak - Token-Optimized AST-Enhanced File Archiver for LLMs

**Version: 2.2.9**

## Abstract

`pak` is a command-line utility enhanced with **semantic AST analysis**, designed to transform code projects into textual archives optimized for Large Language Models. Version 2.2.9 introduces **Abstract Syntax Tree** support via tree-sitter, enabling intelligent compression that *understands* code structure rather than applying simple textual patterns. The result is a `.pak` archive that maximizes signal-to-noise ratio for productive conversations with Claude, GPT, and other LLMs.

## Introduction

In a world where every token counts in LLM interactions, pak goes beyond simple file concatenation. The new AST-enhanced architecture analyzes the **syntactic structure** of code, distinguishing between essential elements (API definitions, interfaces, signatures) and redundancies (verbose comments, excessive whitespace, implementation details).

This semantic approach produces dramatically more compact archives while maintaining context intelligibility - exactly what's needed when you need to make a complex project "understandable" to a language model.

## New AST Capabilities

### Advanced Semantic Compression

pak3's AST mode uses **tree-sitter** to parse code at the syntactic level, not textual. This means:

- **Intelligent comment removal**: eliminates only those not semantically relevant
- **API surface extraction**: maintains signatures, interfaces, public definitions
- **Structural compression**: preserves architectural logic while removing verbose implementation
- **Graceful fallback**: if AST fails, automatically uses textual algorithms as backup

### AST-Supported Languages

Version 2.2.9 supports AST analysis for:

- **Python** (via tree-sitter-python)
- **JavaScript/TypeScript** (via tree-sitter-languages)
- **Java, C/C++, Go, Rust** (via tree-sitter-languages)
- **Ruby, PHP, C#** (via tree-sitter-languages)

For languages not supported by AST, pak continues to use optimized textual compression algorithms.

### Auto-Installation of Dependencies

pak3 can automatically install required Python dependencies:

```bash
# On first use with AST compression, pak will automatically attempt:
pip3 install --user tree-sitter tree-sitter-languages tree-sitter-python
```

Auto-installation can be disabled with `--disable-auto-install` if you prefer to manage dependencies manually.

## Modular Architecture

pak3 introduces a component-based architecture:

- **`pak3`**: Main bash script with orchestration logic
- **`ast_helper.py`**: AST compression engine for supported languages
- **`python_extractor.py`**: Specialized extractor for Python structures

This modularity enables future extensions and customizations for specific use cases.

## Compression Modes

### Traditional Compression Levels

- **`none`**: No compression, pure textual archive
- **`light`**: Whitespace and empty line removal
- **`medium`**: Comment elimination + textual optimizations
- **`aggressive`**: Extraction of only essential structures

### Smart Mode with Token Budget

- **`smart`**: Adaptive compression based on:
  - **Semantic importance** of files (README > utility, main.py > test.py)
  - **Available token budget** (compresses more aggressively when necessary)
  - **Content type** (code vs documentation vs configuration)

## Token Management and Prioritization

pak3 introduces a sophisticated **budget management** system:

```bash
# Example: 50k token project compressed to 8k for Claude
pak --compress-level smart --max-tokens 8000 ./my_project > optimized.pak
```

The prioritization algorithm considers:

1. **Critical importance files**: README, main.py, index.js, core modules
2. **Support files**: utilities, helpers, configurations
3. **Test and mock files**: aggressively compressed or excluded if necessary

## Installation and Dependencies

### Basic Installation

```bash
# Download and setup
chmod +x pak3
mv pak3 /usr/local/bin/

# Verify AST capabilities
pak3 --ast-info
```

### Complete AST Setup

To fully leverage AST capabilities:

```bash
# Manual dependency installation (recommended)
pip3 install --user tree-sitter tree-sitter-languages tree-sitter-python

# Or let pak auto-install on first use
pak3 --compress-level aggressive ./src > project.pak
```

## Advanced Usage Examples

### Aggressive Compression of a Python Project

```bash
# Extracts only APIs, classes, functions - ideal for LLM code review
pak3 --compress-level aggressive --max-tokens 12000 \
     --ext .py .md ./my_django_project > api_surface.pak
```

### Smart Mode for Multi-language Projects

```bash
# Intelligent prioritization, adaptive compression
pak3 --compress-level smart --max-tokens 16000 \
     ./full_stack_project > smart_context.pak
```

### AST Debug and Verification

```bash
# Show available AST capabilities
pak3 --ast-info

# Verify compression results
pak3 --verify smart_context.pak

# List contents with compression metadata
pak3 --ls smart_context.pak
```

## Enhanced Archive Format

pak3 archives include extended metadata:

```
__PAK_ID__:aF30uOVUH0s5
# Archive created with pak v2.2.9
# Archive ID: aF30uOVUH0s5
# Compression Mode: aggressive
# AST Support: enabled
# Extension Filter: .py .js .md
# Token Limit: 8000

__PAK_FILE_aF30uOVUH0s5_START__
Path: src/api/models.py
Language: python
Size: 3247
Lines: 89
Tokens: 723
Compression: aggressive
Method: AST-enabled (via helper)
__PAK_DATA_aF30uOVUH0s5_START__
[semantically compressed content...]
```

## Benefits of AST Compression

### For Developers and Code Review

- **Optimal signal-to-noise ratio**: LLMs see architecture, not verbose implementation
- **Efficient context switching**: 50k lines → 8k tokens while maintaining comprehensibility
- **Focus on design patterns**: architectural decisions emerge naturally

### For Productive LLM Interactions

- **Deeper conversations**: token budget freed for complex questions
- **Multi-file analysis**: LLM can "see" the entire project in one pass
- **Intelligent refactoring**: suggestions based on complete structure, not fragments

## Limitations and Considerations

### Python Dependencies

Full AST support requires a functional Python environment with tree-sitter libraries. In constrained environments, pak3 automatically falls back to textual compression.

### Compression Accuracy

**Aggressive** compression is *opinionated* - it privileges API surface and structure over implementation details. For debugging specific bugs, consider more conservative compression levels.

### Language Support

Languages not supported by AST (shell scripts, config files, markdown) use textual algorithms that are still effective, but less semantically precise.

## Roadmap and Extensibility

pak3's modular architecture facilitates:

- **New language parsers** via tree-sitter ecosystem
- **Custom compression strategies** for specific domains
- **IDE and CI/CD integration** for automated workflows
- **Alternative output formats** (JSON, structured markdown)

## Conclusion

pak3 represents an evolutionary leap in code optimization for LLMs. The combination of AST analysis, semantic compression, and intelligent token budget management makes it an indispensable tool for developers who want to maximize the productivity of their interactions with AI assistants.

No longer necessary to choose between complete context and token budget: pak3 lets you have both, intelligently.

---

**Development Notes**: pak3 is optimized for Unix/Linux systems with bash 4+. Tested on Ubuntu 24+, compatible with most modern distributions.
