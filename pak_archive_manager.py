import os
import sys
import json
import uuid
import datetime
import string
import random
import re # For pattern matching in list/extract
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Import Compressor from the sibling module
try:
    from pak_compressor import Compressor, CacheManager, ParallelCompressor # CacheManager might be needed if PakArchive sets it up
except ImportError:
    # Fallback for direct execution
    if __name__ == '__main__':
        sys.path.append(os.path.dirname(__file__))
        from pak_compressor import Compressor, CacheManager
    else:
        raise

class PakArchive:
    """
    Handles creation, extraction, listing, and verification of .pak archives
    using a JSON-based format.
    """
    PAK_FORMAT_VERSION = "4.2.0-refactored" # Version of the .pak JSON format

    def __init__(self, compression_level: str = "medium", max_tokens: int = 0, quiet: bool = False):
        self.compression_level = compression_level
        self.max_tokens = max_tokens # Token budgeting to be implemented if desired
        self.files_data: List[Dict[str, Any]] = [] # Stores file entries for the archive
        self.archive_uuid: str = self._generate_short_uuid()
        self.cache_manager: Optional[CacheManager] = None
        self.quiet: bool = quiet
    
        # Accumulated totals
        self.total_original_size_bytes: int = 0
        self.total_compressed_size_bytes: int = 0
        self.total_estimated_tokens: int = 0
    
    def _generate_short_uuid(self) -> str:
        """Generate a 4-character short UUID using letters and digits."""
        chars = string.ascii_letters + string.digits  # a-z, A-Z, 0-9
        return ''.join(random.choices(chars, k=4))

    def _log(self, message: str, is_error: bool = False):
        if not self.quiet or is_error:
            level = "ERROR" if is_error else "INFO"
            # Standardize log prefix
            print(f"PakArchive ({level}): {message}", file=sys.stderr)

    def set_cache_manager(self, cache_manager: CacheManager):
        """Allows setting a CacheManager, typically for compression operations."""
        self.cache_manager = cache_manager
        self._log(f"CacheManager set. Cache file: {getattr(cache_manager, 'cache_file', 'N/A')}")


    def add_file(self, file_path: str, content: str, importance: int = 0):
        """
        Adds a file to the in-memory archive representation.
        Content is compressed based on current settings.
        """
        normalized_file_path = str(Path(file_path)).replace(os.sep, '/') # Ensure POSIX-style paths in archive

        # Initialize compressor. Pass the cache_manager if it's set.
        compressor_instance = Compressor(cache_manager=self.cache_manager, quiet=self.quiet)

        # compress_content returns a dictionary with all relevant details
        comp_result = compressor_instance.compress_content(content, normalized_file_path, self.compression_level)

        self._log(f"Adding '{normalized_file_path}': "
                  f"{comp_result['original_size']}B -> {comp_result['compressed_size']}B "
                  f"({comp_result['compression_ratio']:.1f}x), "
                  f"{comp_result['estimated_tokens']} tokens, "
                  f"Method: {comp_result['method']}")

        file_entry: Dict[str, Any] = {
            "path": normalized_file_path,
            "content": comp_result["compressed_content"],
            "original_size_bytes": comp_result["original_size"],
            "compressed_size_bytes": comp_result["compressed_size"],
            "estimated_tokens": comp_result["estimated_tokens"],
            "compression_method": comp_result["method"],
            "compression_ratio": comp_result["compression_ratio"],
            "importance_score": importance, # Renamed for clarity
            "last_modified_utc": datetime.datetime.utcfromtimestamp(os.path.getmtime(file_path)).isoformat() + "Z" if os.path.exists(file_path) else None
        }
        self.files_data.append(file_entry)

        # Update totals
        self.total_original_size_bytes += comp_result["original_size"]
        self.total_compressed_size_bytes += comp_result["compressed_size"]
        self.total_estimated_tokens += comp_result["estimated_tokens"]
    
    def add_files_parallel(self, file_data_list: List[Tuple[str, str, int]], max_workers: int = 3):
        """
        Add multiple files to the archive using parallel processing.
        
        Args:
            file_data_list: List of (file_path, content, importance) tuples
            max_workers: Maximum number of parallel workers (default 3 for conservative approach)
        """
        if not file_data_list:
            return
            
        self._log(f"Adding {len(file_data_list)} files with parallel processing (max_workers={max_workers})")
        
        # Initialize compressor and parallel processor
        base_compressor = Compressor(cache_manager=self.cache_manager, quiet=self.quiet)
        parallel_compressor = ParallelCompressor(base_compressor, max_workers=max_workers, quiet=self.quiet)
        
        # Prepare compression tasks: (content, normalized_file_path, compression_level)
        compression_tasks = []
        file_info_list = []
        
        for file_path, content, importance in file_data_list:
            normalized_file_path = str(Path(file_path)).replace(os.sep, '/') # Ensure POSIX-style paths in archive
            compression_tasks.append((content, normalized_file_path, self.compression_level))
            file_info_list.append((normalized_file_path, importance, file_path))  # Store for later processing
        
        # Execute parallel compression
        compression_results = parallel_compressor.compress_files_parallel(compression_tasks)
        
        # Process results and add to archive
        for (normalized_file_path, importance, original_file_path), comp_result in zip(file_info_list, compression_results):
            if comp_result is None:
                self._log(f"Warning: No result for file {normalized_file_path}", is_error=True)
                continue
                
            self._log(f"Adding '{normalized_file_path}': "
                      f"{comp_result['original_size']}B -> {comp_result['compressed_size']}B "
                      f"({comp_result['compression_ratio']:.1f}x), "
                      f"{comp_result['estimated_tokens']} tokens, "
                      f"Method: {comp_result['method']}")

            file_entry: Dict[str, Any] = {
                "path": normalized_file_path,
                "content": comp_result["compressed_content"],
                "original_size_bytes": comp_result["original_size"],
                "compressed_size_bytes": comp_result["compressed_size"],
                "estimated_tokens": comp_result["estimated_tokens"],
                "compression_method": comp_result["method"],
                "compression_ratio": comp_result["compression_ratio"],
                "importance_score": importance,
                "last_modified_utc": datetime.datetime.utcfromtimestamp(os.path.getmtime(original_file_path)).isoformat() + "Z" if os.path.exists(original_file_path) else None
            }
            self.files_data.append(file_entry)

            # Update totals
            self.total_original_size_bytes += comp_result["original_size"]
            self.total_compressed_size_bytes += comp_result["compressed_size"]
            self.total_estimated_tokens += comp_result["estimated_tokens"]
        
        # Log parallel processing statistics
        parallel_stats = parallel_compressor.get_parallel_stats()
        self._log(f"Parallel processing completed. Stats: {parallel_stats['files_processed_in_parallel']} parallel, "
                  f"{parallel_stats['files_processed_sequentially']} sequential, "
                  f"avg wait: {parallel_stats['average_wait_per_file']:.1f}s")

    def create_archive(self, output_file_path: Optional[str] = None) -> Optional[str]:
        """
        Finalizes the archive structure and writes it to a JSON file,
        or returns the JSON string if output_file_path is None.
        """
        archive_metadata: Dict[str, Any] = {
            "pak_format_version": PakArchive.PAK_FORMAT_VERSION,
            "archive_uuid": self.archive_uuid,
            "creation_timestamp_utc": datetime.datetime.utcnow().isoformat() + "Z",
            "source_tool_version": "pak_core_refactored_v_unknown", # Placeholder, could be passed in
            "compression_level_setting": self.compression_level,
            "max_tokens_setting": self.max_tokens,
            "total_files": len(self.files_data),
            "total_original_size_bytes": self.total_original_size_bytes,
            "total_compressed_size_bytes": self.total_compressed_size_bytes,
            "total_estimated_tokens": self.total_estimated_tokens,
        }

        full_archive_data: Dict[str, Any] = {
            "metadata": archive_metadata,
            "files": self.files_data
        }

        self._log(f"Archive generation complete. Summary: {len(self.files_data)} files, "
                  f"{self.total_original_size_bytes}B original, "
                  f"{self.total_compressed_size_bytes}B compressed, "
                  f"{self.total_estimated_tokens} tokens.")

        if output_file_path:
            try:
                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_file_path) or '.', exist_ok=True)
                with open(output_file_path, 'w', encoding='utf-8') as f:
                    json.dump(full_archive_data, f, indent=2)
                self._log(f"Archive successfully written to '{output_file_path}'.")
                # Save cache if a manager was used and an output path was provided
                if self.cache_manager:
                    self.cache_manager.save_cache()
                return None # Indicates success to file
            except IOError as e:
                self._log(f"Error writing archive to '{output_file_path}': {e}", is_error=True)
                raise
        else: # Return as JSON string
            json_output_string = json.dumps(full_archive_data, indent=2)
            if self.cache_manager: # Still save cache if used
                 self.cache_manager.save_cache()
            return json_output_string

    @staticmethod
    def _load_archive_json_data(archive_file_path: str, quiet: bool = False) -> Dict[str, Any]:
        """Loads and performs initial validation on the archive JSON data."""
        if not os.path.exists(archive_file_path):
            # Logged by PakArchive static methods directly if quiet is False
            raise FileNotFoundError(f"Archive file not found: {archive_file_path}")
        try:
            with open(archive_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, dict) or "metadata" not in data or "files" not in data:
                raise ValueError("Invalid archive format: Missing 'metadata' or 'files' top-level keys.")
            if "pak_format_version" not in data["metadata"]:
                raise ValueError("Invalid archive format: 'pak_format_version' missing in metadata.")
            # Could add version compatibility check here if versions diverge significantly
            # e.g., if data["metadata"]["pak_format_version"] < PakArchive.MIN_SUPPORTED_VERSION: ...
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in archive file '{archive_file_path}': {e}")
        except Exception as e: # Catch other loading errors
            # PakArchive._log(f"Unexpected error loading archive '{archive_file_path}': {e}", quiet, is_error=True) # Static methods need explicit quiet
            raise Exception(f"Error loading archive data from '{archive_file_path}': {e}")


    @staticmethod
    def extract_archive(archive_file_path: str, output_base_dir: str,
                        file_path_pattern: Optional[str] = None, quiet: bool = False):
        """Extracts files from a .pak archive to the specified output directory."""
        try:
            archive_data = PakArchive._load_archive_json_data(archive_file_path, quiet)
        except Exception as e: # Catch errors from loading (FileNotFound, ValueError)
            if not quiet: print(f"PakArchive (ERROR): Failed to load archive for extraction: {e}", file=sys.stderr)
            return # Cannot proceed

        os.makedirs(output_base_dir, exist_ok=True)
        if not quiet:
            print(f"PakArchive (INFO): Extracting from '{archive_file_path}' (UUID: {archive_data['metadata'].get('archive_uuid', 'N/A')}) to '{os.path.abspath(output_base_dir)}'", file=sys.stderr)

        extracted_count = 0
        total_files = len(archive_data.get("files", []))
        pattern_regex = re.compile(file_path_pattern) if file_path_pattern else None

        for file_entry in archive_data.get("files", []):
            stored_path = file_entry.get("path", "")
            if not stored_path:
                if not quiet: print("PakArchive (WARNING): Skipping file entry with no path.", file=sys.stderr)
                continue

            if pattern_regex and not pattern_regex.search(stored_path):
                continue # Skip if path doesn't match pattern

            # Construct OS-specific relative path and then absolute output path
            # Stored paths are POSIX-style ('/')
            os_specific_relative_path = os.path.join(*stored_path.split('/'))
            abs_output_file_path = os.path.abspath(os.path.join(output_base_dir, os_specific_relative_path))

            # Security check: ensure path is still within the intended output_base_dir
            if not abs_output_file_path.startswith(os.path.abspath(output_base_dir)):
                if not quiet: print(f"PakArchive (WARNING): Skipping potentially unsafe path '{stored_path}' trying to write outside '{output_base_dir}'. Resolved to '{abs_output_file_path}'", file=sys.stderr)
                continue

            try:
                os.makedirs(os.path.dirname(abs_output_file_path), exist_ok=True)
                with open(abs_output_file_path, 'w', encoding='utf-8') as f:
                    f.write(file_entry.get("content", "")) # Default to empty content if missing
                if not quiet: print(f"  Extracted: {stored_path} -> {abs_output_file_path}", file=sys.stderr)
                extracted_count += 1
            except IOError as e:
                if not quiet: print(f"PakArchive (ERROR): Could not write file '{abs_output_file_path}': {e}", file=sys.stderr)
            except Exception as e_other:
                if not quiet: print(f"PakArchive (ERROR): Unexpected error extracting '{stored_path}': {e_other}", file=sys.stderr)

        if not quiet:
            summary = f"PakArchive (INFO): Extraction complete. {extracted_count}/{total_files} files"
            if file_path_pattern: summary += f" (matching '{file_path_pattern}')"
            summary += f" extracted to '{os.path.abspath(output_base_dir)}'."
            print(summary, file=sys.stderr)

    @staticmethod
    def list_archive(archive_file_path: str, detailed: bool = False,
                     file_path_pattern: Optional[str] = None, quiet: bool = False):
        """Lists contents of a .pak archive. Output goes to stdout."""
        try:
            archive_data = PakArchive._load_archive_json_data(archive_file_path, quiet)
        except Exception as e:
            # Use stdout for list command errors as per typical CLI behavior
            print(f"Error loading archive for listing: {e}", file=sys.stdout if quiet else sys.stderr)
            return

        # List output should go to stdout
        header_prefix = "Archive (Detailed View):" if detailed else "Archive Contents:"
        print(f"{header_prefix} {os.path.basename(archive_file_path)}", file=sys.stdout)
        print(f"  Format Version: {archive_data['metadata'].get('pak_format_version', 'N/A')}", file=sys.stdout)
        print(f"  UUID: {archive_data['metadata'].get('archive_uuid', 'N/A')}", file=sys.stdout)
        print("-" * 40, file=sys.stdout)

        matched_count = 0
        total_files = len(archive_data.get("files", []))
        pattern_regex = re.compile(file_path_pattern) if file_path_pattern else None

        for file_entry in archive_data.get("files", []):
            path = file_entry.get("path", "UNKNOWN_PATH")
            if pattern_regex and not pattern_regex.search(path):
                continue
            matched_count += 1

            if detailed:
                orig_size = file_entry.get('original_size_bytes', 0)
                comp_size = file_entry.get('compressed_size_bytes', 0)
                tokens = file_entry.get('estimated_tokens', 0)
                method = file_entry.get('compression_method', 'N/A')
                ratio = file_entry.get('compression_ratio', 0.0)

                print(f"File: {path}", file=sys.stdout)
                print(f"  Size: {orig_size} B (Original) -> {comp_size} B (Compressed, {ratio:.1f}x)", file=sys.stdout)
                print(f"  Tokens: ~{tokens}, Method: {method}", file=sys.stdout)
                content_preview = file_entry.get("content", "")
                preview_lines = content_preview.splitlines()[:2] # Preview first 2 lines
                if preview_lines:
                    print(f"  Preview:", file=sys.stdout)
                    for p_line in preview_lines: print(f"    {p_line[:80]}{'...' if len(p_line)>80 else ''}", file=sys.stdout)
                if len(content_preview.splitlines()) > 2: print("    ...", file=sys.stdout)
                print("  ---", file=sys.stdout)
            else:
                print(path, file=sys.stdout)

        print("=" * 40, file=sys.stdout)
        summary_totals = archive_data.get("metadata", {})
        print(f"Listed {matched_count}/{total_files} files.", file=sys.stdout)
        if file_path_pattern: print(f"  (Filtered by pattern: '{file_path_pattern}')", file=sys.stdout)
        print(f"Total Archive (Original): {summary_totals.get('total_original_size_bytes',0)} B", file=sys.stdout)
        print(f"Total Archive (Compressed): {summary_totals.get('total_compressed_size_bytes',0)} B", file=sys.stdout)
        print(f"Total Archive (Est. Tokens): {summary_totals.get('total_estimated_tokens',0)}", file=sys.stdout)


    @staticmethod
    def verify_archive(archive_file_path: str, quiet: bool = False) -> bool:
        """Verifies the basic integrity and structure of a .pak archive."""
        # Verification messages go to stdout as per CLI tool conventions.
        # Errors during verification process (like file not found) can go to stderr if not quiet.
        try:
            archive_data = PakArchive._load_archive_json_data(archive_file_path, quiet) # Performs initial load and format checks

            # Additional checks specific to verification
            files_list = archive_data.get("files", [])
            if not isinstance(files_list, list):
                print(f"✗ Verification Failed: 'files' key is not a list in '{archive_file_path}'.", file=sys.stdout)
                return False

            for i, file_entry in enumerate(files_list):
                if not isinstance(file_entry, dict):
                    print(f"✗ Verification Failed: File entry #{i+1} is not a dictionary.", file=sys.stdout)
                    return False
                required_keys = ["path", "content", "original_size_bytes", "compressed_size_bytes", "estimated_tokens", "compression_method"]
                for key in required_keys:
                    if key not in file_entry:
                        print(f"✗ Verification Failed: Missing key '{key}' in file entry #{i+1} ('{file_entry.get('path','UNKNOWN_PATH')}').", file=sys.stdout)
                        return False

            if not quiet:
                print(f"✓ Archive '{archive_file_path}' (Format: {archive_data['metadata'].get('pak_format_version','unknown')}) appears valid. Contains {len(files_list)} file entries.", file=sys.stdout)
            return True
        except FileNotFoundError:
            # Error already logged by _load_archive_json_data if not quiet
            if not quiet: print(f"✗ Verification Error: Archive file '{archive_file_path}' not found.", file=sys.stdout)
            return False
        except ValueError as e: # Catches JSON errors and format errors from _load_archive_json_data
            print(f"✗ Verification Failed for '{archive_file_path}': {e}", file=sys.stdout)
            return False
        except Exception as e: # Catch-all for other unexpected errors
            if not quiet: print(f"PakArchive (ERROR): Unexpected error verifying archive '{archive_file_path}': {e}", file=sys.stderr)
            print(f"✗ Unexpected error verifying archive '{archive_file_path}'.", file=sys.stdout)
            return False

if __name__ == '__main__':
    # Example for direct testing of PakArchive
    print("PakArchive - Direct Execution Test")

    # Create a dummy PakArchive instance
    # For a real test, you'd need a CacheManager if testing compression-related caching
    pak_test = PakArchive(compression_level="light", quiet=False)

    # Add some dummy files
    pak_test.add_file("test_dir/file1.txt", "This is content for file1.\nHello world.", importance=1)
    pak_test.add_file("test_dir/subdir/file2.py", "def main():\n  print('Hello from Python')\n# A comment", importance=2)
    pak_test.add_file("empty.txt", "") # Test empty file

    # Create archive to a file
    test_archive_path = "test_output_archive.pak.json" # Use .json extension for clarity
    pak_test.create_archive(test_archive_path)

    if os.path.exists(test_archive_path):
        print(f"\n--- Verifying Archive: {test_archive_path} ---")
        PakArchive.verify_archive(test_archive_path, quiet=False)

        print(f"\n--- Listing Archive (Simple): {test_archive_path} ---")
        PakArchive.list_archive(test_archive_path, quiet=False)

        print(f"\n--- Listing Archive (Detailed): {test_archive_path} ---")
        PakArchive.list_archive(test_archive_path, detailed=True, quiet=False)

        print(f"\n--- Extracting Archive: {test_archive_path} ---")
        extract_to_dir = "test_extracted_output"
        PakArchive.extract_archive(test_archive_path, extract_to_dir, quiet=False)
        print(f"Files should be in '{extract_to_dir}' directory.")

        # Clean up test files/dirs (optional, comment out to inspect)
        # import shutil
        # os.remove(test_archive_path)
        # shutil.rmtree(extract_to_dir)
        print(f"\nTest files ({test_archive_path}, {extract_to_dir}) left for inspection.")
    else:
        print(f"ERROR: Test archive file '{test_archive_path}' was not created.")
