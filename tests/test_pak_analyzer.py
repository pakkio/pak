import pytest
from pak_analyzer import PythonAnalyzer

SAMPLE_CODE_V1 = """
import os, sys
from my_module import specific_import

GLOBAL_VAR = 100
another_var: int = 20

class MyClass(BaseClass):
    cls_attr = "classy"
    def __init__(self, value: int):
        self.value = value

    def greet(self, name: str) -> str:
        return f"Hello, {name}!"

def top_level_func(a, b: int) -> int:
    return a + b
"""

SAMPLE_CODE_V2_MODIFIED = """
import os # sys removed
from my_module import specific_import, another_one # new import

GLOBAL_VAR = 200 # Modified
NEW_GLOBAL = "new"

class MyClass(BaseClass): # No change in signature
    cls_attr = "classy_v2" # Modified
    def __init__(self, value: int): # No change
        self.value = value

    def greet(self, name: str, title: str = "") -> str: # Signature and body modified
        return f"Greetings, {title} {name}!"

    def new_method(self): # Added method
        return "brand new"

# top_level_func removed
async def async_top_level_func(): # Added async func
    pass
"""

def test_extract_structure_basic(sample_python_code_str):
    structure = PythonAnalyzer.extract_structure(sample_python_code_str)
    assert "error" not in structure
    assert "import os" in structure["imports"]
    assert any("MyClass" in c["signature"] for c in structure["classes"])
    assert any("greet(" in m for c in structure["classes"] for m in c["methods"] if "MyClass" in c["signature"])
    assert "def top_level_func(a, b)" in structure["functions"]

def test_extract_structure_syntax_error():
    code = "def foo(:::"
    structure = PythonAnalyzer.extract_structure(code)
    assert "error" in structure
    assert "Invalid Python syntax" in structure["error"]

def test_extract_methods_basic(sample_python_code_str):
    methods = PythonAnalyzer.extract_methods(sample_python_code_str)
    method_names = [m["name"] for m in methods]
    assert "__init__" in method_names
    assert "greet" in method_names
    assert "top_level_func" in method_names
    greet_method = next(m for m in methods if m["name"] == "greet")
    assert "def greet(self, name: str) -> str" in greet_method["signature"]
    assert "message = f" in greet_method["source"]

def test_compare_methods_no_changes():
    diffs = PythonAnalyzer.compare_methods(SAMPLE_CODE_V1, SAMPLE_CODE_V1)
    assert len(diffs) == 0

def test_compare_methods_added():
    diffs = PythonAnalyzer.compare_methods(SAMPLE_CODE_V1, SAMPLE_CODE_V2_MODIFIED)
    added_diffs = [d for d in diffs if d["type"] == "added"]
    added_names = {d["method_name"] for d in added_diffs}
    assert "new_method" in added_names
    assert "async_top_level_func" in added_names

def test_compare_methods_removed():
    diffs = PythonAnalyzer.compare_methods(SAMPLE_CODE_V1, SAMPLE_CODE_V2_MODIFIED)
    removed_diffs = [d for d in diffs if d["type"] == "removed"]
    assert any(d["method_name"] == "top_level_func" for d in removed_diffs)

def test_compare_methods_modified():
    diffs = PythonAnalyzer.compare_methods(SAMPLE_CODE_V1, SAMPLE_CODE_V2_MODIFIED)
    modified_diffs = [d for d in diffs if d["type"] == "modified"]
    assert any(d["method_name"] == "greet" for d in modified_diffs)
    greet_diff = next(d for d in modified_diffs if d["method_name"] == "greet")
    assert "Greetings," in greet_diff["new_source"]
    assert "def greet(self, name: str, title: str = "") -> str" in greet_diff["new_signature"]
