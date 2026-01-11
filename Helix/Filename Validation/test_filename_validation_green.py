"""
GREEN PHASE - Implement filename validation
Simple implementation to make tests pass
"""

import unittest
import re

class ClinicalDataValidatorGreen:
    """Simple implementation for filename validation"""
    
    def __init__(self, download_dir, archive_dir, error_dir):
        # Not needed for filename validation
        pass
    
    def _validate_filename_pattern(self, filename, status_queue=None):
        """GREEN: Implement filename pattern validation"""
        # Pattern: CLINICALDATA + 14 digits + .CSV (case-insensitive)
        pattern = r'^CLINICALDATA\d{14}\.CSV$'
        is_valid = re.match(pattern, filename, re.IGNORECASE) is not None
        return is_valid

class TestFilenameValidationGreen(unittest.TestCase):
    """GREEN PHASE TESTS - Filename validation implemented"""
    
    def setUp(self):
        self.validator = ClinicalDataValidatorGreen("download", "archive", "errors")
    
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

if __name__ == '__main__':
    print("=" * 60)
    print("GREEN PHASE - Filename Validation Tests")
    print("Expected: All tests PASS with implementation")
    print("=" * 60)
    unittest.main(verbosity=2)