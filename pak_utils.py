import os
import glob
from pathlib import Path
import sys # For printing warnings
from typing import List, Dict, Optional, Set
import fnmatch

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

def filter_files_by_pattern(files: List[str], pattern: str) -> List[str]:
    """
    Filter files by a Unix shell-style wildcard pattern.
    
    Args:
        files: List of file paths to filter
        pattern: Unix shell-style pattern (e.g., "*.py", "test_*")
    
    Returns:
        List of files matching the pattern
    """
    if not pattern:
        return files
    
    filtered = []
    for file_path in files:
        # Check both full path and just filename
        if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(os.path.basename(file_path), pattern):
            filtered.append(file_path)
    
    return filtered

def validate_file_access(file_paths: List[str], quiet: bool = False) -> List[str]:
    """
    Validate that files exist and are readable.
    
    Args:
        file_paths: List of file paths to validate
        quiet: If True, suppress warning messages
    
    Returns:
        List of valid, accessible file paths
    """
    valid_files = []
    
    for file_path in file_paths:
        try:
            if os.path.exists(file_path) and os.access(file_path, os.R_OK):
                valid_files.append(file_path)
            elif not quiet:
                print(f"pak_utils: Warning: Cannot access file '{file_path}'", file=sys.stderr)
        except Exception as e:
            if not quiet:
                print(f"pak_utils: Warning: Error checking file '{file_path}': {e}", file=sys.stderr)
    
    return valid_files

def get_file_stats(file_paths: List[str]) -> Dict[str, int]:
    """
    Get statistics about a collection of files.
    
    Args:
        file_paths: List of file paths to analyze
    
    Returns:
        Dictionary with file statistics
    """
    stats = {
        'total_files': len(file_paths),
        'total_size_bytes': 0,
        'extensions': {},
        'largest_file_size': 0,
        'smallest_file_size': float('inf')
    }
    
    for file_path in file_paths:
        try:
            size = os.path.getsize(file_path)
            stats['total_size_bytes'] += size
            stats['largest_file_size'] = max(stats['largest_file_size'], size)
            stats['smallest_file_size'] = min(stats['smallest_file_size'], size)
            
            ext = Path(file_path).suffix.lower()
            stats['extensions'][ext] = stats['extensions'].get(ext, 0) + 1
            
        except OSError:
            continue  # Skip files that can't be accessed
    
    if stats['smallest_file_size'] == float('inf'):
        stats['smallest_file_size'] = 0
    
    return stats
