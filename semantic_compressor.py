"""
Semantic Compressor for Pak4
Uses LLM to create detailed semantic descriptions of code files
that enable reconstruction while dramatically reducing token count.
MODIFIED: Now ALWAYS applies semantic compression when possible.
"""
import sys
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from llm_wrapper import llm_call
except ImportError:
    print("ERROR: llm_wrapper.py not found. Please ensure it's in the same directory.", file=sys.stderr)
    sys.exit(1)

SEMANTIC_PROMPT_TEMPLATE = """You are a code analysis expert. Create a CONCISE semantic description for reconstruction.

File: {filename} ({size} bytes, {language})

Code:
```{language}
{content}
```

Return ONLY valid JSON (no markdown blocks). Be concise but complete:
{{
    "purpose": "Brief 1-sentence description",
    "components": {{
        "functions": ["func1(args): brief purpose", "func2(args): brief purpose"],
        "classes": ["Class1: brief purpose"],
        "constants": ["CONST1: value"]
    }},
    "logic": "Key algorithm/flow in 1-2 sentences",
    "deps": ["lib1", "lib2"],
    "reconstruct": "Critical implementation details for rebuilding"
}}"""

def compress_file_semantically(file_path: str, language: str, content: str) -> tuple[str, str]:
    """
    Compress a file using LLM semantic analysis.
    Returns (compressed_content, method_description)
    MODIFIED: Now always applies semantic compression, no size/type restrictions.
    """
    filename = Path(file_path).name
    size = len(content.encode('utf-8'))

    # REMOVED: Size check (< 200 bytes)
    # REMOVED: Data file type exclusions

    # Only skip completely empty files
    if not content.strip():
        return content, "semantic-skip (empty)"

    try:
        prompt = SEMANTIC_PROMPT_TEMPLATE.format(
            language=language,
            filename=filename,
            size=size,
            content=content
        )

        messages = [{"role": "user", "content": prompt}]
        semantic_desc, success = llm_call(messages)

        if os.environ.get("PAK_DEBUG") == "true":
            print(f"\n=== SEMANTIC DEBUG: {filename} ===", file=sys.stderr)
            print(f"LLM Success: {success}", file=sys.stderr)
            print(f"Original content length: {len(content)} chars", file=sys.stderr)
            print(f"LLM response length: {len(semantic_desc)} chars", file=sys.stderr)
            print(f"LLM response starts with: {semantic_desc[:150]}...", file=sys.stderr)
            if not success:
                print(f"LLM call failed!", file=sys.stderr)
            print("=== END DEBUG ===\n", file=sys.stderr)

        if not success:
            logging.warning(f"LLM call failed for {filename}, falling back to original")
            return content, "semantic-fallback (LLM failed)"

        try:
            # Clean up JSON response (remove markdown blocks if present)
            json_content = semantic_desc.strip()
            if json_content.startswith('```json'):
                lines = json_content.split('\n')
                start_idx = 0
                end_idx = len(lines)
                for i, line in enumerate(lines):
                    if line.strip() == '```json':
                        start_idx = i + 1
                    elif line.strip() == '```' and i > start_idx:
                        end_idx = i
                        break
                json_content = '\n'.join(lines[start_idx:end_idx]).strip()
            elif json_content.startswith('```'):
                lines = json_content.split('\n')
                if len(lines) > 2:
                    json_content = '\n'.join(lines[1:-1]).strip()

            # Validate JSON structure
            parsed = json.loads(json_content)
            required_fields = ["purpose", "components"]
            if not all(field in parsed for field in required_fields):
                missing = [f for f in required_fields if f not in parsed]
                raise ValueError(f"Missing required fields: {missing}")

        except (json.JSONDecodeError, ValueError) as e:
            logging.warning(f"Invalid JSON response for {filename}: {e}")
            if os.environ.get("PAK_DEBUG") == "true":
                print(f"DEBUG: Failed to parse JSON. Content was: {semantic_desc[:500]}...", file=sys.stderr)
            return content, "semantic-fallback (invalid JSON)"

        # Create compressed format with semantic description
        compressed = f"""# SEMANTIC COMPRESSION v1.0
# Original: {filename} ({size} bytes, {language})
{semantic_desc}
# END SEMANTIC COMPRESSION"""

        # MODIFIED: Always return semantic compression, regardless of compression ratio
        semantic_compression_ratio = len(content) / len(semantic_desc)
        return compressed, f"semantic-llm ({semantic_compression_ratio:.1f}x ratio, always-applied)"

    except Exception as e:
        logging.error(f"Semantic compression failed for {filename}: {e}")
        return content, f"semantic-error ({str(e)})"

def decompress_semantic_file(compressed_content: str) -> Optional[str]:
    """
    Extract semantic description from compressed file.
    This would be used by a reconstruction tool (not implemented here).
    """
    if not compressed_content.startswith("# SEMANTIC COMPRESSION"):
        return None

    lines = compressed_content.split('\n')
    start_idx = None
    end_idx = None

    for i, line in enumerate(lines):
        if line.startswith('# Original:'):
            start_idx = i + 1
        elif line.startswith('# END SEMANTIC COMPRESSION'):
            end_idx = i
            break

    if start_idx is None or end_idx is None:
        return None

    semantic_json = '\n'.join(lines[start_idx:end_idx]).strip()
    return semantic_json

def main():
    """CLI interface for semantic compression"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <file_path> <compression_level> <language>", file=sys.stderr)
        print("Note: compression_level should be 'semantic' for semantic compression", file=sys.stderr)
        sys.exit(2)

    file_path = sys.argv[1]
    level = sys.argv[2]
    language = sys.argv[3]

    if level != "semantic":
        print(f"ERROR: This tool only handles 'semantic' compression level, got '{level}'", file=sys.stderr)
        sys.exit(1)

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        if not content.strip():
            print("", end="")  # Empty file
            sys.exit(0)

        compressed, method = compress_file_semantically(file_path, language, content)
        print(compressed, end="")

        if os.environ.get("PAK_DEBUG") == "true":
            print(f"semantic_compressor: {file_path} -> {method}", file=sys.stderr)

    except FileNotFoundError:
        print(f"ERROR: File not found: {file_path}", file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        # Still try to output original content on error
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                print(f.read(), end="")
        except:
            pass
        sys.exit(0)  # Don't fail pak4 on compression errors

if __name__ == "__main__":
    main()