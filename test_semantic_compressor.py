#!/usr/bin/env python3
"""
Fake semantic compressor for testing cache functionality
Does NOT call real LLM APIs - just simulates compression
"""
import sys
import hashlib
import time

def fake_semantic_compression(content, filename, language):
    """Simulate semantic compression with fake delay"""
    # Simulate API delay
    time.sleep(0.5)  # Mezzo secondo per simulare LLM call
    
    # Create a fake but deterministic "semantic" result
    content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
    
    fake_result = f"""# SEMANTIC COMPRESSION v1.0
{{
  "purpose": "Fake semantic compression for {filename}",
  "components": {{
    "functions": ["function_detected"],
    "classes": ["class_detected"], 
    "constants": []
  }},
  "logic": "Simulated logic for testing cache (hash: {content_hash})",
  "deps": [],
  "reconstruct": "Fake reconstruction info"
}}
# END SEMANTIC COMPRESSION"""
    
    return fake_result

def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <file_path> <compression_level> <language>", file=sys.stderr)
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
            print("", end="")
            sys.exit(0)
        
        # Simulate semantic compression
        print(f"FAKE LLM: Processing {file_path} (size: {len(content)} bytes)", file=sys.stderr)
        compressed = fake_semantic_compression(content, file_path, language)
        print(compressed, end="")
        
    except FileNotFoundError:
        print(f"ERROR: File not found: {file_path}", file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(0)

if __name__ == "__main__":
    main()
