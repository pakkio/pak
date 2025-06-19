"""
pak.py - LLM-enhanced file archiver with semantic compression and method diff support.
Main CLI entry point for all pak operations.
"""
# import tiktoken
# For now, tiktoken is disabled/faked. We assume 3 chars = 1 token.
# try:
#     tiktoken.get_encoding("cl100k_base")
# except Exception as e:
#     print(f"pak: Warning: cl100k_base encoding not available: {e}", file=sys.stderr, flush=True)

import argparse
import datetime
import os
import re
import sys
from pathlib import Path

# Import from local modules
from pak_utils import collect_files
from pak_analyzer import PythonAnalyzer 
from pak_compressor import Compressor, CacheManager
from pak_differ import MethodDiffManager
from pak_archive_manager import PakArchive

VERSION = "5.0.0"

def check_dependencies(quiet=False):
    """Check for required dependencies and configuration."""
    missing_deps = []
    
    # Check for .env file for semantic compression
    env_files = [".env", Path(__file__).parent / ".env"]
    env_found = any(f.exists() if isinstance(f, Path) else os.path.exists(f) for f in env_files)
    
    if not env_found and not quiet:
        print("pak: Warning: No .env file found. Please copy .env.sample to .env and configure.", file=sys.stderr)
        print("pak: Semantic compression (level 4) requires OPENROUTER_API_KEY.", file=sys.stderr)
    
    # Check Python dependencies for semantic compression
    try:
        import requests
        import dotenv
    except ImportError:
        if not quiet:
            print("pak: Warning: Missing Python dependencies for semantic compression.", file=sys.stderr)
            print("pak: Install with: pip install requests python-dotenv", file=sys.stderr)
            print("pak: Falling back to AST/aggressive compression when semantic is requested.", file=sys.stderr)
    
    return len(missing_deps) == 0

def load_env():
    """Load environment variables from .env file."""
    try:
        from dotenv import load_dotenv
        
        # Try current directory first, then script directory
        script_dir = Path(__file__).parent
        env_paths = [
            Path.cwd() / ".env",  # Current working directory
            script_dir / ".env"   # pak.py script directory
        ]
        
        for env_path in env_paths:
            if env_path.exists():
                load_dotenv(env_path)
                if os.environ.get('PAK_DEBUG') == 'true':
                    print(f"pak: Loaded .env from {env_path}", file=sys.stderr)
                break
        else:
            if os.environ.get('PAK_DEBUG') == 'true':
                print(f"pak: No .env file found in {[str(p) for p in env_paths]}", file=sys.stderr)
                
    except ImportError:
        pass  # dotenv not available, skip

def test_llm_connection():
    """Test LLM connection for semantic compression."""
    try:
        import sys
        script_dir = Path(__file__).parent
        sys.path.insert(0, str(script_dir))
        from llm_wrapper import test_llm_connection
        return test_llm_connection()
    except Exception:
        return False

def auto_output_name(targets, compression_level="medium"):
    """Generate automatic output filename based on targets and compression level."""
    base_name = "archive"
    
    if len(targets) == 1 and os.path.isdir(targets[0]):
        base_name = os.path.basename(os.path.abspath(targets[0]))
        if base_name == "." or not base_name:
            base_name = os.path.basename(os.getcwd())
    elif targets:
        base_name = os.path.basename(targets[0]).split('.')[0] + "_collection"
    
    # Add compression suffix
    suffix_map = {
        "semantic": "_semantic",
        "smart": "_smart", 
        "aggressive": "_min",
        "medium": "_med",
        "light": "_light"
    }
    
    suffix = suffix_map.get(compression_level, "")
    return f"{base_name}{suffix}.pak"

def normalize_compression_level(level):
    """Normalize compression level input to standard names."""
    level_map = {
        '0': 'none', 'none': 'none',
        '1': 'light', 'light': 'light',
        '2': 'medium', 'medium': 'medium', 
        '3': 'aggressive', 'aggressive': 'aggressive',
        '4': 'semantic', 'semantic': 'semantic',
        's': 'smart', 'S': 'smart', 'smart': 'smart'
    }
    
    normalized = level_map.get(level)
    if normalized is None:
        raise ValueError(f"Invalid compression level '{level}'. Use 0-4, s, or full names.")
    return normalized

def normalize_extensions(ext_list):
    """Normalize file extensions from various input formats."""
    normalized = []
    if not ext_list:
        return normalized
        
    for ext_item in ext_list:
        # Handle comma-separated extensions like "py,md,js"
        for single_ext in re.split(r'[,\s]+', ext_item):
            if single_ext:
                if not single_ext.startswith('.'):
                    normalized.append('.' + single_ext.lower())
                else:
                    normalized.append(single_ext.lower())
    
    return list(set(normalized))

def show_usage():
    """Show comprehensive usage information."""
    print(f"""pak v{VERSION} - LLM-enhanced file archiver with semantic compression + METHOD DIFF SUPPORT

USAGE:
  pak [targets] [options]                     # Pack (default)
  pak -l archive.pak [-p regex]              # List contents (with optional pattern filter)
  pak -ll archive.pak [-p regex]             # List with content preview
  pak -x archive.pak [-d outdir] [-p regex]  # Extract (with optional pattern filter)
  pak -v archive.pak                         # Verify archive integrity

  METHOD DIFF COMMANDS:
  pak --diff file1.py file2.py [...] -o changes.diff  # Extract method-level diff
  pak -vd changes.diff                               # Verify method diff file syntax
  pak -ad changes.diff target_dir_or_file            # Apply method diff to files

TARGETS:
  .                    Current directory
  src/ lib/            Specific directories
  main.py readme.md    Specific files
  pak_core*            GLOB PATTERNS
  *.py                 All Python files in current dir
  src/**/*.js          All JS files in src/ recursively (zsh/bash 4.0+)

PACK OPTIONS:
  -t ext1,ext2         Extensions (py,md,js,ts,cpp,h,go,rs,java). Separated by comma.
       Example: -t py,md or -t "py,md,js"
  -c LEVEL             Compression: 0=none, 1=light, 2=medium, 3=aggressive, 4=semantic, s=smart.
       Example: -c 2 or -c 4 or -c semantic
  -m NUM               Max tokens (0=unlimited). Example: -m 8000
  -j NUM               Parallel workers (1-5, default: 1). Use 2-3 for semantic compression.
       Example: -j 3
  -o FILE              Output file (default: stdout or auto-generated if stdout is a TTY).
       Example: -o project.pak
  -q                   Quiet mode.

EXTRACT/LIST OPTIONS:
  -p PATTERN           Filter files matching regex pattern (applied to full path).
  -d DIR               (Extract only) Extract to specific directory.

METHOD DIFF OPTIONS:
  --diff               Extract method-level differences between files
  -vd                  Verify method diff file syntax
  -ad                  Apply method diff to target files
  -o FILE              Output file for method diff extraction

EXAMPLES:
  # Modern pak usage
  pak . -t py,md -c 4                        # Semantic compression, Python+Markdown
  pak src/ -c s -m 8000 -o project.pak      # Smart mode, 8k token limit
  pak . -c semantic -j 3 -o project.pak     # Semantic with 3 parallel workers
  
  # Legacy syntax (backward compatible)
  pak --compress-level smart --max-tokens 8000 src/  # Legacy format
  pak --ext .py .md --compress-level semantic .      # Legacy extensions

  # Method diff workflow
  pak --diff original.py modified.py -o changes.diff
  pak -vd changes.diff
  pak -ad changes.diff target_project/target_file.py

COMPRESSION LEVELS:
  0/none      : Raw content
  1/light     : Basic whitespace/empty line removal
  2/medium    : Light + comment removal (pak3 compatible)
  3/aggressive: AST-based structure extraction
  4/semantic  : LLM-based semantic compression
  s/smart     : Adaptive compression with semantic fallback
""")

def parse_legacy_args(args):
    """Parse legacy bash pak arguments for backward compatibility."""
    # Convert legacy arguments to new format
    converted_args = []
    i = 0
    
    while i < len(args):
        arg = args[i]
        
        # Legacy compression level
        if arg == '--compress-level':
            if i + 1 < len(args):
                converted_args.extend(['-c', args[i + 1]])
                i += 2
            else:
                converted_args.append(arg)  # Let argparse handle the error
                i += 1
        
        # Legacy max tokens
        elif arg == '--max-tokens':
            if i + 1 < len(args):
                converted_args.extend(['-m', args[i + 1]])
                i += 2
            else:
                converted_args.append(arg)  # Let argparse handle the error
                i += 1
        
        # Legacy commands
        elif arg == '--pack':
            # --pack is implicit in new format, skip it
            i += 1
        elif arg == '--ls':
            converted_args.append('-l')
            i += 1
        elif arg == '--unpack':
            converted_args.append('-x')
            i += 1
        elif arg == '--verify':
            converted_args.append('-v')
            i += 1
        
        # Legacy outdir
        elif arg == '--outdir':
            if i + 1 < len(args):
                converted_args.extend(['-d', args[i + 1]])
                i += 2
            else:
                converted_args.append(arg)  # Let argparse handle the error
                i += 1
        
        # Legacy ext handling (can take multiple values)
        elif arg == '--ext':
            i += 1
            ext_values = []
            # Collect all extension values until next -- option or end
            while i < len(args) and not args[i].startswith('--'):
                ext_values.append(args[i])
                i += 1
            if ext_values:
                converted_args.extend(['-t', ','.join(ext_values)])
        
        # All other arguments pass through unchanged
        else:
            converted_args.append(arg)
            i += 1
    
    return converted_args

def main():
    # Initialize environment
    load_env()
    
    # Handle legacy argument conversion
    original_args = sys.argv[1:]
    converted_args = parse_legacy_args(original_args)
    
    parser = argparse.ArgumentParser(
        description=f"pak v{VERSION} - LLM-enhanced file archiver with semantic compression + METHOD DIFF SUPPORT",
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False  # We'll add custom help
    )

    # Positional arguments (targets)
    parser.add_argument('targets', nargs='*',
                        help="Target files, directories, or glob patterns")

    # Main action flags (mutually exclusive)
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument('-l', '--list', action='store_true',
                              help='List archive contents')
    action_group.add_argument('-ll', '--list-detailed', action='store_true', 
                              help='List archive contents with details')
    action_group.add_argument('-x', '--extract', action='store_true',
                              help='Extract archive')
    action_group.add_argument('-v', '--verify', action='store_true',
                              help='Verify archive integrity')
    action_group.add_argument('--diff', action='store_true',
                              help='Extract method-level differences')
    action_group.add_argument('-vd', '--verify-diff', action='store_true',
                              help='Verify method diff file')
    action_group.add_argument('-ad', '--apply-diff', action='store_true', 
                              help='Apply method diff to files')

    # Compression options
    parser.add_argument('-c', '--compression-level', default='medium',
                        help='Compression level: 0/none, 1/light, 2/medium, 3/aggressive, 4/semantic, s/smart')
    parser.add_argument('-m', '--max-tokens', type=int, default=0,
                        help='Max total estimated tokens (0=unlimited)')
    parser.add_argument('-t', '--types', '--ext',
                        help='File extensions (comma-separated): py,md,js')
    parser.add_argument('-j', '--parallel', type=int, default=1, metavar='N',
                        help='Number of parallel workers for compression (default: 1, max recommended: 3)')
    
    # Output options
    parser.add_argument('-o', '--output', 
                        help='Output file for pack/diff operations')
    parser.add_argument('-d', '--outdir', default='.',
                        help='Output directory for extract')
    parser.add_argument('-p', '--pattern',
                        help='Regex pattern to filter files')
    
    # General options
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Suppress informational messages')
    parser.add_argument('-h', '--help', action='store_true',
                        help='Show this help message')
    parser.add_argument('--version', action='store_true',
                        help='Show version information')

    args = parser.parse_args(converted_args)

    # Handle help and version
    if args.help:
        show_usage()
        return 0
    
    if args.version:
        print(f"pak v{VERSION}")
        return 0

    # Check dependencies
    check_dependencies(args.quiet)

    # Determine command
    command = 'pack'  # default
    if args.list:
        command = 'list'
    elif args.list_detailed:
        command = 'list-detailed'
    elif args.extract:
        command = 'extract'
    elif args.verify:
        command = 'verify'
    elif args.diff:
        command = 'extract-diff'
    elif args.verify_diff:
        command = 'verify-diff'
    elif args.apply_diff:
        command = 'apply-diff'

    # Normalize compression level
    try:
        compression_level = normalize_compression_level(args.compression_level)
    except ValueError as e:
        print(f"pak: Error: {e}", file=sys.stderr)
        return 1

    # Normalize extensions
    extensions = []
    if args.types:
        extensions = normalize_extensions([args.types])

    # Test semantic compression if needed
    if command == 'pack' and compression_level == 'semantic':
        if os.environ.get('PAK_DEBUG') == 'true' and not args.quiet:
            print("pak: Testing LLM connection for semantic compression...", file=sys.stderr)
        
        if not test_llm_connection():
            if not args.quiet:
                print("pak: Semantic compression requested but LLM unavailable. Falling back to aggressive.", file=sys.stderr)
            compression_level = 'aggressive'

    # Set environment variable for semantic compressor path
    script_dir = Path(__file__).parent
    os.environ['SEMANTIC_COMPRESSOR_PATH'] = str(script_dir / 'semantic_compressor.py')

    try:
        # Execute the determined command
        if command == 'pack':
            return execute_pack_command(args, compression_level, extensions)
        elif command in ['list', 'list-detailed']:
            return execute_list_command(args, command)
        elif command == 'extract':
            return execute_extract_command(args)
        elif command == 'verify':
            return execute_verify_command(args)
        elif command == 'extract-diff':
            return execute_diff_command(args)
        elif command == 'verify-diff':
            return execute_verify_diff_command(args)
        elif command == 'apply-diff':
            return execute_apply_diff_command(args)
        else:
            print(f"pak: Error: Unknown command '{command}'", file=sys.stderr)
            return 1

    except FileNotFoundError as e:
        print(f"pak: Error - File not found: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"pak: Error - Value error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(f"\npak: Operation cancelled by user", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"pak: Unexpected error: {e}", file=sys.stderr)
        return 1

def execute_pack_command(args, compression_level, extensions):
    """Execute pack command."""
    targets = args.targets if args.targets else ['.']
    
    if os.environ.get('PAK_DEBUG') == 'true' and not args.quiet:
        print(f"pak: DEBUG: Final targets for pack: {targets}", file=sys.stderr)
    
    collected_files = collect_files(targets, extensions, args.quiet)
    
    # Auto-generate output name if needed
    output_path = args.output
    if not output_path and sys.stdout.isatty():
        output_path = auto_output_name(targets, compression_level)
        if not args.quiet:
            print(f"pak: Auto-generated output file: {output_path}", file=sys.stderr)
    
    if not collected_files:
        if not args.quiet:
            print("pak: No files found matching targets and extension filters.", file=sys.stderr)
        return 0
    
    # Create archive
    pak = PakArchive(compression_level, args.max_tokens, args.quiet)
    # Always create cache manager for semantic compression to avoid repeated LLM calls
    cache_identifier = output_path if output_path else f"stdout_{hash(tuple(collected_files))}"
    cache_mgr = CacheManager(cache_identifier, args.quiet)
    pak.set_cache_manager(cache_mgr)
    
    # Validate parallel workers setting
    max_workers = max(1, min(args.parallel, 5))  # Clamp between 1-5 for safety
    if args.parallel != max_workers and not args.quiet:
        print(f"pak: Parallel workers clamped to {max_workers} (requested: {args.parallel})", file=sys.stderr)
    
    # Choose processing method based on file count and parallel setting
    if len(collected_files) > 1 and max_workers > 1:
        if not args.quiet:
            print(f"pak: Processing {len(collected_files)} files with {max_workers} parallel workers", file=sys.stderr)
        
        # Collect all file data for batch processing
        file_data_list = []
        for file_path in collected_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                file_data_list.append((file_path, content, 0))  # importance = 0 for all
            except Exception as e:
                if not args.quiet:
                    print(f"pak: Warning: Could not read file {file_path}: {e}", file=sys.stderr)
        
        # Process files in parallel
        pak.add_files_parallel(file_data_list, max_workers=max_workers)
    else:
        # Sequential processing (original behavior)
        if not args.quiet and len(collected_files) > 1:
            print(f"pak: Processing {len(collected_files)} files sequentially", file=sys.stderr)
        
        for file_path in collected_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                pak.add_file(file_path, content)
            except Exception as e:
                if not args.quiet:
                    print(f"pak: Warning: Could not read file {file_path}: {e}", file=sys.stderr)
    
    archive_output = pak.create_archive(output_path)
    if archive_output:
        print(archive_output)
    
    return 0

def execute_list_command(args, command):
    """Execute list or list-detailed command."""
    if not args.targets:
        print("pak: Error: No archive file specified for listing.", file=sys.stderr)
        return 1
    
    archive_file = args.targets[0]
    detailed = (command == 'list-detailed')
    
    PakArchive.list_archive(archive_file, detailed=detailed, 
                           file_path_pattern=args.pattern, quiet=args.quiet)
    return 0

def execute_extract_command(args):
    """Execute extract command."""
    if not args.targets:
        print("pak: Error: No archive file specified for extraction.", file=sys.stderr)
        return 1
    
    archive_file = args.targets[0]
    PakArchive.extract_archive(archive_file, args.outdir, args.pattern, args.quiet)
    return 0

def execute_verify_command(args):
    """Execute verify command."""
    if not args.targets:
        print("pak: Error: No archive file specified for verification.", file=sys.stderr)
        return 1
    
    archive_file = args.targets[0] 
    success = PakArchive.verify_archive(archive_file, args.quiet)
    return 0 if success else 1

def execute_diff_command(args):
    """Execute extract-diff command."""
    if len(args.targets) < 2:
        print("pak: Error: extract-diff requires at least two files.", file=sys.stderr)
        return 1
    
    output_file = args.output
    if not output_file and sys.stdout.isatty():
        output_file = "changes.diff"
        if not args.quiet:
            print(f"pak: Auto-generated diff output file: {output_file}", file=sys.stderr)
    elif not output_file:
        print("pak: Error: extract-diff requires --output when not writing to stdout.", file=sys.stderr)
        return 1
    
    diff_data = MethodDiffManager.extract_diff(args.targets, quiet=args.quiet)
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for diff_item in diff_data:
                f.write(f"FILE: {diff_item['file']}\n")
                f.write(f"FIND_METHOD: {diff_item['find_method']}\n")
                f.write(f"UNTIL_EXCLUDE: {diff_item['until_exclude']}\n")
                f.write(f"REPLACE_WITH:\n{diff_item['replace_with']}\n")
        
        if not args.quiet:
            print(f"pak: Extracted {len(diff_data)} method diffs to {output_file}", file=sys.stderr)
        return 0
    except IOError as e:
        print(f"pak: Error writing diff file to {output_file}: {e}", file=sys.stderr)
        return 1

def execute_verify_diff_command(args):
    """Execute verify-diff command."""
    if not args.targets:
        print("pak: Error: No diff file specified for verification.", file=sys.stderr)
        return 1
    
    diff_file = args.targets[0]
    success = MethodDiffManager.verify_diff_file(diff_file, quiet=args.quiet)
    return 0 if success else 1

def execute_apply_diff_command(args):
    """Execute apply-diff command."""
    if len(args.targets) < 2:
        print("pak: Error: apply-diff requires a diff file and target path.", file=sys.stderr)
        return 1
    
    diff_file = args.targets[0]
    target_path = args.targets[1]

    # Output pak file logic is now bypassed
    output_pak = args.output if hasattr(args, 'output') and args.output else None
    if not output_pak and sys.stdout.isatty():
        if not args.quiet:
            print(f"pak: Note: Output pak file generation for applied diffs is currently bypassed by this fix.", file=sys.stderr)

    # Apply the diff to the target path (file or directory)
    success = MethodDiffManager.apply_diff(diff_file, target_path, quiet=args.quiet)
    if not success:
        if not args.quiet:
            print("pak: Warning: Diff application reported no successful changes or an error occurred.", file=sys.stderr)
        return 1
    else:
        if not args.quiet:
            print(f"pak: Diff successfully applied. Target path '{target_path}' may have been modified.", file=sys.stderr)
            print(f"pak: NOTE: The feature to output a '_patched.pak' file is disabled with this modification.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
