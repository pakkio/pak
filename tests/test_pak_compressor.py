import pytest
import json
from unittest.mock import patch, MagicMock
from pak_compressor import Compressor, LanguageAwareTokenizer, CacheManager, SemanticCompressor as InternalSemanticCompressor

# Backward compatibility alias for tests
TokenCounter = LanguageAwareTokenizer

# Fixtures for sample content are in conftest.py

@pytest.fixture
def compressor_instance(temp_dir_fixture):
    cache_mgr = CacheManager(archive_path_or_id=str(temp_dir_fixture / "test_cache.json"), quiet=True)
    return Compressor(cache_manager=cache_mgr, quiet=True)

def test_token_counter_empty():
    assert TokenCounter.count_tokens("") == 0

def test_token_counter_code(sample_python_code_str):
    # Language-aware tokenizer should be more accurate than simple 3:1 heuristic
    tokens = TokenCounter.count_tokens(sample_python_code_str, "python")
    old_method_tokens = len(sample_python_code_str) // 3
    assert tokens > 5  # Should produce reasonable token count
    assert tokens < old_method_tokens  # Should be more efficient than old method

def test_token_counter_text(sample_text_content_str):
    assert TokenCounter.count_tokens(sample_text_content_str, "text") > 5

def test_cache_manager_get_miss_and_hit(temp_dir_fixture):
    cache_file = temp_dir_fixture / "mycache.json"
    cache_mgr = CacheManager(str(cache_file), quiet=True)
    content = "test content"
    level = "light"

    assert cache_mgr.get_cached_compression(content, level) is None # Miss

    result_data = {"compressed_content": "test compressed", "method": "light (cached test)"}
    cache_mgr.cache_compression(content, level, result_data)
    cache_mgr.save_cache() # Explicit save

    # New instance to load from file
    cache_mgr_new = CacheManager(str(cache_file), quiet=True)
    cached_result = cache_mgr_new.get_cached_compression(content, level)
    assert cached_result is not None
    assert cached_result["compressed_content"] == "test compressed"

def test_compress_none(compressor_instance, sample_text_content_str):
    result = compressor_instance.compress_content(sample_text_content_str, "file.txt", "none")
    assert result["compressed_content"] == sample_text_content_str
    assert result["method"] == "none (raw)"
    assert result["compression_ratio"] == 1.0

def test_compress_light(compressor_instance, sample_text_content_str):
    result = compressor_instance.compress_content(sample_text_content_str, "file.txt", "light")
    assert "Trailing spaces here." in result["compressed_content"] # Text content preserved
    assert "here.   " not in result["compressed_content"]  # Trailing spaces removed  
    assert "\n\n\n" not in result["compressed_content"] # Multiple blanks collapsed
    assert result["method"] == "light (whitespace norm.)"
    assert result["original_size"] > result["compressed_size"]

def test_compress_medium_python(compressor_instance, sample_python_code_str):
    result = compressor_instance.compress_content(sample_python_code_str, "file.py", "medium")
    assert "# This is a comment" not in result["compressed_content"]
    assert "'''Docstring for MyClass.'''" not in result["compressed_content"] # Basic medium removes docstrings too
    assert "def greet" in result["compressed_content"] # Code preserved
    assert result["method"] == "medium (comments/blanks removed)"

def test_compress_aggressive_python(compressor_instance, sample_python_code_str):
    result = compressor_instance.compress_content(sample_python_code_str, "file.py", "aggressive")
    assert result["method"] == "aggressive (py-ast)"
    assert result["compressed_content"].startswith("# PYTHON AST STRUCTURE (Aggressive)")
    try:
        json_part = result["compressed_content"].split("\n", 1)[1]
        data = json.loads(json_part)
        assert "imports" in data
        assert "classes" in data
    except (IndexError, json.JSONDecodeError) as e:
        pytest.fail(f"Aggressive compression for Python did not produce valid JSON structure: {e}")

def test_compress_aggressive_non_python_fallback(compressor_instance, sample_text_content_str):
    result = compressor_instance.compress_content(sample_text_content_str, "file.txt", "aggressive")
    # Falls back to medium for non-python
    assert result["method"] == "medium (comments/blanks removed)"


@patch.object(InternalSemanticCompressor, '_call_llm_api', autospec=True)
def test_compress_semantic_success(mock_call_llm_api, compressor_instance, sample_python_code_str):
    # Ensure SEMANTIC_AVAILABLE is true for this test path, or mock SemanticCompressor init
    if not compressor_instance.semantic_compressor:
        compressor_instance.semantic_compressor = InternalSemanticCompressor(quiet=True)
        # If the SemanticCompressor in Compressor is only created if SEMANTIC_AVAILABLE,
        # we might need to patch SEMANTIC_AVAILABLE to True for this test.
        # For simplicity, we assume it gets created or we mock its presence.

    # Mock the behavior of _call_llm_api inside the internal SemanticCompressor
    mock_semantic_json_output = {
        "file_path": "file.py", "file_type": "python",
        "overall_purpose": "Test purpose",
        "key_components": {"imports_dependencies": [], "classes": [], "functions_methods": [], "data_structures": [], "configuration": []},
        "core_logic_flow": "Test flow",
        "critical_reconstruction_details": "None",
        "external_interactions": []
    }
    mock_call_llm_api.return_value = json.dumps(mock_semantic_json_output)

    # Temporarily ensure API key is set for SemanticCompressor internal check
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "fake_key_for_test"}):
        result = compressor_instance.compress_content(sample_python_code_str, "file.py", "semantic")

    assert result["method"] == "semantic-llm"
    assert "# SEMANTIC COMPRESSION v1.1" in result["compressed_content"]
    assert json.dumps(mock_semantic_json_output, indent=2) in result["compressed_content"]
    mock_call_llm_api.assert_called_once()


@patch.object(InternalSemanticCompressor, '_call_llm_api', autospec=True)
def test_compress_semantic_llm_failure_fallback(mock_call_llm_api, compressor_instance, sample_python_code_str):
    if not compressor_instance.semantic_compressor: # Ensure it exists for mocking
        compressor_instance.semantic_compressor = InternalSemanticCompressor(quiet=True)

    mock_call_llm_api.side_effect = Exception("LLM API Error")

    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "fake_key_for_test"}):
        result = compressor_instance.compress_content(sample_python_code_str, "file.py", "semantic")

    assert "semantic-llm-failed, fallback to aggressive (py-ast)" in result["method"]
    assert result["compressed_content"].startswith("# PYTHON AST STRUCTURE (Aggressive)")


@patch.object(InternalSemanticCompressor, '_call_llm_api')
def test_compress_smart_chooses_semantic(mock_call_llm_api_semantic, compressor_instance, sample_python_code_str):
    if not compressor_instance.semantic_compressor:
        compressor_instance.semantic_compressor = InternalSemanticCompressor(quiet=True)

    mock_semantic_json_output = {
        "file_path": "file.py", "file_type": "python", "overall_purpose": "Smart test",
        "key_components": {}, "core_logic_flow": "Flow",
        "critical_reconstruction_details": "", "external_interactions": []
    }
    mock_call_llm_api_semantic.return_value = json.dumps(mock_semantic_json_output)

    # Make content large enough to likely trigger semantic in smart mode
    large_code_content = sample_python_code_str * 5

    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "fake_key_for_test"}):
        result = compressor_instance.compress_content(large_code_content, "file.py", "smart")

    assert "smart->semantic-llm" in result["method"]
    mock_call_llm_api_semantic.assert_called_once()


def test_compress_smart_fallback_to_aggressive(compressor_instance, sample_python_code_str):
    # Make content large, but simulate semantic failure by temporarily removing semantic_compressor
    original_semantic_compressor = compressor_instance.semantic_compressor
    compressor_instance.semantic_compressor = None # Simulate semantic not available

    large_code_content = sample_python_code_str * 20 # Ensure it's large

    result = compressor_instance.compress_content(large_code_content, "file.py", "smart")

    assert "smart->aggressive (py-ast)" in result["method"]
    compressor_instance.semantic_compressor = original_semantic_compressor # Restore


def test_compress_content_with_caching(compressor_instance, sample_text_content_str):
    # First call - should not be cached
    result1 = compressor_instance.compress_content(sample_text_content_str, "cached_file.txt", "light")

    # Second call - should hit cache
    # Mock the get_cached_compression to check if it's called and returns our expected result
    with patch.object(compressor_instance.cache_manager, 'get_cached_compression', return_value=result1) as mock_get_cache:
        result2 = compressor_instance.compress_content(sample_text_content_str, "cached_file.txt", "light")
        mock_get_cache.assert_called_once_with(sample_text_content_str, "light", None)
        assert result2["method"] == result1["method"] + " (cached)" # CacheManager adds "(cached)"
        assert result2["compressed_content"] == result1["compressed_content"]
