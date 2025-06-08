#!/usr/bin/env python3
"""
Integration tests for pak4.py
Tests the main CLI functionality end-to-end by running pak4.py as a subprocess
"""

import os
import shutil
import subprocess
import tempfile
import json
from pathlib import Path

# Import pytest only if running with pytest
try:
    import pytest
except ImportError:
    pytest = None


class Pak4IntegrationTester:
    """Integration test class for pak4.py CLI functionality"""
    
    def __init__(self):
        self.test_dir = None
        self.pak4_path = Path(__file__).parent / "pak4.py"
        
    def setup_test_environment(self):
        """Create temporary test environment with sample files"""
        self.test_dir = Path(tempfile.mkdtemp(prefix="pak_core_test_"))
        
        # Create sample Python file
        python_file = self.test_dir / "calculator.py"
        python_file.write_text('''#!/usr/bin/env python3
"""
Simple calculator for testing pak_core.py
"""

class Calculator:
    def __init__(self):
        self.history = []
    
    def add(self, a, b):
        """Add two numbers"""
        result = a + b
        self.history.append(f"add({a}, {b}) = {result}")
        return result
    
    def subtract(self, a, b):
        """Subtract two numbers"""
        result = a - b
        self.history.append(f"subtract({a}, {b}) = {result}")
        return result
    
    def get_history(self):
        """Get calculation history"""
        return self.history.copy()

if __name__ == "__main__":
    calc = Calculator()
    print(calc.add(5, 3))
    print(calc.subtract(10, 4))
''')
        
        # Create sample JavaScript file
        js_file = self.test_dir / "utils.js"
        js_file.write_text('''/**
 * Utility functions for testing pak_core.py
 */

function greet(name) {
    return `Hello, ${name}!`;
}

function formatDate(date) {
    return date.toISOString().split('T')[0];
}

module.exports = { greet, formatDate };
''')
        
        # Create sample markdown file
        md_file = self.test_dir / "README.md"
        md_file.write_text('''# Test Project

This is a test project for pak_core.py integration tests.

## Features

- Calculator functionality
- Utility functions
- Documentation

## Usage

Run the calculator or use utility functions as needed.
''')
        
        # Create subdirectory with more files
        subdir = self.test_dir / "lib"
        subdir.mkdir()
        
        config_file = subdir / "config.json"
        config_file.write_text('{"version": "1.0.0", "debug": false}')
        
        return self.test_dir
    
    def cleanup_test_environment(self):
        """Clean up temporary test directory"""
        if self.test_dir and self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def run_pak4(self, args, input_data=None):
        """Run pak4.py with given arguments and return result"""
        cmd = ["python3", str(self.pak4_path)] + args
        
        try:
            result = subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.test_dir
            )
            return {
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'success': result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': 'Command timed out',
                'success': False
            }
        except Exception as e:
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': str(e),
                'success': False
            }


# Only define pytest fixtures if pytest is available
if pytest:
    @pytest.fixture
    def pak_tester():
        """Fixture that provides a Pak4IntegrationTester instance"""
        tester = Pak4IntegrationTester()
        tester.setup_test_environment()
        yield tester
        tester.cleanup_test_environment()


def test_pak_core_pack_basic(pak_tester):
    """Test basic pack functionality"""
    # Pack all files with no compression
    result = pak_tester.run_pak4(['pack', '.', '-c', 'none', '-o', 'test.pak'])
    
    assert result['success'], f"Pack failed: {result['stderr']}"
    
    # Verify archive was created
    archive_path = pak_tester.test_dir / "test.pak"
    assert archive_path.exists(), "Archive file was not created"
    
    # Verify it's valid JSON
    archive_content = archive_path.read_text()
    archive_data = json.loads(archive_content)
    
    assert 'metadata' in archive_data
    assert 'files' in archive_data
    assert len(archive_data['files']) > 0
    
    # Check that our test files are included
    file_paths = [f['path'] for f in archive_data['files']]
    assert 'calculator.py' in file_paths
    assert 'utils.js' in file_paths
    assert 'README.md' in file_paths


def test_pak_core_pack_with_compression_levels(pak_tester):
    """Test pack with different compression levels"""
    compression_levels = ['none', 'light', 'medium', 'aggressive']
    
    for level in compression_levels:
        output_file = f"test_{level}.pak"
        result = pak_tester.run_pak4(['pack', '.', '-c', level, '-o', output_file])
        
        assert result['success'], f"Pack with {level} compression failed: {result['stderr']}"
        
        archive_path = pak_tester.test_dir / output_file
        assert archive_path.exists(), f"Archive for {level} compression not created"
        
        # Verify it's valid JSON
        archive_content = archive_path.read_text()
        archive_data = json.loads(archive_content)
        
        assert archive_data['metadata']['compression_level_setting'] == level


def test_pak_core_pack_with_extensions_filter(pak_tester):
    """Test pack with file extension filtering"""
    # Pack only Python files
    result = pak_tester.run_pak4(['pack', '.', '--ext', '.py', '-o', 'python_only.pak'])
    
    assert result['success'], f"Pack with extension filter failed: {result['stderr']}"
    
    archive_path = pak_tester.test_dir / "python_only.pak"
    archive_content = archive_path.read_text()
    archive_data = json.loads(archive_content)
    
    # Should only contain Python files
    file_paths = [f['path'] for f in archive_data['files']]
    python_files = [path for path in file_paths if path.endswith('.py')]
    
    assert len(python_files) > 0, "No Python files found in filtered archive"
    assert all(path.endswith('.py') for path in file_paths), "Non-Python files found in filtered archive"


def test_pak_core_pack_with_max_tokens(pak_tester):
    """Test pack with token limit"""
    result = pak_tester.run_pak4(['pack', '.', '-m', '1000', '-o', 'limited.pak'])
    
    assert result['success'], f"Pack with token limit failed: {result['stderr']}"
    
    archive_path = pak_tester.test_dir / "limited.pak"
    archive_content = archive_path.read_text()
    archive_data = json.loads(archive_content)
    
    # Check that token limit was respected
    estimated_tokens = archive_data['metadata']['total_estimated_tokens']
    assert estimated_tokens <= 1000, f"Token limit exceeded: {estimated_tokens} > 1000"


def test_pak_core_list_archive(pak_tester):
    """Test list functionality"""
    # First create an archive
    pak_tester.run_pak4(['pack', '.', '-o', 'test.pak'])
    
    # List archive contents
    result = pak_tester.run_pak4(['list', 'test.pak'])
    
    assert result['success'], f"List failed: {result['stderr']}"
    
    # Check that file paths are listed
    assert 'calculator.py' in result['stdout']
    assert 'utils.js' in result['stdout']
    assert 'README.md' in result['stdout']


def test_pak_core_list_detailed(pak_tester):
    """Test detailed list functionality"""
    # First create an archive
    pak_tester.run_pak4(['pack', '.', '-o', 'test.pak'])
    
    # List archive contents with details
    result = pak_tester.run_pak4(['list-detailed', 'test.pak'])
    
    assert result['success'], f"List-detailed failed: {result['stderr']}"
    
    # Should contain metadata and file details
    assert 'Files in archive:' in result['stdout'] or 'calculator.py' in result['stdout']


def test_pak_core_verify_archive(pak_tester):
    """Test verify functionality"""
    # First create an archive
    pak_tester.run_pak4(['pack', '.', '-o', 'test.pak'])
    
    # Verify archive
    result = pak_tester.run_pak4(['verify', 'test.pak'])
    
    assert result['success'], f"Verify failed: {result['stderr']}"


def test_pak_core_extract_archive(pak_tester):
    """Test extract functionality"""
    # First create an archive
    pak_tester.run_pak4(['pack', '.', '-o', 'test.pak'])
    
    # Create extraction directory
    extract_dir = pak_tester.test_dir / "extracted"
    extract_dir.mkdir()
    
    # Extract archive
    result = pak_tester.run_pak4(['extract', 'test.pak', '-d', str(extract_dir)])
    
    assert result['success'], f"Extract failed: {result['stderr']}"
    
    # Verify extracted files exist
    assert (extract_dir / 'calculator.py').exists()
    assert (extract_dir / 'utils.js').exists()
    assert (extract_dir / 'README.md').exists()
    
    # Verify content matches original
    original_content = (pak_tester.test_dir / 'calculator.py').read_text()
    extracted_content = (extract_dir / 'calculator.py').read_text()
    assert original_content == extracted_content


def test_pak_core_extract_with_pattern(pak_tester):
    """Test extract with pattern filtering"""
    # First create an archive
    pak_tester.run_pak4(['pack', '.', '-o', 'test.pak'])
    
    # Create extraction directory
    extract_dir = pak_tester.test_dir / "extracted_filtered"
    extract_dir.mkdir()
    
    # Extract only Python files
    result = pak_tester.run_pak4(['extract', 'test.pak', '-d', str(extract_dir), '-p', '.*\\.py$'])
    
    assert result['success'], f"Extract with pattern failed: {result['stderr']}"
    
    # Should only extract Python files
    assert (extract_dir / 'calculator.py').exists()
    assert not (extract_dir / 'utils.js').exists()
    assert not (extract_dir / 'README.md').exists()


def test_pak_core_extract_diff(pak_tester):
    """Test extract-diff functionality"""
    # Create two versions of a file
    original_file = pak_tester.test_dir / "original.py"
    modified_file = pak_tester.test_dir / "modified.py"
    
    original_file.write_text('''def hello():
    print("Hello World")

def add(a, b):
    return a + b
''')
    
    modified_file.write_text('''def hello():
    print("Hello Universe!")

def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
''')
    
    # Extract diff
    result = pak_tester.run_pak4(['extract-diff', str(original_file), str(modified_file), '-o', 'changes.diff'])
    
    assert result['success'], f"Extract-diff failed: {result['stderr']}"
    
    # Verify diff file was created
    diff_path = pak_tester.test_dir / "changes.diff"
    assert diff_path.exists(), "Diff file was not created"
    
    # Verify diff content contains expected changes
    diff_content = diff_path.read_text()
    assert 'FILE:' in diff_content
    assert 'FIND_METHOD:' in diff_content or 'REPLACE_WITH:' in diff_content


def test_pak_core_verify_diff(pak_tester):
    """Test verify-diff functionality"""
    # Create a valid diff file
    diff_file = pak_tester.test_dir / "test.diff"
    diff_file.write_text('''FILE: test.py
FIND_METHOD: def hello()
UNTIL_EXCLUDE: def add(a, b):
REPLACE_WITH:
def hello():
    print("Hello Test!")
''')
    
    # Verify diff
    result = pak_tester.run_pak4(['verify-diff', str(diff_file)])
    
    assert result['success'], f"Verify-diff failed: {result['stderr']}"


def test_pak_core_error_handling(pak_tester):
    """Test error handling for invalid inputs"""
    # Test with non-existent archive
    result = pak_tester.run_pak4(['list', 'non_existent.pak'])
    assert not result['success'], "Should fail with non-existent archive"
    
    # Test with invalid compression level
    result = pak_tester.run_pak4(['pack', '.', '-c', 'invalid'])
    assert not result['success'], "Should fail with invalid compression level"
    
    # Test pack with non-existent directory
    result = pak_tester.run_pak4(['pack', 'non_existent_dir'])
    assert not result['success'], "Should fail with non-existent directory"


def test_pak_core_quiet_mode(pak_tester):
    """Test quiet mode functionality"""
    # Pack with quiet mode
    result = pak_tester.run_pak4(['pack', '.', '-q', '-o', 'quiet_test.pak'])
    
    assert result['success'], f"Pack in quiet mode failed: {result['stderr']}"
    
    # In quiet mode, stdout should only contain the archive or minimal output
    # stderr should be minimal (no informational messages)
    assert len(result['stderr']) == 0 or 'error' not in result['stderr'].lower()


if __name__ == "__main__":
    # For manual testing
    tester = Pak4IntegrationTester()
    tester.setup_test_environment()
    
    print("🧪 Running pak_core.py integration tests manually...")
    
    try:
        # Test basic pack
        print("📦 Testing basic pack...")
        result = tester.run_pak4(['pack', '.', '-o', 'manual_test.pak'])
        print(f"   Pack result: {'✅ Success' if result['success'] else '❌ Failed'}")
        if not result['success']:
            print(f"   Error: {result['stderr']}")
        
        # Test list
        print("📋 Testing list...")
        result = tester.run_pak4(['list', 'manual_test.pak'])
        print(f"   List result: {'✅ Success' if result['success'] else '❌ Failed'}")
        if result['success']:
            print(f"   Files found: {len(result['stdout'].splitlines())}")
        
        print("✅ Manual integration tests completed!")
        
    finally:
        tester.cleanup_test_environment()