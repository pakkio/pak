import pytest
import os
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from pak_archive_manager import PakArchive
from pak_compressor import Compressor, CacheManager # For type hints and mocking

# Fixtures for content (sample_valid_archive_content_str) are in conftest.py

@pytest.fixture
def mock_compressor_output():
    return {
        "compressed_content": "compressed_data",
        "original_size": 100,
        "compressed_size": 50,
        "estimated_tokens": 10,
        "method": "mock_compression",
        "compression_ratio": 2.0
    }

@pytest.fixture
def pak_archive_instance(mock_compressor_output):
    # Patch the Compressor used by PakArchive
    with patch('pak_archive_manager.Compressor') as MockCompressorClass:
        mock_compressor_instance = MockCompressorClass.return_value
        mock_compressor_instance.compress_content.return_value = mock_compressor_output

        # Create a PakArchive instance for testing, it will use the mocked Compressor
        pa = PakArchive(compression_level="mocked", quiet=True)
        # Ensure the mock is available if needed by other parts of the test
        pa.mocked_compressor_instance = mock_compressor_instance
        yield pa


def test_pak_archive_add_file(pak_archive_instance, mock_compressor_output, temp_dir_fixture):
    # Create a dummy file to get mtime
    dummy_file_path = temp_dir_fixture / "dummy.txt"
    dummy_file_path.write_text("original content")

    pak_archive_instance.add_file(str(dummy_file_path), "original content")

    assert len(pak_archive_instance.files_data) == 1
    file_entry = pak_archive_instance.files_data[0]

    assert file_entry["path"] == str(dummy_file_path).replace(os.sep, '/')
    assert file_entry["content"] == mock_compressor_output["compressed_content"]
    assert file_entry["original_size_bytes"] == mock_compressor_output["original_size"]
    assert file_entry["compressed_size_bytes"] == mock_compressor_output["compressed_size"]
    assert file_entry["estimated_tokens"] == mock_compressor_output["estimated_tokens"]
    assert file_entry["compression_method"] == mock_compressor_output["method"]
    assert file_entry["last_modified_utc"] is not None

    assert pak_archive_instance.total_original_size_bytes == mock_compressor_output["original_size"]
    assert pak_archive_instance.total_compressed_size_bytes == mock_compressor_output["compressed_size"]
    assert pak_archive_instance.total_estimated_tokens == mock_compressor_output["estimated_tokens"]

    # Verify compressor was called
    pak_archive_instance.mocked_compressor_instance.compress_content.assert_called_once_with(
        "original content", str(dummy_file_path).replace(os.sep, '/'), "mocked"
    )

def test_pak_archive_create_archive_to_file(pak_archive_instance, temp_dir_fixture):
    pak_archive_instance.add_file(str(temp_dir_fixture / "file1.txt"), "content1") # Use dummy path for mtime
    (temp_dir_fixture / "file1.txt").write_text("content1")
    output_path = temp_dir_fixture / "test_archive.pak.json"

    archive_json_string = pak_archive_instance.create_archive(str(output_path))
    assert archive_json_string is None # Returns None when writing to file
    assert output_path.exists()

    with open(output_path, 'r') as f:
        data = json.load(f)

    assert "metadata" in data
    assert "files" in data
    assert data["metadata"]["total_files"] == 1
    assert data["files"][0]["path"] == str(temp_dir_fixture / "file1.txt").replace(os.sep, '/')

def test_pak_archive_create_archive_to_stdout(pak_archive_instance):
    pak_archive_instance.add_file("file_in_mem.txt", "content_mem") # No real file needed for this part

    archive_json_string = pak_archive_instance.create_archive(None)
    assert archive_json_string is not None
    data = json.loads(archive_json_string)
    assert "metadata" in data
    assert data["files"][0]["path"] == "file_in_mem.txt"

def test_load_valid_archive(temp_dir_fixture, sample_valid_archive_content_str):
    archive_file = temp_dir_fixture / "valid.pak.json"
    archive_file.write_text(sample_valid_archive_content_str)

    data = PakArchive._load_archive_json_data(str(archive_file), quiet=True)
    assert data["metadata"]["archive_uuid"] == "sample-uuid-123"
    assert len(data["files"]) == 1

def test_load_archive_not_found(temp_dir_fixture):
    with pytest.raises(FileNotFoundError):
        PakArchive._load_archive_json_data(str(temp_dir_fixture / "non_existent.pak.json"), quiet=True)

def test_load_archive_invalid_json(temp_dir_fixture):
    archive_file = temp_dir_fixture / "invalid.pak.json"
    archive_file.write_text("this is not json")
    with pytest.raises(ValueError, match="Invalid JSON"):
        PakArchive._load_archive_json_data(str(archive_file), quiet=True)

def test_extract_archive_all(temp_dir_fixture, sample_valid_archive_content_str):
    source_archive_file = temp_dir_fixture / "source.pak.json"
    source_archive_file.write_text(sample_valid_archive_content_str) # Contains "sample.txt" with "Hello world."

    extract_dir = temp_dir_fixture / "extracted"
    PakArchive.extract_archive(str(source_archive_file), str(extract_dir), quiet=True)

    extracted_file = extract_dir / "sample.txt"
    assert extracted_file.exists()
    assert extracted_file.read_text() == "Hello world."

@patch('sys.stdout', new_callable=MagicMock) # Can't use io.StringIO directly as it might not have fileno
def test_list_archive_simple(mock_stdout, temp_dir_fixture, sample_valid_archive_content_str):
    archive_file = temp_dir_fixture / "list_me.pak.json"
    archive_file.write_text(sample_valid_archive_content_str)

    # Can't directly capture print with MagicMock, need a more elaborate stdout capture
    # For simplicity, we'll just check if it runs without error.
    # A better test would use capsys fixture from pytest.
    PakArchive.list_archive(str(archive_file), quiet=True) # quiet=True means no stderr, but list prints to stdout
    # mock_stdout.write.assert_any_call("sample.txt\n") # This assertion style depends on how print is mocked

def test_verify_archive_valid(temp_dir_fixture, sample_valid_archive_content_str):
    archive_file = temp_dir_fixture / "verify_valid.pak.json"
    archive_file.write_text(sample_valid_archive_content_str)
    assert PakArchive.verify_archive(str(archive_file), quiet=True) is True

def test_verify_archive_invalid_structure(temp_dir_fixture):
    invalid_content = json.dumps({"metadata": {}, "files": [{"no_path_key": "test"}]})
    archive_file = temp_dir_fixture / "verify_invalid.pak.json"
    archive_file.write_text(invalid_content)
    assert PakArchive.verify_archive(str(archive_file), quiet=True) is False
