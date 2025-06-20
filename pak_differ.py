import os
import sys
from typing import List, Dict, Any, Optional

# Import PythonAnalyzer from the sibling module
try:
    from pak_analyzer import PythonAnalyzer
except ImportError:
    # Fallback for direct execution
    if __name__ == '__main__':
        sys.path.append(os.path.dirname(__file__))
        from pak_analyzer import PythonAnalyzer
    else:
        raise

class MethodDiffManager:
    """Manages method-level diff extraction and application."""

    @staticmethod
    def _log(message: str, quiet: bool, is_error: bool = False):
        if not quiet or is_error:
            level = "ERROR" if is_error else "INFO"
            print(f"MethodDiffManager ({level}): {message}", file=sys.stderr)

    @staticmethod
    def extract_diff(file_paths: List[str], quiet: bool = False) -> List[Dict[str, Any]]:
        """
        Extracts method diffs. The first file in file_paths is the base,
        subsequent files are compared against this base.
        """
        if len(file_paths) < 2:
            MethodDiffManager._log("Need at least 2 files for method diff (base_file, modified_file1, ...).", quiet, is_error=True)
            raise ValueError("Method diff extraction requires at least a base file and one modified file.")

        base_file_path = file_paths[0]
        modified_file_paths = file_paths[1:] # One or more modified files

        if not os.path.exists(base_file_path):
            MethodDiffManager._log(f"Base file not found: {base_file_path}", quiet, is_error=True)
            raise FileNotFoundError(f"Base file for diff not found: {base_file_path}")

        try:
            with open(base_file_path, 'r', encoding='utf-8') as f_base:
                base_content = f_base.read()
        except Exception as e:
            MethodDiffManager._log(f"Error reading base file {base_file_path}: {e}", quiet, is_error=True)
            raise

        all_diffs: List[Dict[str, Any]] = []

        for modified_file_path in modified_file_paths:
            if not os.path.exists(modified_file_path):
                MethodDiffManager._log(f"Modified file not found, skipping: {modified_file_path}", quiet)
                continue

            try:
                with open(modified_file_path, 'r', encoding='utf-8') as f_mod:
                    modified_content = f_mod.read()
            except Exception as e:
                MethodDiffManager._log(f"Error reading modified file {modified_file_path}: {e}", quiet, is_error=True)
                continue

            # Assuming Python files for now. This could be extended for other languages
            # if PythonAnalyzer supports them or a different analyzer is used.
            try:
                # PythonAnalyzer.compare_methods returns a list of diffs for this pair
                per_file_method_diffs = PythonAnalyzer.compare_methods(base_content, modified_content)
            except Exception as e:
                MethodDiffManager._log(f"Error comparing methods between {base_file_path} and {modified_file_path}: {e}", quiet, is_error=True)
                continue # Skip this pair on error

            for diff_detail in per_file_method_diffs:
                # The file_name in the diff should refer to the *modified* file's identity.
                # If file_paths can be relative, os.path.basename is fine.
                # If they are absolute and from different source trees, more complex path logic might be needed.
                # For now, assume file_paths gives enough context for identity.
                diff_entry = MethodDiffManager._convert_to_diff_format(
                    diff_detail,
                    os.path.basename(modified_file_path), # Use basename of the modified file
                    base_content, # Pass base_content for context when finding 'until_exclude'
                    quiet # Pass quiet flag
                )
                if diff_entry:
                    all_diffs.append(diff_entry)

        MethodDiffManager._log(f"Extracted {len(all_diffs)} total method diff instructions.", quiet)
        return all_diffs

    @staticmethod
    def _convert_to_diff_format(diff_detail: Dict[str, Any], modified_file_name: str, base_code_content: str, quiet: bool) -> Optional[Dict[str, Any]]:
        """
        Converts a single method diff (from PythonAnalyzer.compare_methods)
        into the structured format for a .diff file.
        Needs base_code_content to find context for 'until_exclude'.
        """
        method_name = diff_detail['method_name']
        # Use the precise signature from the analyzer if available, otherwise a simple "def name"
        find_method_signature_str = (diff_detail.get('old_signature', f"def {method_name}")
                                     if diff_detail['type'] != 'added' else "")


        # Determine 'until_exclude' by finding the start of the *next* definition in the base content
        # This is only relevant for 'modified' or 'removed' types.
        until_exclude_signature_str = ""
        if diff_detail['type'] in ['modified', 'removed']:
            # Find the original method in the base content to get its end line
            original_methods_in_base = PythonAnalyzer.extract_methods(base_code_content)
            original_method_node = next((m for m in original_methods_in_base if m["name"] == method_name), None)

            if original_method_node and original_method_node.get("end_line"):
                until_exclude_signature_str = MethodDiffManager._find_next_definition_signature_in_text(
                    base_code_content,
                    original_method_node["end_line"] # Search after the end of the current method
                )
            else: # Fallback if end_line not found or method node missing (should be rare)
                 MethodDiffManager._log(f"Could not determine original end line for method '{method_name}' to find until_exclude. 'until_exclude' may be empty.", quiet, is_error=True)


        if diff_detail["type"] == "added":
            return {
                "file": modified_file_name,
                "find_method": "", # Empty indicates an addition (usually append)
                "until_exclude": "", # Not relevant for pure addition
                "replace_with": diff_detail["new_source"]
            }
        elif diff_detail["type"] == "modified":
            return {
                "file": modified_file_name,
                "find_method": find_method_signature_str,
                "until_exclude": until_exclude_signature_str,
                "replace_with": diff_detail["new_source"]
            }
        elif diff_detail["type"] == "removed":
            return {
                "file": modified_file_name,
                "find_method": find_method_signature_str,
                "until_exclude": until_exclude_signature_str,
                "replace_with": "" # Empty string means delete the block
            }
        return None

    @staticmethod
    def _find_next_definition_signature_in_text(file_text_content: str, start_search_after_line_num: int) -> str:
        """
        Scans text content line by line after a given line number to find the
        next 'def', 'async def', or 'class' definition at the start of a line (ignoring indent).
        Returns the signature line (e.g., "def next_func(...):") or empty string.
        """
        lines = file_text_content.splitlines()
        # Start searching from the line *after* the one specified
        for i in range(start_search_after_line_num, len(lines)):
            line_stripped_leading = lines[i].lstrip() # Check for def/class at start of content on line
            if line_stripped_leading.startswith(("def ", "async def ", "class ")):
                # Return the line up to the colon (if any) or the full significant part of the line
                # This makes the 'until_exclude' more robust to minor formatting.
                signature_part = lines[i].strip() # Get the full stripped line for the signature
                # We want to match this line when applying the diff.
                return signature_part
        return "" # No subsequent definition found

    @staticmethod
    def _parse_diff_file(diff_file_path: str, quiet: bool = False) -> List[Dict[str, Any]]:
        """Parses a .diff file into a list of diff instruction dictionaries."""
        diff_instructions = []
        if not os.path.exists(diff_file_path):
            MethodDiffManager._log(f"Diff file '{diff_file_path}' not found for parsing.", quiet, is_error=True)
            return diff_instructions

        try:
            with open(diff_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            MethodDiffManager._log(f"Error reading diff file '{diff_file_path}': {e}", quiet, is_error=True)
            return diff_instructions

        current_instruction: Dict[str, Any] = {}
        lines = content.splitlines() # Keep empty lines for REPLACE_WITH
        i = 0
        while i < len(lines):
            line = lines[i] # Original line with leading/trailing spaces
            line_stripped = line.strip() # For checking prefixes

            if line_stripped.startswith("FILE:"):
                if current_instruction: diff_instructions.append(current_instruction)
                current_instruction = {"file": line_stripped.split(":", 1)[1].strip()}
            elif line_stripped.startswith("SECTION:"):
                current_instruction["section"] = line_stripped.split(":", 1)[1].strip()
            elif line_stripped.startswith("FIND_METHOD:"):
                current_instruction["find_method"] = line_stripped.split(":", 1)[1].strip()
            elif line_stripped.startswith("UNTIL_EXCLUDE:"):
                current_instruction["until_exclude"] = line_stripped.split(":", 1)[1].strip()
            elif line_stripped.startswith("REPLACE_WITH:"):
                replacement_block_lines = []
                i += 1 # Move to the first line of the replacement block
                # Collect all subsequent lines until the next 'FILE:' directive or EOF
                while i < len(lines) and not lines[i].strip().startswith("FILE:"):
                    replacement_block_lines.append(lines[i]) # Preserve original line content
                    i += 1
                current_instruction["replace_with"] = "\n".join(replacement_block_lines)
                # If loop ended due to new 'FILE:', decrement i so it's processed in next outer loop
                if i < len(lines) and lines[i].strip().startswith("FILE:"):
                    i -= 1
            i += 1

        if current_instruction: # Append the last instruction gathered
            diff_instructions.append(current_instruction)

        if not diff_instructions and content.strip(): # If file had content but no instructions parsed
            MethodDiffManager._log(f"Diff file '{diff_file_path}' had content but no valid diff instructions were parsed.", quiet, is_error=True)

        return diff_instructions

    @staticmethod
    def apply_diff(diff_file_path: str, target_base_path: str, quiet: bool = False) -> bool:
        """
        Applies method diffs from a .diff file to target(s).
        target_base_path can be a single file or a directory.
        """
        diff_instructions = MethodDiffManager._parse_diff_file(diff_file_path, quiet)
        if not diff_instructions:
            if os.path.exists(diff_file_path) and os.path.getsize(diff_file_path) > 0 : # File exists and is not empty
                 MethodDiffManager._log(f"No valid diff instructions found in or parsed from '{diff_file_path}'. No changes applied.", quiet, is_error=True)
            elif not os.path.exists(diff_file_path):
                 MethodDiffManager._log(f"Diff file '{diff_file_path}' does not exist. No changes applied.", quiet, is_error=True)
            else: # File exists but is empty
                 MethodDiffManager._log(f"Diff file '{diff_file_path}' is empty. No changes applied.", quiet)
            return False # No diffs to apply or error parsing

        applied_successfully_count = 0

        for instruction in diff_instructions:
            relative_file_in_diff = instruction.get("file", "")
            if not relative_file_in_diff:
                MethodDiffManager._log("Skipping diff instruction with no 'FILE:' specified.", quiet, is_error=True)
                continue

            actual_target_file_path = ""
            if os.path.isfile(target_base_path):
                # If target_base_path is a file, all diffs apply to this one file.
                # The 'FILE:' directive in the diff is informational in this case.
                actual_target_file_path = target_base_path
                MethodDiffManager._log(f"Applying diff for '{relative_file_in_diff}' (from diff file) to specified target file '{actual_target_file_path}'.", quiet)
            elif os.path.isdir(target_base_path):
                actual_target_file_path = os.path.join(target_base_path, relative_file_in_diff)
            else:
                MethodDiffManager._log(f"Target base path '{target_base_path}' is not a valid file or directory. Skipping diff for '{relative_file_in_diff}'.", quiet, is_error=True)
                continue

            # File creation for 'added' methods if target file doesn't exist
            if not os.path.exists(actual_target_file_path):
                if not instruction.get("find_method") and instruction.get("replace_with","").strip(): # It's an "add" operation with content
                    MethodDiffManager._log(f"Target file '{actual_target_file_path}' does not exist. Creating and adding new method/content.", quiet)
                    try:
                        os.makedirs(os.path.dirname(actual_target_file_path) or '.', exist_ok=True)
                        with open(actual_target_file_path, 'w', encoding='utf-8') as f:
                            f.write(instruction["replace_with"].rstrip('\n') + '\n') # Ensure single trailing newline
                        applied_successfully_count += 1
                        continue
                    except IOError as e:
                        MethodDiffManager._log(f"Failed to create/write to new file '{actual_target_file_path}': {e}", quiet, is_error=True)
                        continue # Skip to next instruction
                else: # Not an "add" or no content to add, so file must exist
                    MethodDiffManager._log(f"Target file '{actual_target_file_path}' for diff does not exist and operation is not a simple addition. Skipping.", quiet, is_error=True)
                    continue

            # Apply the single diff instruction to the (now existing) target file
            if MethodDiffManager._apply_single_instruction_to_file_content(instruction, actual_target_file_path, quiet):
                applied_successfully_count += 1

        MethodDiffManager._log(f"Applied {applied_successfully_count} of {len(diff_instructions)} method diff instructions.", quiet)
        return applied_successfully_count > 0 # Returns True if at least one diff was applied.

    @staticmethod
    def _apply_single_instruction_to_file_content(instruction: Dict[str, Any], target_file_path: str, quiet: bool) -> bool:
        try:
            with open(target_file_path, 'r', encoding='utf-8') as f:
                original_lines = f.read().splitlines()
        except Exception as e:
            MethodDiffManager._log(f"Error reading target file '{target_file_path}' for applying diff: {e}", quiet, is_error=True)
            return False

        section_type = instruction.get("section", "").strip()
        find_sig = instruction.get("find_method", "").strip()
        until_sig = instruction.get("until_exclude", "").strip()
        replace_block = instruction.get("replace_with", "") # This is a multi-line string

        modified_lines = list(original_lines) # Work on a copy

        # Handle GLOBAL_PREAMBLE sections
        if section_type == "GLOBAL_PREAMBLE":
            # Find end boundary (UNTIL_EXCLUDE or first def/class)
            end_idx = len(modified_lines)
            if until_sig:
                for i, line in enumerate(modified_lines):
                    if until_sig in line.strip():
                        end_idx = i
                        break
            else:
                # Auto-detect first def/class if no UNTIL_EXCLUDE
                for i, line in enumerate(modified_lines):
                    line_stripped = line.lstrip()
                    if line_stripped.startswith(("def ", "async def ", "class ")):
                        end_idx = i
                        break
            
            # Replace entire preamble (from start of file to boundary)
            modified_lines = replace_block.splitlines() + modified_lines[end_idx:]
            MethodDiffManager._log(f"  Applied GLOBAL_PREAMBLE to '{target_file_path}'", quiet)
        elif not find_sig: # Add new content (typically at the end of the file)
            if replace_block.strip(): # Only add if there's non-whitespace content
                if modified_lines and modified_lines[-1].strip() != "": # Add a blank line if file not empty and doesn't end blank
                    modified_lines.append("")
                modified_lines.extend(replace_block.splitlines())
            MethodDiffManager._log(f"  Applied ADD to '{target_file_path}'", quiet)
        else:
            # Find and replace/delete existing block
            start_idx = -1
            for i, line_text in enumerate(modified_lines):
                # Match find_sig considering it might be indented in the file
                if find_sig in line_text.strip(): # More robust to find it anywhere if it's a unique enough signature start
                    start_idx = i
                    break

            if start_idx == -1:
                MethodDiffManager._log(f"  Signature '{find_sig}' not found in '{target_file_path}'. Cannot apply diff.", quiet, is_error=True)
                return False

            # Enhanced: Scan backwards to include decorators
            decorator_start_idx = start_idx
            for i in range(start_idx - 1, -1, -1):
                line = modified_lines[i].strip()
                if line.startswith('@'):
                    # Found a decorator, extend the start
                    decorator_start_idx = i
                elif line == '' or line.startswith('#'):
                    # Empty line or comment, continue scanning
                    continue
                else:
                    # Non-decorator, non-empty line - stop scanning
                    break
            
            # Update start_idx to include decorators
            start_idx = decorator_start_idx

            # Determine end_idx (exclusive)
            end_idx = len(modified_lines) # Default to end of file
            if until_sig:
                for i in range(start_idx + 1, len(modified_lines)):
                    if until_sig in modified_lines[i].strip(): # Similar matching for until_sig
                        end_idx = i
                        break
            else: # No until_sig, find next top-level def/class or EOF
                for i in range(start_idx + 1, len(modified_lines)):
                    line = modified_lines[i]
                    # A simple heuristic for top-level: starts with def/class and has no leading indent beyond what's on start_idx line
                    # This needs refinement for truly robust parsing.
                    current_indent = len(line) - len(line.lstrip())
                    start_line_indent = len(modified_lines[start_idx]) - len(modified_lines[start_idx].lstrip())

                    if line.lstrip().startswith(("def ", "async def ", "class ")) and current_indent <= start_line_indent :
                        end_idx = i
                        break

            # Perform replacement
            pre_block = modified_lines[:start_idx]
            post_block = modified_lines[end_idx:]

            modified_lines = pre_block
            if replace_block.strip() or (not replace_block.strip() and instruction.get("type") == "modified"): # Add if content or if explicit empty modification
                 modified_lines.extend(replace_block.splitlines())
            modified_lines.extend(post_block)
            action = "REMOVE" if not replace_block.strip() else "MODIFY"
            MethodDiffManager._log(f"  Applied {action} for '{find_sig}' in '{target_file_path}'", quiet)

        try:
            with open(target_file_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(modified_lines))
                if modified_lines: # Add trailing newline if content exists
                     f.write("\n")
            return True
        except Exception as e:
            MethodDiffManager._log(f"Error writing modified content to '{target_file_path}': {e}", quiet, is_error=True)
            # import traceback; traceback.print_exc(file=sys.stderr) # For deeper debugging
            return False

    @staticmethod
    def verify_diff_file(diff_file_path: str, quiet: bool = False) -> bool:
        """Verifies the syntax and basic structure of a .diff file."""
        instructions = MethodDiffManager._parse_diff_file(diff_file_path, quiet)

        if not instructions:
            if os.path.exists(diff_file_path) and os.path.getsize(diff_file_path) > 0:
                 MethodDiffManager._log(f"Diff file '{diff_file_path}' has content, but no valid instructions parsed.", quiet, is_error=True)
                 return False
            elif not os.path.exists(diff_file_path):
                 MethodDiffManager._log(f"Diff file '{diff_file_path}' not found.", quiet, is_error=True)
                 return False
            # Empty file is considered valid (0 diffs)
            MethodDiffManager._log(f"Diff file '{diff_file_path}' is empty or contains no instructions. Verified as valid (0 diffs).", quiet)
            return True

        valid_structure = True
        for idx, instruction in enumerate(instructions):
            if "file" not in instruction or not instruction["file"].strip():
                MethodDiffManager._log(f"Instruction #{idx+1} missing or empty 'FILE:' directive.", quiet, is_error=True)
                valid_structure = False
            # FIND_METHOD can be empty for additions. UNTIL_EXCLUDE can be empty. REPLACE_WITH can be empty for removals.
            # No other strict structural checks here, assuming _parse_diff_file handles basic format.

        if valid_structure:
            MethodDiffManager._log(f"Diff file '{diff_file_path}' syntax appears valid with {len(instructions)} instruction(s).", quiet)
        else:
            MethodDiffManager._log(f"Diff file '{diff_file_path}' has structural issues.", quiet, is_error=True)
        return valid_structure

if __name__ == '__main__':
    # Example for direct testing of MethodDiffManager
    print("MethodDiffManager - Direct Execution Test")

    # Create dummy files for diffing
    base_py_content = """
class Greeter:
    def say_hello(self, name):
        print(f"Hello, {name}!")

    def say_goodbye(self, name):
        # Original goodbye
        print(f"Goodbye, {name}.")

def utility_func():
    return "utility v1"
"""
    modified_py_content = """
class Greeter: # Class changed
    def say_hello(self, name, title=""): # Signature changed, body changed
        if title:
            print(f"Hello, {title} {name}!")
        else:
            print(f"Hello, {name}!") # Logic change

    # say_goodbye removed

    def new_feature(self): # Added method
        print("New feature implemented.")

# utility_func removed

def added_top_level_func():
    return "completely new"
"""
    os.makedirs("test_diff_dir/mod_subdir", exist_ok=True)
    with open("test_diff_dir/base_file.py", "w") as f: f.write(base_py_content)
    with open("test_diff_dir/mod_subdir/modified_file.py", "w") as f: f.write(modified_py_content)

    test_diff_file = "test_diff_dir/test_changes.diff"

    # 1. Extract Diff
    print("\n--- Extracting Diff ---")
    diff_instructions = MethodDiffManager.extract_diff(
        ["test_diff_dir/base_file.py", "test_diff_dir/mod_subdir/modified_file.py"],
        quiet=False
    )
    if diff_instructions:
        with open(test_diff_file, "w") as f:
            for item in diff_instructions:
                f.write(f"FILE: {item['file']}\n")
                f.write(f"FIND_METHOD: {item['find_method']}\n")
                f.write(f"UNTIL_EXCLUDE: {item['until_exclude']}\n")
                f.write(f"REPLACE_WITH:\n{item['replace_with']}\n")
        print(f"Diff extracted to {test_diff_file}")
    else:
        print("No diffs extracted.")

    # 2. Verify Diff
    print("\n--- Verifying Diff File ---")
    is_valid = MethodDiffManager.verify_diff_file(test_diff_file, quiet=False)
    print(f"Diff file '{test_diff_file}' valid: {is_valid}")

    # 3. Apply Diff
    if is_valid and diff_instructions: # Only apply if valid and diffs exist
        print("\n--- Applying Diff ---")
        # Create a copy of the base file to apply diffs to
        target_apply_file = "test_diff_dir/target_to_apply.py"
        import shutil
        shutil.copy("test_diff_dir/base_file.py", target_apply_file)

        # Test applying to a single file
        # The FILE: directive in test_changes.diff will be 'modified_file.py'
        # but we are telling it to apply to 'target_to_apply.py'
        success = MethodDiffManager.apply_diff(test_diff_file, target_apply_file, quiet=False)
        print(f"Apply diff to single file successful: {success}")
        if success:
            print(f"Contents of '{target_apply_file}' after applying diff:")
            with open(target_apply_file, "r") as f: print(f.read())

    # Clean up
    # shutil.rmtree("test_diff_dir")
    print("\nTest diff dir left for inspection: test_diff_dir/")
