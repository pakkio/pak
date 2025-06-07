import pytest
from unittest.mock import patch, MagicMock
import os
import requests # Needed for requests.exceptions.RequestException

# Important: Assuming llm_wrapper.py is in the Python path
# (e.g., if tests are run from project root)
from llm_wrapper import llm_call, test_llm_connection

@pytest.fixture(autouse=True)
def manage_env_vars():
    # Set default env vars for tests, backup and restore original ones
    original_api_key = os.environ.get("OPENROUTER_API_KEY")
    original_model = os.environ.get("SEMANTIC_MODEL")

    os.environ["OPENROUTER_API_KEY"] = "test_api_key"
    os.environ["SEMANTIC_MODEL"] = "test_model/test_model_name"
    yield
    if original_api_key is None:
        del os.environ["OPENROUTER_API_KEY"]
    else:
        os.environ["OPENROUTER_API_KEY"] = original_api_key

    if original_model is None:
        if "SEMANTIC_MODEL" in os.environ: # Check if it was set by this fixture
             del os.environ["SEMANTIC_MODEL"]
    else:
        os.environ["SEMANTIC_MODEL"] = original_model


@patch('llm_wrapper.requests.post')
def test_llm_call_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Test response content"}}]
    }
    mock_post.return_value = mock_response

    messages = [{"role": "user", "content": "Test prompt"}]
    response_text, success = llm_call(messages)

    assert success is True
    assert response_text == "Test response content"
    mock_post.assert_called_once()
    call_args = mock_post.call_args[1] # keyword args
    assert call_args['json']['model'] == "test_model/test_model_name"


def test_llm_call_api_key_missing(manage_env_vars): # manage_env_vars to ensure clean state
    del os.environ["OPENROUTER_API_KEY"]
    messages = [{"role": "user", "content": "Test prompt"}]
    response_text, success = llm_call(messages)
    assert success is False
    assert "[ERROR: API key missing]" in response_text


@patch('llm_wrapper.requests.post')
def test_llm_call_http_error(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_post.return_value = mock_response

    messages = [{"role": "user", "content": "Test prompt"}]
    response_text, success = llm_call(messages)
    assert success is False
    assert "[ERROR: API 500]" in response_text

@patch('llm_wrapper.requests.post')
def test_llm_call_network_error(mock_post):
    mock_post.side_effect = requests.exceptions.RequestException("Network issue")
    messages = [{"role": "user", "content": "Test prompt"}]
    response_text, success = llm_call(messages)
    assert success is False
    assert "[ERROR: Network issue]" in response_text

@patch('llm_wrapper.llm_call')
def test_test_llm_connection_success(mock_llm_call):
    mock_llm_call.return_value = ("CONNECTION_OK", True)
    assert test_llm_connection() is True
    mock_llm_call.assert_called_once_with([{"role": "user", "content": "Reply with exactly: 'CONNECTION_OK'"}])

@patch('llm_wrapper.llm_call')
def test_test_llm_connection_failure_response(mock_llm_call):
    mock_llm_call.return_value = ("WRONG_RESPONSE", True)
    assert test_llm_connection() is False

@patch('llm_wrapper.llm_call')
def test_test_llm_connection_failure_call(mock_llm_call):
    mock_llm_call.return_value = ("Error", False)
    assert test_llm_connection() is False
