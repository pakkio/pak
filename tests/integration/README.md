# Integration Tests

This directory contains integration tests for pak's advanced features.

## Test Suites

### `test_pakdiff_multilang.py`

Comprehensive integration tests for the enhanced pakdiff format v4.3.0, covering:

- **Multi-language support**: Python, C++, configuration files
- **GLOBAL_PREAMBLE sections**: Import/include statement management
- **Decorator handling**: Proper inclusion and removal of Python decorators
- **Method-level changes**: Add, modify, delete operations across languages
- **Boundary detection**: Automatic detection of global section boundaries
- **Mixed changes**: Combined global and method changes in single files

### Test Structure

```
tests/integration/pakdiff_multilang/
├── original/           # Original source files
│   ├── calculator.py   # Python with decorators and classes
│   ├── geometry.cpp    # C++ with templates and namespaces
│   └── config.txt      # Configuration file with sections
├── modified/           # Enhanced versions of source files
│   ├── calculator.py   # Added typing, logging, validation
│   ├── geometry.cpp    # Added error handling, new classes
│   └── config.txt      # Updated settings and new sections
└── expected_diffs/     # Expected pakdiff files
    ├── python_enhanced.diff   # Python changes with GLOBAL_PREAMBLE
    ├── cpp_enhanced.diff      # C++ changes with templates
    └── config_enhanced.diff   # Config section changes
```

## Running Tests

```bash
# Run all integration tests
python -m pytest tests/integration/ -v

# Run specific multi-language tests
python -m pytest tests/integration/test_pakdiff_multilang.py -v

# Run individual test methods
python -m pytest tests/integration/test_pakdiff_multilang.py::TestPakdiffMultiLanguage::test_python_global_preamble_and_decorator_removal -v
```

## Test Coverage

The integration tests verify:

1. **Format Validation**: All pakdiff files pass syntax validation
2. **GLOBAL_PREAMBLE Application**: Header sections are replaced correctly
3. **Decorator Handling**: Python decorators are properly removed
4. **Method Transformations**: Function bodies are updated with proper boundaries
5. **Cross-Language Support**: C++ templates, namespaces, and STL usage
6. **Configuration Files**: Section-based changes in non-code files
7. **Boundary Detection**: Automatic detection when UNTIL_EXCLUDE is omitted
8. **Mixed Operations**: Global and method changes applied in sequence

## Expected Behavior

- All diff files should validate successfully
- GLOBAL_PREAMBLE sections should replace file headers completely
- Method changes should preserve indentation and structure
- Boundary detection should work without explicit UNTIL_EXCLUDE markers
- Multi-language transformations should maintain language-specific syntax