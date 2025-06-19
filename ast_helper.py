#!/usr/bin/env python3
import sys
import re # If needed for any text manipulation post-AST

try:
    from tree_sitter import Language, Parser
    import tree_sitter_languages # For pre-built languages
    # Import specific language grammars if needed directly
    import tree_sitter_python
except ImportError:
    # This error message will be visible on stderr if pak3 calls this script
    # and the libraries are missing.
    print("ast-helper-py: error: Required tree-sitter libraries not found. Please ensure py-tree-sitter, tree-sitter-languages, and tree-sitter-python are installed in the Python environment being used.", file=sys.stderr)
    sys.exit(1) # Indicate critical error to pak3

_AST_HELPER_LOG_PREFIX = 'ast-helper-py:'

def get_language_object(lang_name_short):
    """
    Tries to get a tree-sitter Language object based on the short name
    provided by pak3's detect_language function.
    """
    try:
        if lang_name_short == 'python':
            # Use the direct language object without wrapping in Language()
            return tree_sitter_python.language()
        elif lang_name_short in ['javascript', 'js']:
            return tree_sitter_languages.get_language('javascript')
        elif lang_name_short == 'typescript':
            return tree_sitter_languages.get_language('typescript')
        elif lang_name_short == 'java':
            return tree_sitter_languages.get_language('java')
        elif lang_name_short == 'rust':
            return tree_sitter_languages.get_language('rust')
        elif lang_name_short == 'c':
            return tree_sitter_languages.get_language('c')
        elif lang_name_short == 'cpp':
            return tree_sitter_languages.get_language('cpp')
        elif lang_name_short == 'go':
            return tree_sitter_languages.get_language('go')
        elif lang_name_short == 'ruby':
            return tree_sitter_languages.get_language('ruby')
        elif lang_name_short == 'php':
            return tree_sitter_languages.get_language('php')
        elif lang_name_short == 'csharp': # pak3 detect_language uses 'csharp'
            return tree_sitter_languages.get_language('c_sharp') # tree-sitter-languages uses 'c_sharp'
        # Add other supported languages here if you expand pak3's detect_language
        else:
            print(f"{_AST_HELPER_LOG_PREFIX} warn: Language '{lang_name_short}' not explicitly mapped in ast_helper.py's get_language_object.", file=sys.stderr)
            return None
    except Exception as e:
        print(f"{_AST_HELPER_LOG_PREFIX} error: Could not load tree-sitter language for '{lang_name_short}'. Error: {e}", file=sys.stderr)
        return None

def extract_api_only(tree, source_bytes):
    """
    Aggressive compression: Extracts API-level elements using tree-sitter. A full, robust implementation is provided here.
    """
    api_elements = []
    source_text = source_bytes.decode('utf8', errors='ignore') # For easier text slicing for headers

    # This recursive traversal is a general pattern.
    # Specific node types and text extraction logic will vary GREATLY per language.
    # The 'type' strings (e.g., "import_statement") depend on the tree-sitter grammar for that language.
    def traverse_node(node):
        node_type = node.type
        
        # Python-specific examples (adapt for other languages)
        if node_type in ["import_statement", "import_from_statement"]:
            api_elements.append(node.text.decode('utf8').strip())
        
        elif node_type == "class_definition":
            # Attempt to get the class header line (e.g., "class MyClass(Base):")
            # This is a heuristic and might need refinement based on actual grammar structure.
            # It finds the 'class' keyword, then the name, then optional base classes.
            # We are looking for the ':' character that typically ends the header.
            header_end_byte = node.end_byte # default to full node if ':' not found early
            for child in node.children:
                if child.type == ':': # This is specific to Python grammar
                    header_end_byte = child.end_byte
                    break
                if child.start_byte > node.start_byte + 200: # Safety break if ':' is too far
                    break 
            class_header = source_bytes[node.start_byte:header_end_byte].decode('utf-8', errors='ignore').splitlines()[0]
            api_elements.append(class_header.strip() + " ...")

        elif node_type == "function_definition":
            # Similar heuristic for function definitions.
            header_end_byte = node.end_byte
            for child in node.children:
                if child.type == ':': # Python specific
                    header_end_byte = child.end_byte
                    break
                if child.start_byte > node.start_byte + 300: # Safety break
                    break
            func_header = source_bytes[node.start_byte:header_end_byte].decode('utf-8', errors='ignore').splitlines()[0]
            api_elements.append(func_header.strip() + " ...")
        
        # Generic: Recurse into children
        for child in node.children:
            traverse_node(child)

    if tree and tree.root_node:
        traverse_node(tree.root_node)
    
    if not api_elements: # Fallback if AST traversal yielded nothing significant
        return source_text[:1000] + '\n# ... API extraction (stub, ast_helper.py - AST analysis yielded no specific elements)'

    # Add a blank line between groups of elements for readability if there are multiple imports vs. defs/classes
    # This is a simple heuristic.
    final_output = []
    last_was_import = False
    for elem in api_elements:
        current_is_import = elem.startswith("import ") or elem.startswith("from ")
        if final_output and not current_is_import and last_was_import:
            final_output.append("") # Add a separator
        final_output.append(elem)
        last_was_import = current_is_import
        
    return "\n".join(final_output) + "\n# ... (Structure extracted via AST - ast_helper.py)"

def extract_signatures_preview(tree, source_bytes):
    """
    Medium compression: Extracts signatures and a bit more context. (Stub)
    TODO: Implement AST traversal.
    """
    # Placeholder: Could be similar to extract_api_only but keep more of the body,
    # or keep first N lines of function/method bodies.
    return source_bytes.decode('utf8', errors='ignore')[:2000] + '\n# ... Signature preview (stub from ast_helper.py)'

def extract_clean_code(tree, source_bytes):
    """
    Light compression: Removes comments, potentially some whitespace. (Stub)
    TODO: Implement AST traversal to identify and exclude comment nodes.
    """
    # Placeholder: A real 'light' AST compression would traverse the tree,
    # identify comment nodes, and reconstruct the source without them.
    # This is non-trivial to do perfectly while preserving formatting of kept code.
    return source_bytes.decode('utf8', errors='ignore') + '\n# ... Cleaned code (stub from ast_helper.py, full content for now)'

def main():
    if len(sys.argv) != 4:
        print(f"{_AST_HELPER_LOG_PREFIX} usage_error: {sys.argv[0]} <file_path> <compression_level> <language_short_name>", file=sys.stderr)
        sys.exit(2) # Different exit code for usage error

    file_path = sys.argv[1]
    level = sys.argv[2]
    lang_short_name = sys.argv[3]
    output_content = ""

    try:
        with open(file_path, 'rb') as f:
            source_bytes = f.read()
        
        if not source_bytes and level != "none": # Handle empty files correctly
            print("", end="") 
            sys.exit(0)

        # If level is "none", just pass through the content
        if level == "none":
            print(source_bytes.decode('utf8', errors='ignore'), end="")
            sys.exit(0)

        language_obj = get_language_object(lang_short_name)
        if not language_obj:
            print(f"{_AST_HELPER_LOG_PREFIX} error: Failed to load tree-sitter language grammar for '{lang_short_name}' for file '{file_path}'. Falling back to raw content.", file=sys.stderr)
            print(source_bytes.decode('utf8', errors='ignore'), end="")
            sys.exit(0) # Graceful fallback to raw content for pak3 to capture

        parser = Parser()
        parser.set_language(language_obj)
        tree = parser.parse(source_bytes)

        if level == "aggressive":
            output_content = extract_api_only(tree, source_bytes)
        elif level == "medium":
            output_content = extract_signatures_preview(tree, source_bytes)
        elif level == "light":
            output_content = extract_clean_code(tree, source_bytes)
        else: 
            # Should have been caught by level == "none" already, but as a safeguard
            print(f"{_AST_HELPER_LOG_PREFIX} warn: Unknown compression level '{level}' for '{file_path}'. Using raw content.", file=sys.stderr)
            output_content = source_bytes.decode('utf8', errors='ignore')
        
        print(output_content, end="") # Print final processed content to stdout

    except FileNotFoundError:
        print(f"{_AST_HELPER_LOG_PREFIX} error: File not found '{file_path}'", file=sys.stderr)
        sys.exit(3) # Different exit code for file not found
    except Exception as e:
        print(f"{_AST_HELPER_LOG_PREFIX} error: Unexpected error processing '{file_path}' with lang '{lang_short_name}', level '{level}': {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        # Fallback to printing original content to stdout if any error occurs during AST processing
        # This allows pak3 to still capture *something* instead of an empty string on error.
        try:
            if 'source_bytes' in locals(): # Check if source_bytes was read
                print(source_bytes.decode('utf8', errors='ignore'), end="")
            else: # If source_bytes wasn't even read (e.g. very early error)
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f_fallback:
                    print(f_fallback.read(), end="")
        except Exception as fallback_e:
            print(f"{_AST_HELPER_LOG_PREFIX} error: Also failed to read fallback content for '{file_path}': {fallback_e}", file=sys.stderr)
            # If all else fails, print nothing to stdout for this file. pak3 will capture empty content.
        sys.exit(0) # Exit 0 so pak3 captures the (potentially raw) output rather than triggering shell's ||

if __name__ == "__main__":
    main()
