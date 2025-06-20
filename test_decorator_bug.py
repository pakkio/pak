#!/usr/bin/env python3
"""
Test script to reproduce the decorator removal bug in pak method diff system.
"""

import os
import tempfile
from pak_differ import MethodDiffManager

def test_decorator_removal_bug():
    """Test case for decorator removal bug."""
    
    # Original code with decorator
    original_code = '''def hello():
    """Say hello to the world."""
    print("Hello World!")

@property
def get_name(self):
    """Get the name property."""
    return self._name

def goodbye():
    """Say goodbye."""
    print("Goodbye!")
'''

    # Modified code with decorator removed
    modified_code = '''def hello():
    """Say hello to the world."""
    print("Hello World!")

def get_name(self):
    """Get the name property without decorator."""
    return self._name

def goodbye():
    """Say goodbye."""
    print("Goodbye!")
'''

    # Target code (same as original)
    target_code = '''def hello():
    """Say hello to the world."""
    print("Hello World!")

@property
def get_name(self):
    """Get the name property."""
    return self._name

def goodbye():
    """Say goodbye."""
    print("Goodbye!")
'''

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create files
        orig_file = os.path.join(temp_dir, "original.py")
        mod_file = os.path.join(temp_dir, "modified.py")
        target_file = os.path.join(temp_dir, "target.py")
        diff_file = os.path.join(temp_dir, "test.diff")
        
        with open(orig_file, 'w') as f:
            f.write(original_code)
        with open(mod_file, 'w') as f:
            f.write(modified_code)
        with open(target_file, 'w') as f:
            f.write(target_code)
        
        print("=== ORIGINAL CODE ===")
        print(original_code)
        print("\n=== MODIFIED CODE (decorator removed) ===")
        print(modified_code)
        print("\n=== TARGET CODE (same as original) ===")
        print(target_code)
        
        # Generate diff
        print("\n=== GENERATING DIFF ===")
        diff_instructions = MethodDiffManager.extract_diff([orig_file, mod_file], quiet=False)
        
        if diff_instructions:
            with open(diff_file, 'w') as f:
                for instruction in diff_instructions:
                    f.write(f"FILE: {instruction['file']}\n")
                    if instruction.get('find_method'):
                        f.write(f"FIND_METHOD: {instruction['find_method']}\n")
                    if instruction.get('until_exclude'):
                        f.write(f"UNTIL_EXCLUDE: {instruction['until_exclude']}\n")
                    f.write("REPLACE_WITH:\n")
                    if instruction.get('replace_with'):
                        for line in instruction['replace_with'].splitlines():
                            f.write(f"{line}\n")
                    f.write("\n")
            
            print(f"Generated diff with {len(diff_instructions)} instructions")
            
            # Show the diff content
            print("\n=== DIFF CONTENT ===")
            with open(diff_file, 'r') as f:
                print(f.read())
            
            # Apply diff
            print("\n=== APPLYING DIFF ===")
            success = MethodDiffManager.apply_diff(diff_file, target_file, quiet=False)
            
            # Check result
            print("\n=== RESULT AFTER APPLYING DIFF ===")
            with open(target_file, 'r') as f:
                result_code = f.read()
            print(result_code)
            
            # Analyze the result
            print("\n=== ANALYSIS ===")
            has_decorator_before = "@property" in target_code
            has_decorator_after = "@property" in result_code
            
            print(f"Had @property decorator before: {has_decorator_before}")
            print(f"Has @property decorator after: {has_decorator_after}")
            
            if has_decorator_before and has_decorator_after:
                print("❌ BUG CONFIRMED: Decorator was supposed to be removed but is still present!")
                
                # Check if decorator was duplicated
                decorator_count_before = target_code.count("@property")
                decorator_count_after = result_code.count("@property")
                print(f"@property count before: {decorator_count_before}")
                print(f"@property count after: {decorator_count_after}")
                
                if decorator_count_after > decorator_count_before:
                    print("❌ WORSE: Decorator was DUPLICATED instead of removed!")
                
            elif not has_decorator_before and not has_decorator_after:
                print("✅ No decorator to remove - test case invalid")
            elif has_decorator_before and not has_decorator_after:
                print("✅ Decorator successfully removed")
            else:
                print("❓ Unexpected state")
            
            return success
        else:
            print("No diff instructions generated")
            return False

if __name__ == "__main__":
    test_decorator_removal_bug()