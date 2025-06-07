import pytest
import os
from pathlib import Path
from pak_differ import MethodDiffManager
from pak_analyzer import PythonAnalyzer # Used for verification

# Fixtures for content are in conftest.py (diff_sample_file1_content_str, etc.)

@pytest.fixture
def temp_diff_files(temp_dir_fixture, diff_sample_file1_content_str, diff_sample_file2_content_str):
    base_file = temp_dir_fixture / "base_file.py"
    modified_file = temp_dir_fixture / "modified_file.py"
    base_file.write_text(diff_sample_file1_content_str)
    modified_file.write_text(diff_sample_file2_content_str)
    return base_file, modified_file

def test_extract_diff_valid_files(temp_diff_files):
    base_file, modified_file = temp_diff_files
    diff_instructions = MethodDiffManager.extract_diff([str(base_file), str(modified_file)], quiet=True)

    assert len(diff_instructions) > 0 # Expecting changes

    hello_diff = next((d for d in diff_instructions if "hello" in d.get("find_method", "") or "hello" in d.get("replace_with", "")), None)
    subtract_diff = next((d for d in diff_instructions if "subtract" in d.get("replace_with", "")), None)

    assert hello_diff is not None
    assert hello_diff["file"] == "modified_file.py"
    assert "def hello()" in hello_diff["find_method"]
    assert "Hello Universe!" in hello_diff["replace_with"]
    assert "def add(a, b):" in hello_diff["until_exclude"] # Next method in base

    assert subtract_diff is not None
    assert subtract_diff["file"] == "modified_file.py"
    assert not subtract_diff["find_method"] # Added method
    assert "def subtract(a, b):" in subtract_diff["replace_with"]

def test_extract_diff_base_not_found(temp_dir_fixture):
    modified_file = temp_dir_fixture / "mod.py"
    modified_file.write_text("content")
    with pytest.raises(FileNotFoundError):
        MethodDiffManager.extract_diff(["non_existent_base.py", str(modified_file)], quiet=True)

def test_extract_diff_identical_files(temp_diff_files):
    base_file, _ = temp_diff_files # Use base_file for both
    diff_instructions = MethodDiffManager.extract_diff([str(base_file), str(base_file)], quiet=True)
    assert len(diff_instructions) == 0

def test_parse_diff_file_valid(temp_dir_fixture, sample_valid_method_diff_content_str):
    diff_file = temp_dir_fixture / "test.diff"
    diff_file.write_text(sample_valid_method_diff_content_str)

    instructions = MethodDiffManager._parse_diff_file(str(diff_file), quiet=True)
    assert len(instructions) == 1
    instr = instructions[0]
    assert instr["file"] == "sample_target_file.py"
    assert instr["find_method"] == "def hello()"
    assert instr["until_exclude"] == "def add(a, b):"
    assert "Hello Diff Applied!" in instr["replace_with"]

def test_parse_diff_file_empty(temp_dir_fixture):
    diff_file = temp_dir_fixture / "empty.diff"
    diff_file.write_text("")
    instructions = MethodDiffManager._parse_diff_file(str(diff_file), quiet=True)
    assert len(instructions) == 0

def test_verify_diff_file_valid(temp_dir_fixture, sample_valid_method_diff_content_str):
    diff_file = temp_dir_fixture / "valid.diff"
    diff_file.write_text(sample_valid_method_diff_content_str)
    assert MethodDiffManager.verify_diff_file(str(diff_file), quiet=True) is True

def test_verify_diff_file_invalid_structure(temp_dir_fixture):
    invalid_content = "FIND_METHOD: def test()\nREPLACE_WITH:\n  pass" # Missing FILE
    diff_file = temp_dir_fixture / "invalid.diff"
    diff_file.write_text(invalid_content)
    assert MethodDiffManager.verify_diff_file(str(diff_file), quiet=True) is False

def test_apply_diff_to_single_file(temp_dir_fixture, diff_sample_file1_content_str, sample_valid_method_diff_content_str):
    target_apply_file = temp_dir_fixture / "target_to_apply.py"
    target_apply_file.write_text(diff_sample_file1_content_str) # Starts like file1

    diff_file = temp_dir_fixture / "apply.diff"
    # This diff expects to change "def hello()" to print "Hello Diff Applied!"
    diff_file.write_text(sample_valid_method_diff_content_str)

    success = MethodDiffManager.apply_diff(str(diff_file), str(target_apply_file), quiet=False) # Not quiet to see logs
    assert success is True

    modified_content = target_apply_file.read_text()
    assert "Hello Diff Applied!" in modified_content
    assert "Hello World" not in modified_content # Original print should be gone
    assert "def add(a, b):" in modified_content # Ensure 'add' method is still there

def test_apply_diff_file_creation_for_added(temp_dir_fixture):
    target_dir = temp_dir_fixture / "project"
    target_dir.mkdir()

    new_file_diff_content = """FILE: new_module.py
FIND_METHOD:
UNTIL_EXCLUDE:
REPLACE_WITH:
def brand_new_function():
    return "created from diff"
"""
    diff_file = temp_dir_fixture / "create_new.diff"
    diff_file.write_text(new_file_diff_content)

    success = MethodDiffManager.apply_diff(str(diff_file), str(target_dir), quiet=True)
    assert success is True

    created_file_path = target_dir / "new_module.py"
    assert created_file_path.exists()
    assert "brand_new_function" in created_file_path.read_text()

def test_apply_diff_signature_not_found_in_target(temp_dir_fixture, diff_sample_file1_content_str):
    target_file = temp_dir_fixture / "target.py"
    target_file.write_text(diff_sample_file1_content_str) # Contains "def hello()"

    non_matching_diff = """FILE: target.py
FIND_METHOD: def non_existent_function()
UNTIL_EXCLUDE:
REPLACE_WITH:
    pass # Should not be applied
"""
    diff_file = temp_dir_fixture / "nomatch.diff"
    diff_file.write_text(non_matching_diff)

    success = MethodDiffManager.apply_diff(str(diff_file), str(target_file), quiet=True)
    assert success is False # The specific diff for non_existent_function should fail
    # The file content should remain unchanged
    assert target_file.read_text() == diff_sample_file1_content_str
