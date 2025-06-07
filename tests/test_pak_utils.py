import pytest
import os
from pathlib import Path
from pak_utils import collect_files # Assumes pak_utils.py is in PYTHONPATH or project root

def test_collect_single_file(temp_dir_fixture):
    file_path = temp_dir_fixture / "file1.txt"
    file_path.write_text("content")
    result = collect_files([str(file_path)], [], quiet=True)
    assert len(result) == 1
    assert os.path.normpath(result[0]) == os.path.normpath(str(file_path))

def test_collect_single_file_with_matching_ext(temp_dir_fixture):
    file_path = temp_dir_fixture / "file1.py"
    file_path.write_text("content")
    result = collect_files([str(file_path)], [".py"], quiet=True)
    assert len(result) == 1
    assert os.path.normpath(result[0]) == os.path.normpath(str(file_path))

def test_collect_single_file_with_non_matching_ext(temp_dir_fixture):
    file_path = temp_dir_fixture / "file1.txt"
    file_path.write_text("content")
    result = collect_files([str(file_path)], [".py"], quiet=True)
    assert len(result) == 0

def test_collect_directory_no_ext_filter(temp_dir_fixture):
    (temp_dir_fixture / "file1.txt").write_text("txt")
    (temp_dir_fixture / "file2.py").write_text("py")
    subdir = temp_dir_fixture / "subdir"
    subdir.mkdir()
    (subdir / "file3.md").write_text("md")

    result = collect_files([str(temp_dir_fixture)], [], quiet=True)
    assert len(result) == 3
    paths = {os.path.normpath(p) for p in result}
    expected_paths = {
        os.path.normpath(temp_dir_fixture / "file1.txt"),
        os.path.normpath(temp_dir_fixture / "file2.py"),
        os.path.normpath(subdir / "file3.md"),
    }
    assert paths == expected_paths

def test_collect_directory_with_ext_filter(temp_dir_fixture):
    (temp_dir_fixture / "file1.txt").write_text("txt")
    (temp_dir_fixture / "file2.py").write_text("py")
    (temp_dir_fixture / "file3.py").write_text("py2")

    result = collect_files([str(temp_dir_fixture)], [".py"], quiet=True)
    assert len(result) == 2
    paths = {os.path.normpath(p) for p in result}
    expected_paths = {
        os.path.normpath(temp_dir_fixture / "file2.py"),
        os.path.normpath(temp_dir_fixture / "file3.py"),
    }
    assert paths == expected_paths

def test_collect_glob_pattern_files_only(temp_dir_fixture):
    (temp_dir_fixture / "file1.txt").write_text("txt1")
    (temp_dir_fixture / "file2.txt").write_text("txt2")
    (temp_dir_fixture / "file3.py").write_text("py")

    # Need to change CWD for glob to work reliably relative to temp_dir_fixture
    original_cwd = os.getcwd()
    os.chdir(temp_dir_fixture)
    try:
        result = collect_files(["*.txt"], [], quiet=True)
        assert len(result) == 2
        paths = {os.path.normpath(p) for p in result} # Globs return relative paths here
        expected_paths = {
            os.path.normpath("file1.txt"),
            os.path.normpath("file2.txt"),
        }
        assert paths == expected_paths
    finally:
        os.chdir(original_cwd)

def test_collect_non_existent_target():
    result = collect_files(["non_existent_path_123"], [], quiet=True)
    assert len(result) == 0

def test_collect_empty_targets_list():
    result = collect_files([], [".txt"], quiet=True)
    assert len(result) == 0
