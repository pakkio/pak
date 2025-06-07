import os
import glob
from pathlib import Path
import sys # For printing warnings

def collect_files(targets: list[str], extensions: list[str], quiet: bool = False) -> list[str]:
    """
    Collects files based on targets (files, dirs, globs) and extensions.
    Args:
        targets: A list of strings, where each string can be a file path,
                 a directory path, or a glob pattern.
        extensions: A list of extension strings (e.g., ['.py', '.js']) to filter by.
                    If empty, all files matching targets are included.
        quiet: If True, suppress warning messages.
    Returns:
        A sorted list of unique, normalized file paths.
    """
    collected_files_set = set()

    for target_pattern in targets:
        # Normalize the target pattern early
        norm_target_pattern = os.path.normpath(target_pattern)

        if os.path.isdir(norm_target_pattern):
            for root, _, files_in_dir in os.walk(norm_target_pattern):
                for file_name in files_in_dir:
                    full_file_path = os.path.normpath(os.path.join(root, file_name))
                    if not extensions or Path(file_name).suffix.lower() in extensions:
                        collected_files_set.add(full_file_path)
        elif os.path.isfile(norm_target_pattern):
            if not extensions or Path(norm_target_pattern).suffix.lower() in extensions:
                collected_files_set.add(norm_target_pattern)
        else:
            # Treat as glob pattern
            # Using iglob for potentially large number of matches to save memory
            # Ensure recursive glob works if '**' is present
            is_recursive = "**" in target_pattern
            try:
                # For glob, it's better to use the original pattern if it might contain special chars
                # that normpath could alter in a way glob doesn't expect (though unlikely for valid paths).
                matched_paths = glob.iglob(target_pattern, recursive=is_recursive)
                for path_str in matched_paths:
                    norm_path = os.path.normpath(path_str)
                    if os.path.isfile(norm_path): # Ensure it's a file
                        if not extensions or Path(norm_path).suffix.lower() in extensions:
                            collected_files_set.add(norm_path)
            except Exception as e:
                if not quiet:
                    print(f"pak_utils: Warning: Error processing glob pattern '{target_pattern}': {e}", file=sys.stderr)

    return sorted(list(collected_files_set))

if __name__ == '__main__':
    # Example usage:
    # Create some dummy files and directories for testing
    os.makedirs("test_collect/subdir", exist_ok=True)
    open("test_collect/file1.py", "w").close()
    open("test_collect/file2.txt", "w").close()
    open("test_collect/subdir/file3.py", "w").close()
    open("test_collect/subdir/file4.md", "w").close()

    print("Collecting all from 'test_collect':")
    print(collect_files(["test_collect"], [], quiet=False))

    print("\nCollecting .py files from 'test_collect':")
    print(collect_files(["test_collect"], [".py"], quiet=False))

    print("\nCollecting specific files and a glob:")
    print(collect_files(["test_collect/file1.py", "test_collect/subdir/*.md"], [], quiet=False))

    print("\nCollecting with recursive glob (test_collect/**/*.py):")
    # Note: '**' might need shell expansion or Python 3.5+ glob
    print(collect_files(["test_collect/**/*.py"], [], quiet=False))


    # Clean up dummy files
    import shutil
    shutil.rmtree("test_collect")
