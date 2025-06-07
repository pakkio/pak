import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def temp_dir_fixture(): # Renamed to avoid clash if user has temp_dir
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def sample_python_code_str(): # Provides content directly
    return """
import os
# This is a comment
class MyClass:
    '''Docstring for MyClass.'''
    cls_var: int = 10

    def __init__(self, value):
        self.value = value

    def greet(self, name: str) -> str:
        # A comment inside method
        message = f"Hello, {name}! Value is {self.value}"
        return message

def top_level_func(a, b):
    # This is a simple function
    return a + b
"""

@pytest.fixture
def sample_text_content_str(): # Provides content directly
    return """
This is a line.

This is another line after a blank.

    Indented line.
Trailing spaces here.

Final line.

"""

@pytest.fixture
def diff_sample_file1_content_str():
    return """def hello():
    print("Hello World")

def add(a, b):
    return a + b
"""

@pytest.fixture
def diff_sample_file2_content_str():
    return """def hello():
    print("Hello Universe!")  # Modified

def add(a, b):
    return a + b

def subtract(a, b):  # New method
    return a - b
"""

# Fixture for a valid pak file content as a string
@pytest.fixture
def sample_valid_archive_content_str():
    return """{
  "metadata": {
    "pak_format_version": "4.2.0-refactored",
    "archive_uuid": "sample-uuid-123",
    "creation_timestamp_utc": "2023-01-01T00:00:00Z",
    "source_tool_version": "pak_core_refactored_v_test",
    "compression_level_setting": "none",
    "max_tokens_setting": 0,
    "total_files": 1,
    "total_original_size_bytes": 12,
    "total_compressed_size_bytes": 12,
    "total_estimated_tokens": 2
  },
  "files": [
    {
      "path": "sample.txt",
      "content": "Hello world.",
      "original_size_bytes": 12,
      "compressed_size_bytes": 12,
      "estimated_tokens": 2,
      "compression_method": "none",
      "compression_ratio": 1.0,
      "importance_score": 0,
      "last_modified_utc": "2023-01-01T00:00:00Z"
    }
  ]
}"""

@pytest.fixture
def sample_valid_method_diff_content_str():
    return """FILE: sample_target_file.py
FIND_METHOD: def hello()
UNTIL_EXCLUDE: def add(a, b):
REPLACE_WITH:
def hello():
    print("Hello Diff Applied!")
"""
