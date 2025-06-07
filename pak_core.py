#!/usr/bin/env python3
"""
pak_core.py (Orchestrator) - Main entry point for pak operations.
Delegates tasks to specialized modules.
"""

import sys
import argparse
import datetime
import os # For os.path.basename in auto_output_name

# Import from local modules
from pak_utils import collect_files
from pak_analyzer import PythonAnalyzer # Though not directly used here, good to know it's available
from pak_compressor import Compressor, CacheManager # Compressor also brings SemanticCompressor, TokenCounter
from pak_differ import MethodDiffManager
from pak_archive_manager import PakArchive

def main():
    parser = argparse.ArgumentParser(
        description="pak_core.py - LLM-enhanced file archiver with semantic compression and method diff support. Uses JSON archive format.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument('command',
                        choices=['pack', 'extract', 'list', 'list-detailed', 'verify',
                                 'extract-diff', 'verify-diff', 'apply-diff'],
                        help="Action to perform.\n"
                             "  pack: Create an archive.\n"
                             "  extract: Extract files from an archive.\n"
                             "  list: List archive contents (paths only).\n"
                             "  list-detailed: List archive contents with details and previews.\n"
                             "  verify: Verify archive integrity.\n"
                             "  extract-diff: Extract method-level differences between files.\n"
                             "  verify-diff: Verify a method diff file's syntax.\n"
                             "  apply-diff: Apply a method diff file to target(s).")

    parser.add_argument('targets', nargs='*',
                        help="Target files, directories, or glob patterns for 'pack' and 'extract-diff'.\n"
                             "For 'extract', 'list', 'list-detailed', 'verify': path to the .pak archive file.\n"
                             "For 'verify-diff': path to the .diff file.\n"
                             "For 'apply-diff': first target is .diff file, second is target file/directory.")

    pack_group = parser.add_argument_group('Packing Options')
    pack_group.add_argument('--compression-level', '-c', default='medium',
                       choices=['0', 'none', '1', 'light', '2', 'medium', '3', 'aggressive', '4', 'semantic', 's', 'smart'],
                       help="Compression strategy (default: medium).\n"
                            "  0/none: Raw content.\n"
                            "  1/light: Basic whitespace normalization.\n"
                            "  2/medium: Removes comments and empty lines.\n"
                            "  3/aggressive: AST-based structure extraction (Python), or heuristic.\n"
                            "  4/semantic: LLM-based semantic summary.\n"
                            "  s/smart: Adaptive, tries semantic for suitable files.")
    pack_group.add_argument('--max-tokens', '-m', type=int, default=0, help='Max total estimated tokens for archive (0=unlimited, pack only).')
    pack_group.add_argument('--output', '-o', help='Output file path for "pack" or "extract-diff". If not set for "pack", outputs to stdout or auto-generates name.')
    pack_group.add_argument('--ext', nargs='*', default=[],
                       help="File extensions to include for 'pack' (e.g., .py .js .md). If not specified, all files are considered.")

    filter_group = parser.add_argument_group('Filtering Options (for list/extract)')
    filter_group.add_argument('--pattern', '-p', help='Regex pattern to filter files by path during "list" or "extract".')

    extract_group = parser.add_argument_group('Extraction Options')
    extract_group.add_argument('--outdir', '-d', default=".", help='Output directory for "extract" (default: current directory).')

    general_group = parser.add_argument_group('General Options')
    general_group.add_argument('--quiet', '-q', action='store_true', help='Suppress informational messages (stderr). Errors are still shown.')

    args = parser.parse_args()

    # Normalize extensions (moved from old pak_core.py for clarity)
    import re # For splitting extensions
    normalized_extensions = []
    if args.ext:
        for ext_item in args.ext:
            for single_ext in re.split(r'[,\s]+', ext_item):
                if single_ext:
                    if not single_ext.startswith('.'):
                        normalized_extensions.append('.' + single_ext.lower())
                    else:
                        normalized_extensions.append(single_ext.lower())
    args.ext = list(set(normalized_extensions))

    try:
        if args.command == 'pack':
            if not args.targets:
                parser.error("The 'pack' command requires at least one target (file, directory, or glob pattern).")

            collected_target_files = collect_files(args.targets, args.ext, args.quiet)

            # Auto-generate output name if needed (moved here for clarity)
            # This logic might be better placed in pak4 if it needs access to TTY state
            # For now, keeping it here as pak_core.py is still the entry for Python logic.
            actual_output_path = args.output
            if not actual_output_path and sys.stdout.isatty(): # Check if stdout is a TTY
                base_name="archive"
                if len(args.targets) == 1 and os.path.isdir(args.targets[0]):
                    base_name = os.path.basename(os.path.abspath(args.targets[0])) # Use absolute path for dirname
                    if base_name == "." or not base_name: base_name = os.path.basename(os.getcwd())
                elif args.targets:
                    base_name = os.path.basename(args.targets[0]).split('.')[0] + "_collection"

                cl_suffix_map = {"semantic": "_semantic", "smart": "_smart", "aggressive": "_min", "medium": "_med", "light": "_light"}
                actual_output_path = f"{base_name}{cl_suffix_map.get(args.compression_level, '')}.pak"
                if not args.quiet:
                    print(f"pak_core: Auto-generating output file name: {actual_output_path}", file=sys.stderr)


            if not collected_target_files:
                if not args.quiet:
                    print("pak_core: No files found matching targets and extension filters. Archive will be empty or not created.", file=sys.stderr)
                pak = PakArchive(args.compression_level, args.max_tokens, args.quiet)
                archive_json_output = pak.create_archive(actual_output_path) # Pass potentially auto-generated name
                if archive_json_output: # Output to stdout
                    print(archive_json_output)
                return 0

            pak = PakArchive(args.compression_level, args.max_tokens, args.quiet)
            if actual_output_path:
                cache_mgr = CacheManager(actual_output_path)
                pak.set_cache_manager(cache_mgr)

            for file_to_pack in collected_target_files:
                try:
                    with open(file_to_pack, 'r', encoding='utf-8', errors='ignore') as f:
                        file_content = f.read()
                    pak.add_file(file_to_pack, file_content)
                except Exception as e:
                    if not args.quiet:
                        print(f"pak_core: Warning: Could not read or process file {file_to_pack}: {e}", file=sys.stderr)

            archive_json_output = pak.create_archive(actual_output_path)
            if archive_json_output:
                print(archive_json_output)

        elif args.command == 'extract':
            if not args.targets: parser.error("'extract' command requires an archive file path.")
            PakArchive.extract_archive(args.targets[0], args.outdir, args.pattern, args.quiet)

        elif args.command == 'list':
            if not args.targets: parser.error("'list' command requires an archive file path.")
            PakArchive.list_archive(args.targets[0], detailed=False, file_path_pattern=args.pattern, quiet=args.quiet)

        elif args.command == 'list-detailed':
            if not args.targets: parser.error("'list-detailed' command requires an archive file path.")
            PakArchive.list_archive(args.targets[0], detailed=True, file_path_pattern=args.pattern, quiet=args.quiet)

        elif args.command == 'verify':
            if not args.targets: parser.error("'verify' command requires an archive file path.")
            success = PakArchive.verify_archive(args.targets[0], args.quiet)
            return 0 if success else 1

        elif args.command == 'extract-diff':
            if len(args.targets) < 2:
                parser.error("'extract-diff' requires at least two file targets (base_file, modified_file1 ...).")
            if not args.output:
                # If no output file specified, diffs will be written to stdout by pak4 script directly
                # For pak_core.py, we can construct the diff data and print it as JSON to stdout
                # This requires pak4 to handle it or for pak_core to write to a temp file if needed.
                # For now, let's assume if args.output is None, pak4 handles stdout.
                # If pak_core is called directly, this needs -o.
                 parser.error("'extract-diff' called from pak_core.py directly requires an --output file path for the diff.")


            diff_data = MethodDiffManager.extract_diff(args.targets, quiet=args.quiet) # Pass quiet

            try:
                with open(args.output, 'w', encoding='utf-8') as f:
                    for diff_item in diff_data:
                        f.write(f"FILE: {diff_item['file']}\n")
                        f.write(f"FIND_METHOD: {diff_item['find_method']}\n")
                        f.write(f"UNTIL_EXCLUDE: {diff_item['until_exclude']}\n")
                        f.write(f"REPLACE_WITH:\n{diff_item['replace_with']}\n")
                if not args.quiet:
                    print(f"pak_core: Extracted {len(diff_data)} method diffs to {args.output}", file=sys.stderr)
            except IOError as e:
                 print(f"pak_core: Error writing diff file to {args.output}: {e}", file=sys.stderr)
                 return 1

        elif args.command == 'verify-diff':
            if not args.targets: parser.error("'verify-diff' command requires a diff file path.")
            success = MethodDiffManager.verify_diff_file(args.targets[0], quiet=args.quiet) # Pass quiet
            return 0 if success else 1

        elif args.command == 'apply-diff':
            if len(args.targets) < 2:
                parser.error("'apply-diff' command requires a diff file path and a target file/directory path.")

            diff_file = args.targets[0]
            target_path = args.targets[1]

            success = MethodDiffManager.apply_diff(diff_file, target_path, quiet=args.quiet) # Pass quiet
            return 0 if success else 1

        return 0

    except FileNotFoundError as e:
        print(f"pak_core: Error - File not found: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"pak_core: Error - Value error: {e}", file=sys.stderr)
        return 1
    except argparse.ArgumentError as e:
        print(f"pak_core: Argument Error - {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"pak_core: An unexpected error occurred: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1

if __name__ == "__main__":
    # This allows pak_core.py to be called directly if needed,
    # but pak4.sh is the primary interface that sets up Python path correctly.
    # If running directly, ensure other pak_* modules are in PYTHONPATH.
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    if SCRIPT_DIR not in sys.path:
        sys.path.insert(0, SCRIPT_DIR)

    sys.exit(main())
