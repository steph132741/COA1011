"""
REFACTOR PHASE - Improve filename validation
Add better error handling and edge cases
"""

import unittest
import re
from typing import Optional

class ClinicalDataValidatorRefactored:
    """Refactored implementation with better design"""
    
    # Class constant for pattern - easier to maintain
    FILENAME_PATTERN = r'^CLINICALDATA\d{14}\.CSV$'
    
    def __init__(self, download_dir, archive_dir, error_dir):
        # Compile pattern once for performance
        self.filename_regex = re.compile(self.FILENAME_PATTERN, re.IGNORECASE)
    
    def _validate_filename_pattern(self, filename, status_queue=None):
        """
        Refactored: Validate filename with better error handling
        
        Args:
            filename: Filename to validate
            status_queue: Optional list to collect status messages
            
        Returns:
            bool: True if filename matches pattern
        """
        # FIX 1: Handle non-string input
        if not isinstance(filename, str):
            if status_queue is not None:
                status_queue.append("Filename must be a string")
            return False
        
        # FIX 2: Handle empty filename
        if not filename:
            if status_queue is not None:
                status_queue.append("Filename cannot be empty")
            return False
        
        # Check pattern
        is_valid = bool(self.filename_regex.match(filename))
        
        # FIX 3: Actually add messages to status_queue if provided
        if status_queue is not None:
            if is_valid:
                status_queue.append(f"Filename '{filename}' is valid")
            else:
                status_queue.append(f"Filename '{filename}' doesn't match pattern: CLINICALDATAYYYYMMDDHHMMSS.CSV")
        
        return is_valid
    
class TestFilenameValidationRefactored(unittest.TestCase):
    """REFACTOR PHASE TESTS - Improved filename validation"""
    
    def setUp(self):
        self.validator = ClinicalDataValidatorRefactored("download", "archive", "errors")
    
    def test_01_valid_filename_exact_format(self):
        filename = "CLINICALDATA20250101120000.CSV"
        result = self.validator._validate_filename_pattern(filename)
        self.assertTrue(result, "Exact format filename should be valid")
    
    def test_02_valid_filename_lowercase_extension(self):
        filename = "CLINICALDATA20250101120000.csv"
        result = self.validator._validate_filename_pattern(filename)
        self.assertTrue(result, "Lowercase extension should be valid")
    
    def test_03_invalid_wrong_prefix(self):
        filename = "CLINICAL-DATA20250101120000.CSV"
        result = self.validator._validate_filename_pattern(filename)
        self.assertFalse(result, "Wrong prefix should be invalid")
    
    def test_04_invalid_short_timestamp(self):
        filename = "CLINICALDATA20250101.CSV"
        result = self.validator._validate_filename_pattern(filename)
        self.assertFalse(result, "Short timestamp should be invalid")
    
    def test_05_invalid_wrong_extension(self):
        filename = "CLINICALDATA20250101120000.TXT"
        result = self.validator._validate_filename_pattern(filename)
        self.assertFalse(result, "Wrong extension should be invalid")
    
    def test_06_invalid_no_extension(self):
        filename = "CLINICALDATA20250101120000"
        result = self.validator._validate_filename_pattern(filename)
        self.assertFalse(result, "Missing extension should be invalid")
    
    def test_07_invalid_empty_filename(self):
        filename = ""
        result = self.validator._validate_filename_pattern(filename)
        self.assertFalse(result, "Empty filename should be invalid")
    
    def test_08_invalid_only_prefix(self):
        filename = "CLINICALDATA.CSV"
        result = self.validator._validate_filename_pattern(filename)
        self.assertFalse(result, "Only prefix should be invalid")
    
    def test_09_valid_future_timestamp(self):
        filename = "CLINICALDATA20351231115959.CSV"
        result = self.validator._validate_filename_pattern(filename)
        self.assertTrue(result, "Future timestamp should be valid")
    
    def test_10_status_queue_messages(self):
        """New test: Check status queue messages"""
        status_queue = []
        filename = "CLINICALDATA20250101120000.CSV"
        result = self.validator._validate_filename_pattern(filename, status_queue)
        
        self.assertTrue(result)
        self.assertEqual(len(status_queue), 1)
        self.assertIn("is valid", status_queue[0])
    
    def test_11_status_queue_error_messages(self):
        """New test: Error messages in status queue"""
        status_queue = []
        filename = "WRONGFILE.CSV"
        result = self.validator._validate_filename_pattern(filename, status_queue)
        
        self.assertFalse(result)
        self.assertEqual(len(status_queue), 1)
        self.assertIn("doesn't match pattern", status_queue[0])
    
    def test_12_non_string_input(self):
        """New test: Non-string input should fail gracefully"""
        status_queue = []
        filename = 12345  # Not a string
        result = self.validator._validate_filename_pattern(filename, status_queue)
        
        self.assertFalse(result)
        self.assertIn("must be a string", status_queue[0])
    
    def test_13_unicode_filename(self):
        """New test: Unicode characters should fail"""
        filename = "CLINICALDATA20250101120000.CSV©"
        result = self.validator._validate_filename_pattern(filename)
        self.assertFalse(result, "Unicode characters should be invalid")
    
    def test_14_spaces_in_filename(self):
        """New test: Spaces should fail"""
        filename = "CLINICALDATA 20250101120000.CSV"
        result = self.validator._validate_filename_pattern(filename)
        self.assertFalse(result, "Spaces should be invalid")

if __name__ == '__main__':
    print("=" * 60)
    print("REFACTOR PHASE - Improved Filename Validation")
    print("Expected: All tests PASS with refactored implementation")
    print("=" * 60)
    unittest.main(verbosity=2)