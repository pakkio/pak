import os
import sys
import json
import re
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional

# Import MultiLanguageAnalyzer from the sibling module
try:
    from pak_analyzer import MultiLanguageAnalyzer
except ImportError:
    # This fallback is for direct execution of this file, assuming pak_analyzer.py is in the same dir
    # For the main pak_core.py orchestrator, sys.path should be set up correctly.
    if __name__ == '__main__':
        sys.path.append(os.path.dirname(__file__)) # Add current dir to path if run directly
        from pak_analyzer import MultiLanguageAnalyzer
    else:
        raise # Re-raise if not main, as it implies a real import issue from orchestrator


# Try importing dependencies for semantic compression
try:
    import requests
    from dotenv import load_dotenv # To load .env file for API keys
    load_dotenv() # take environment variables from .env.
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False
    requests = None # Define requests as None if import fails

class TokenCounter:
    """Token counter using a simple heuristic: 3 chars = 1 token (tiktoken disabled)."""

    @staticmethod
    def count_tokens(content: str, file_type: str = "text") -> int:
        if not content:
            return 0
        # Simple heuristic: 3 characters = 1 token
        return max(1, len(content) // 3)

class CacheManager:
    """Manages SHA-256 based caching for semantic compression results."""
    def __init__(self, archive_path_or_id: str, quiet: bool = False):
        # Use a consistent cache directory, e.g., in user's cache or a subfolder
        # For simplicity here, let's assume cache is next to where script is run or related to archive
        # A more robust solution might use appdirs.user_cache_dir("pak_tool", "pak_author")
        cache_dir = Path(os.getenv("PAK_CACHE_DIR", Path.home() / ".cache" / "pak_tool_cache"))
        cache_dir.mkdir(parents=True, exist_ok=True)
        # Using a hash of archive_path_or_id for the cache filename to keep it cleaner
        # Or, if archive_path_or_id is simple, just use it.
        # This example uses a generic cache file for simplicity, but could be per-archive.
        self.cache_file = cache_dir / f"compression_cache.json"
        self.quiet = quiet
        self.cache: Dict[str, Any] = self._load_cache()

    def _log(self, message: str):
        if not self.quiet:
            print(f"CacheManager: {message}", file=sys.stderr)

    def _load_cache(self) -> Dict[str, Any]:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self._log(f"Loading cache from {self.cache_file}")
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self._log(f"Error loading cache file {self.cache_file}: {e}. Starting with empty cache.")
                return {}
        self._log("No cache file found. Starting with empty cache.")
        return {}

    def save_cache(self):
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2)
            self._log(f"Cache saved to {self.cache_file}")
        except IOError as e:
            self._log(f"Warning: Could not save cache to {self.cache_file}: {e}")

    def get_sha256(self, content: str) -> str:
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def get_cached_compression(self, content: str, compression_level: str, model_info: Optional[str] = None) -> Optional[Dict[str, Any]]:
        content_hash = self.get_sha256(content)
        cache_key = f"{content_hash}_{compression_level}"
        if model_info: # For semantic compression, model can influence output
            cache_key += f"_{model_info}"

        cached_item = self.cache.get(cache_key)
        if cached_item:
            self._log(f"Cache hit for key: {cache_key}")
            return cached_item
        self._log(f"Cache miss for key: {cache_key}")
        return None

    def cache_compression(self, content: str, compression_level: str, result: Dict[str, Any], model_info: Optional[str] = None):
        content_hash = self.get_sha256(content)
        cache_key = f"{content_hash}_{compression_level}"
        if model_info:
            cache_key += f"_{model_info}"

        self.cache[cache_key] = result
        self._log(f"Cached result for key: {cache_key}")
        # Consider saving cache immediately or deferring it (e.g., at end of main script)
        # For frequent operations, deferring might be better. Here, save is explicit.

class SemanticCompressor:
    """Handles LLM-based semantic compression."""
    def __init__(self, quiet: bool = False):
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.model_name = os.getenv('SEMANTIC_MODEL', "anthropic/claude-3-haiku-20240307") # Default model
        self.api_base_url = os.getenv('PAK_OPENROUTER_API_BASE', "https://openrouter.ai/api/v1")
        self.timeout = int(os.getenv('PAK_LLM_TIMEOUT', "60"))
        self.max_tokens_response = int(os.getenv('PAK_LLM_MAX_TOKENS', "2000"))
        self.temperature = float(os.getenv('PAK_LLM_TEMPERATURE', "0.1"))
        self.quiet = quiet

        if not self.api_key and not self.quiet:
            print("pak_compressor: Warning: OPENROUTER_API_KEY not found in environment. Semantic compression will fail.", file=sys.stderr)

    def _log(self, message: str, is_error: bool = False):
        if not self.quiet or is_error: # Always print errors
            level = "ERROR" if is_error else "INFO"
            print(f"SemanticCompressor ({level}): {message}", file=sys.stderr)

    def compress_content(self, content: str, file_path: str, file_type: str) -> Dict[str, Any]:
        if not SEMANTIC_AVAILABLE:
            self._log("Python 'requests' library not available. Cannot perform semantic compression.", is_error=True)
            raise Exception("Semantic compression dependencies not met (requests).")
        if not self.api_key:
            self._log("OPENROUTER_API_KEY not set. Cannot perform semantic compression.", is_error=True)
            raise Exception("OPENROUTER_API_KEY missing for semantic compression.")

        prompt = self._build_compression_prompt(content, file_path, file_type)
        try:
            llm_response_text = self._call_llm_api(prompt)
            parsed_json = self._parse_compression_response(llm_response_text, file_path)
            return parsed_json # This is the JSON data, not the final string for the archive
        except Exception as e:
            self._log(f"Semantic compression failed for '{file_path}': {e}", is_error=True)
            raise # Re-raise to be handled by the main Compressor

    def _build_compression_prompt(self, content: str, file_path: str, file_type: str) -> str:
        # Truncate very long content to fit within reasonable prompt limits for the LLM
        # This is a basic truncation; smarter chunking might be needed for huge files.
        # Max prompt content length (heuristic, depends on LLM context window)
        MAX_CONTENT_PROMPT_CHARS = 20000
        if len(content) > MAX_CONTENT_PROMPT_CHARS:
            self._log(f"Content for '{file_path}' is very long ({len(content)} chars), truncating for LLM prompt.")
            content = content[:MAX_CONTENT_PROMPT_CHARS] + "\n... (content truncated for brevity) ..."

        return f"""# SEMANTIC COMPRESSION TASK
You are an expert code analyst. Your task is to compress the following file content into a structured JSON object.
The JSON should capture the essence of the file, its purpose, key components, logic flow, and any critical details needed for a knowledgeable developer to reconstruct a functionally similar file. Be concise yet comprehensive.

FILE INFORMATION:
- Path: {file_path}
- Type: {file_type}
- Size (original): {len(content.encode('utf-8'))} bytes

CONTENT TO ANALYZE:
---BEGIN CONTENT---
{content}
---END CONTENT---

REQUIRED JSON OUTPUT STRUCTURE:
{{
  "file_path": "{file_path}",
  "file_type": "{file_type}",
  "overall_purpose": "A brief (1-2 sentences) description of what this file does or its main responsibility.",
  "key_components": {{
    "imports_dependencies": ["List key libraries or modules imported/depended upon, e.g., 'os', 'requests', './utils.js'"],
    "classes": [
      {{
        "name": "ClassName",
        "purpose": "Brief purpose of the class.",
        "key_methods": ["method1_signature: brief purpose", "method2_signature: brief purpose"],
        "key_attributes": ["attribute_name: brief description or type"]
      }}
    ],
    "functions_methods": [
      {{
        "name": "function_or_method_name (if not in a class above)",
        "signature": "Full signature if available (e.g., funcName(param1: type, param2: type) -> returnType)",
        "purpose": "Brief purpose of this function/method."
      }}
    ],
    "data_structures": ["Describe any significant global variables, constants, or complex data structures defined/used and their purpose."],
    "configuration": ["Mention any important configuration settings or parameters, possibly with default or example values."]
  }},
  "core_logic_flow": "Describe the main operational logic or workflow of the file in a few sentences. How do the components interact? What are the main steps it performs?",
  "critical_reconstruction_details": "List any specific algorithms, non-obvious implementation choices, formulas, or unique patterns that are essential for a developer to reconstruct the file's functionality. Focus on what is not easily inferred.",
  "external_interactions": ["Describe interactions with other files, services, APIs, or databases if any."]
}}

INSTRUCTIONS:
- Adhere strictly to the JSON structure provided.
- Ensure all string values are properly escaped for JSON.
- If a section (e.g., 'classes') is not applicable, provide an empty list `[]` or a null/empty string as appropriate for the field type.
- Be factual and derive information primarily from the provided content.
- The goal is semantic compression, not just a line-by-line summary. Extract the meaning and intent.
- Output ONLY the JSON object, without any surrounding text or markdown.
"""

    def _call_llm_api(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("PAK_HTTP_REFERER", "http://localhost/pak_tool"), # Optional: helps OpenRouter identify app
            "X-Title": os.getenv("PAK_X_TITLE", "PakTool Semantic Compressor"), # Optional
        }
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens_response,
            "temperature": self.temperature,
            "stream": False # Not streaming for this use case
        }

        self._log(f"Calling LLM API ({self.model_name}) for semantic compression...")
        response = requests.post(
            f"{self.api_base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)

        data = response.json()
        if not data.get("choices") or not data["choices"][0].get("message") or \
           not isinstance(data["choices"][0]["message"].get("content"), str):
            self._log(f"LLM API response missing expected content structure. Data: {data}", is_error=True)
            raise ValueError("Invalid LLM API response structure")

        self._log("LLM API call successful.")
        return data["choices"][0]["message"]["content"].strip()

    def _parse_compression_response(self, llm_response_text: str, file_path_for_log: str) -> Dict[str, Any]:
        json_str = llm_response_text
        # Attempt to strip markdown code block fences if present
    
        if json_str.startswith("```json"):
            json_str = json_str[len("```json"):].strip()
            if json_str.endswith("```"):
                json_str = json_str[:-len("```")].strip()
        elif json_str.startswith("```"): # If just ``` without 'json'
             json_str = json_str[len("```"):].strip()
             if json_str.endswith("```"):
                json_str = json_str[:-len("```")].strip()


        # Sometimes LLMs might add a brief preamble before the JSON. Try to find the start.
        if not json_str.startswith('{'):
            brace_pos = json_str.find('{')
            if brace_pos != -1:
                # And ensure it's a plausible JSON object by finding the matching last brace
                # This is a heuristic and might not be perfect for nested objects in preamble
                if json_str.rfind('}') > brace_pos:
                    json_str = json_str[brace_pos : json_str.rfind('}')+1]
            else:
                self._log(f"LLM response for '{file_path_for_log}' does not appear to start with a JSON object. Response prefix: {json_str[:200]}", is_error=True)
                raise ValueError("LLM response is not valid JSON (no starting '{').")
        try:
            parsed_data = json.loads(json_str)
            # Basic validation of top-level keys expected from the prompt
            expected_keys = ["file_path", "file_type", "overall_purpose", "key_components", "core_logic_flow"]
            for key in expected_keys:
                if key not in parsed_data:
                    self._log(f"Warning: LLM response for '{file_path_for_log}' missing expected key '{key}'. Using default.", is_error=False)
                    # Provide sensible defaults if keys are missing
                    if key == "key_components": parsed_data[key] = {}
                    else: parsed_data[key] = "" if key != "file_path" and key != "file_type" else file_path_for_log

            # Ensure key_components sub-keys exist
            if isinstance(parsed_data.get("key_components"), dict):
                expected_comp_keys = ["imports_dependencies", "classes", "functions_methods", "data_structures", "configuration"]
                for comp_key in expected_comp_keys:
                    if comp_key not in parsed_data["key_components"]: # type: ignore
                        parsed_data["key_components"][comp_key] = [] if comp_key in ["imports_dependencies", "classes", "functions_methods"] else "" # type: ignore


            self._log(f"Successfully parsed semantic compression JSON for '{file_path_for_log}'.")
            return parsed_data
        except json.JSONDecodeError as e:
            self._log(f"JSON decoding failed for '{file_path_for_log}': {e}. Response excerpt: {json_str[:500]}...", is_error=True)
            raise ValueError(f"Invalid JSON in LLM response: {e}")


class Compressor:
    """Handles various compression levels by delegating or performing them."""
    def __init__(self, cache_manager: Optional[CacheManager] = None, quiet: bool = False):
        self.cache_manager = cache_manager
        self.semantic_compressor = SemanticCompressor(quiet=quiet) if SEMANTIC_AVAILABLE else None
        self.quiet = quiet
        # Model info for caching semantic results, could be more dynamic
        self.semantic_model_info = self.semantic_compressor.model_name if self.semantic_compressor else "default_semantic_model"


    def _log(self, message: str, is_error: bool = False):
        if not self.quiet or is_error:
            level = "ERROR" if is_error else "INFO"
            print(f"Compressor ({level}): {message}", file=sys.stderr)

    def _detect_file_type(self, file_path: str) -> str:
        # This is a simplified version. A more robust one might use `python-magic` or more mimetypes.
        ext = Path(file_path).suffix.lower()
        type_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.java': 'java',
            '.c': 'c', '.h': 'c_header', '.cpp': 'cpp', '.hpp': 'cpp_header',
            '.cs': 'csharp', '.go': 'go', '.rs': 'rust', '.rb': 'ruby', '.php': 'php',
            '.md': 'markdown', '.txt': 'text', '.json': 'json', '.xml': 'xml', '.html': 'html',
            '.css': 'css', '.sh': 'shell', '.yaml': 'yaml', '.yml': 'yaml', '.toml': 'toml',
            # Add more types as needed
        }
        name = Path(file_path).name.lower()
        if name == "dockerfile": return "dockerfile"
        if name == "makefile": return "makefile"
        return type_map.get(ext, 'text') # Default to 'text'

    def compress_content(self, content: str, file_path: str, compression_level: str) -> Dict[str, Any]:
        original_size_bytes = len(content.encode('utf-8'))
        file_type = self._detect_file_type(file_path)

        if not content.strip() and compression_level != "none":
            return {
                "compressed_content": "", "original_size": original_size_bytes,
                "compressed_size": 0, "compressed_tokens": 0, "estimated_tokens": 0,
                "compression_ratio": 1.0, "method": "skip (empty/whitespace)"
            }

        cached_result = None
        if self.cache_manager:
            model_info_for_cache = self.semantic_model_info if compression_level in ["4", "semantic", "s", "smart"] else None
            cached_result = self.cache_manager.get_cached_compression(content, compression_level, model_info_for_cache)

        if cached_result:
            self._log(f"Using cached result for {file_path} (level {compression_level})")
            # Ensure essential keys are present, calculate if missing
            cached_result.setdefault("original_size", original_size_bytes)
            cached_result.setdefault("compressed_content", content if compression_level == "none" else "")
            cc = cached_result["compressed_content"]
            cs = len(cc.encode('utf-8'))
            cached_result.setdefault("compressed_size", cs)
            cached_result.setdefault("compressed_tokens", TokenCounter.count_tokens(cc, file_type))
            cached_result.setdefault("estimated_tokens", cached_result.get("compressed_tokens", 0))  # Add estimated_tokens alias
            cached_result.setdefault("compression_ratio", original_size_bytes / cs if cs > 0 else (1.0 if original_size_bytes == 0 else float('inf')))
            cached_result["method"] += " (cached)"
            return cached_result

        result: Dict[str, Any] = {}
        if compression_level in ["4", "semantic"]:
            result = self._compress_semantic(content, file_path, file_type)
        elif compression_level in ["s", "smart"]:
            result = self._compress_smart(content, file_path, file_type, original_size_bytes)
        elif compression_level in ["3", "aggressive"]:
            result = self._compress_aggressive(content, file_path, file_type)
        elif compression_level in ["2", "medium"]:
            result = self._compress_medium(content, file_path, file_type)
        elif compression_level in ["1", "light"]:
            result = self._compress_light(content, file_path, file_type)
        else: # "0", "none", or unknown defaults to none
            result = self._compress_none(content)

        result["original_size"] = original_size_bytes
        compressed_content_str = result.get("compressed_content", "")
        result["compressed_size"] = len(compressed_content_str.encode('utf-8'))
        result["compressed_tokens"] = TokenCounter.count_tokens(compressed_content_str, file_type)
        result["estimated_tokens"] = result["compressed_tokens"]  # Add estimated_tokens alias

        if result["compressed_size"] > 0:
            result["compression_ratio"] = original_size_bytes / result["compressed_size"]
        else: # Handle empty compressed content
            result["compression_ratio"] = 1.0 if original_size_bytes == 0 else float('inf')

        if self.cache_manager:
            model_info_for_cache = self.semantic_model_info if compression_level in ["4", "semantic", "s", "smart"] else None
            self.cache_manager.cache_compression(content, compression_level, result, model_info_for_cache)

        return result

    def _compress_semantic(self, content: str, file_path: str, file_type: str) -> Dict[str, Any]:
        method_desc = "semantic-llm"
        if not self.semantic_compressor:
            self._log("Semantic compressor not initialized. Falling back to aggressive.", is_error=True)
            fallback_res = self._compress_aggressive(content, file_path, file_type)
            fallback_res["method"] = f"{method_desc}-unavailable, fallback to {fallback_res['method']}"
            return fallback_res
        try:
            # SemanticCompressor.compress_content returns the structured JSON data
            semantic_data_json = self.semantic_compressor.compress_content(content, file_path, file_type)

            # Format this JSON data into the string that will be stored in the archive
            # This string includes headers for context.
            final_compressed_str = f"# SEMANTIC COMPRESSION v1.1 (pak_compressor.py)\n"
            final_compressed_str += f"# Original: {os.path.basename(file_path)} ({len(content.encode('utf-8'))} bytes, {file_type})\n"
            final_compressed_str += f"# Model: {self.semantic_compressor.model_name}\n"
            final_compressed_str += json.dumps(semantic_data_json, indent=2)

            return {"compressed_content": final_compressed_str, "method": method_desc}
        except Exception as e:
            self._log(f"Semantic compression for '{file_path}' failed: {e}. Falling back.", is_error=True)
            fallback_res = self._compress_aggressive(content, file_path, file_type) # Fallback to aggressive
            fallback_res["method"] = f"{method_desc}-failed, fallback to {fallback_res['method']}"
            return fallback_res

    def _compress_smart(self, content: str, file_path: str, file_type: str, original_size_bytes: int) -> Dict[str, Any]:
        self._log(f"Smart compression for {file_path} (type: {file_type}, size: {original_size_bytes}B)")
        # Heuristic: prioritize semantic for code files over a certain size, or very small text files
        is_code = file_type in ['python', 'javascript', 'typescript', 'java', 'c', 'cpp', 'go', 'rust']

        if is_code and original_size_bytes > 256: # Threshold for attempting semantic on code
            self._log(f"Attempting semantic for code file: {file_path}")
            semantic_result = self._compress_semantic(content, file_path, file_type)
            # Check if semantic compression was effective (e.g., ratio > 1.5 or method doesn't indicate failure)
            # Note: compression_ratio is calculated *after* this call by the main compress_content
            # So we look at the method string or estimate here.
            final_semantic_size = len(semantic_result.get("compressed_content", "").encode('utf-8'))
            semantic_ratio = original_size_bytes / final_semantic_size if final_semantic_size > 0 else 1.0

            if "failed" not in semantic_result["method"].lower() and semantic_ratio > 1.2:
                semantic_result["method"] = f"smart->{semantic_result['method']}"
                return semantic_result
            else:
                self._log(f"Semantic part of smart compression for {file_path} was ineffective (ratio {semantic_ratio:.1f}) or failed. Falling back.")
                # Fallback logic based on original size if semantic wasn't good
                if original_size_bytes > 10000: return self._add_method_prefix(self._compress_aggressive(content, file_path, file_type), "smart->")
                elif original_size_bytes > 1000: return self._add_method_prefix(self._compress_medium(content, file_path, file_type), "smart->")
                else: return self._add_method_prefix(self._compress_light(content, file_path, file_type), "smart->")

        # Fallback for non-code or small code files
        if original_size_bytes > 5000: return self._add_method_prefix(self._compress_aggressive(content, file_path, file_type), "smart->")
        if original_size_bytes > 500: return self._add_method_prefix(self._compress_medium(content, file_path, file_type), "smart->")
        return self._add_method_prefix(self._compress_light(content, file_path, file_type), "smart->")

    def _add_method_prefix(self, result_dict: Dict[str, Any], prefix: str) -> Dict[str, Any]:
        result_dict["method"] = prefix + result_dict.get("method", "unknown")
        return result_dict

    def _compress_aggressive(self, content: str, file_path: str, file_type: str) -> Dict[str, Any]:
        try:
            # Use MultiLanguageAnalyzer for both Python and other languages
            compressed_content = MultiLanguageAnalyzer.compress_with_ast(content, file_type, "aggressive")
            
            # If compression succeeded (content changed), return it
            if compressed_content != content:
                return {
                    "compressed_content": compressed_content, 
                    "method": f"aggressive ({file_type}-ast)"
                }
            else:
                # AST compression failed or unavailable, fall back to medium
                self._log(f"AST compression unavailable for {file_type} in {file_path}. Falling back to medium.")
                return self._compress_medium(content, file_path, file_type)
                
        except Exception as e:
            self._log(f"Unexpected error during AST compression for {file_path}: {e}. Falling back to medium.", is_error=True)
            return self._compress_medium(content, file_path, file_type)

    def _remove_comments_and_empty_lines(self, text_content: str, file_type: str) -> str:
        # This is a very basic heuristic and might incorrectly remove things.
        # A robust solution would use a proper parser for each language (e.g., tree-sitter).
        lines = text_content.splitlines()
        processed_lines = []

        # Language specific comment markers (simplified)
        single_line_markers = {"python": "#", "javascript": "//", "java": "//", "c": "//", "cpp": "//", "go": "//", "rust": "//", "shell": "#"}
        # Multi-line not handled by this simple version to avoid complexity.

        marker = single_line_markers.get(file_type)

        for line in lines:
            stripped_line = line.strip()
            if not stripped_line: # Skip empty lines
                continue
            if marker:
                # Be careful not to remove markers inside strings, e.g. print("# Not a comment")
                # This simple check looks if the line *starts* with the marker after stripping.
                if stripped_line.startswith(marker):
                    continue
                # For inline comments, it's harder. This might remove valid code if marker appears mid-string.
                # A slightly safer approach for inline (but still not perfect):
                comment_start_idx = line.find(marker)
                if comment_start_idx != -1:
                    # Crude check: if no quote before the marker on the line or an even number of quotes
                    # This is highly unreliable for complex strings.
                    slicer = line[:comment_start_idx]
                    if slicer.count('"') % 2 == 0 and slicer.count("'") % 2 == 0:
                        line_content_only = line[:comment_start_idx].rstrip()
                        if line_content_only: # Keep line if content before comment
                           processed_lines.append(line_content_only)
                        continue # Skip line if only comment or whitespace before it
            processed_lines.append(line) # Keep line if no comment processing applied or passed

        return "\n".join(processed_lines)


    def _compress_medium(self, content: str, file_path: str, file_type: str) -> Dict[str, Any]:
        # More careful comment and empty line removal
        cleaned_content = self._remove_comments_and_empty_lines(content, file_type)
        return {"compressed_content": cleaned_content, "method": "medium (comments/blanks removed)"}

    def _compress_light(self, content: str, file_path: str, file_type: str) -> Dict[str, Any]:
        lines = content.splitlines()
        processed_lines = []
        last_was_blank = False
        for line in lines:
            stripped = line.rstrip() # Remove trailing whitespace only
            if not stripped.strip(): # Line is effectively blank
                if not last_was_blank:
                    processed_lines.append("") # Add one blank line
                last_was_blank = True
            else:
                processed_lines.append(stripped)
                last_was_blank = False
        final_content = "\n".join(processed_lines).strip('\n') # Remove leading/trailing blank lines from the whole content
        return {"compressed_content": final_content, "method": "light (whitespace norm.)"}

    def _compress_none(self, content: str) -> Dict[str, Any]:
        return {"compressed_content": content, "method": "none (raw)"}


if __name__ == '__main__':
    # Example Usage (for testing this module directly)
    print("pak_compressor.py - Direct Execution Test")

    # Setup a dummy cache manager for testing
    # Note: For real use, CacheManager is typically initialized by the orchestrator (pak_core.py)
    # with a path related to the archive being created/processed.
    # Here, we use a generic name for a test cache.
    test_cache_archive_id = "test_compressor_cache"
    cache_mgr_test = CacheManager(test_cache_archive_id, quiet=False) # Not quiet for testing

    compressor_test = Compressor(cache_manager=cache_mgr_test, quiet=False)

    sample_py_code = """
# This is a comment
import os

def hello(name): # Another comment
    '''Docstring'''
    message = f"Hello, {name}!" # Inline comment test
    print(message)
    # Final comment

"""
    sample_text_content = """
This is a line.

This is another line after a blank.

    Indented line.
Trailing spaces here.

Final line.

"""
    # Test different compression levels
    levels_to_test = ["none", "light", "medium", "aggressive", "semantic", "smart"]

    print("\n--- Testing Python Code Compression ---")
    for level in levels_to_test:
        print(f"\n--- Level: {level} ---")
        if level == "semantic" and (not SEMANTIC_AVAILABLE or not os.getenv("OPENROUTER_API_KEY")):
            print(f"Skipping semantic test: Not available or API key missing.")
            continue
        if level == "smart" and (not SEMANTIC_AVAILABLE or not os.getenv("OPENROUTER_API_KEY")):
            print(f"Skipping smart test (semantic part): Not available or API key missing.")
            # Test smart without semantic by temporarily disabling semantic_compressor
            # This is a bit hacky for a direct test; in real use, smart adapts.
            original_semantic_compressor = compressor_test.semantic_compressor
            compressor_test.semantic_compressor = None
            result = compressor_test.compress_content(sample_py_code, "sample.py", level)
            compressor_test.semantic_compressor = original_semantic_compressor # Restore
        else:
            result = compressor_test.compress_content(sample_py_code, "sample.py", level)

        print(f"Method: {result['method']}")
        print(f"Original Size: {result['original_size']}, Compressed Size: {result['compressed_size']}")
        print(f"Tokens: {result['compressed_tokens']}, Ratio: {result['compression_ratio']:.2f}x")
        print("Compressed Content:")
        print("vvv")
        print(result['compressed_content'])
        print("^^^")

    print("\n--- Testing Text File Compression ---")
    for level in ["none", "light", "medium"]: # Aggressive/Semantic less relevant for plain text usually
        print(f"\n--- Level: {level} ---")
        result = compressor_test.compress_content(sample_text_content, "sample.txt", level)
        print(f"Method: {result['method']}")
        print(f"Original Size: {result['original_size']}, Compressed Size: {result['compressed_size']}")
        print(f"Tokens: {result['compressed_tokens']}, Ratio: {result['compression_ratio']:.2f}x")
        print("Compressed Content:")
        print("vvv")
        print(result['compressed_content'])
        print("^^^")

    # Explicitly save cache after tests
    if cache_mgr_test:
        cache_mgr_test.save_cache()
