#!/usr/bin/env python3
"""
Simple CSV validation tests for Clinical Data Processor.
Beginner-friendly version.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
import csv
import sys
import os

# Add parent directory to path to import the main module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from helix import ClinicalDataValidator
except ImportError:
    print("Error: Could not import ClinicalDataValidator. Make sure helix.py is in the parent directory.")
    sys.exit(1)


class SimpleCSVTests(unittest.TestCase):
    
    def setUp(self):
        """Set up test directory"""
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_csv_"))
        self.download = self.test_dir / "download"
        self.archive = self.test_dir / "archive"
        self.errors = self.test_dir / "errors"
        
        # Create directories
        for dir_path in [self.download, self.archive, self.errors]:
            dir_path.mkdir(parents=True)
        
        # Create validator
        self.validator = ClinicalDataValidator(
            str(self.download),
            str(self.archive),
            str(self.errors)
        )
    
    def tearDown(self):
        """Clean up test directory"""
        shutil.rmtree(self.test_dir)
    
    def create_test_csv(self, filename, rows):
        """Helper to create a CSV file"""
        filepath = self.download / filename
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for row in rows:
                writer.writerow(row)
        return filepath
    
    def test_valid_filename(self):
        """Test valid filename passes"""
        result = self.validator._validate_filename_pattern("CLINICALDATA20250101120000.CSV")
        self.assertTrue(result)
    
    def test_invalid_filename(self):
        """Test invalid filename fails"""
        result = self.validator._validate_filename_pattern("wrongfile.csv")
        self.assertFalse(result)
    
    def test_perfect_csv(self):
        """Test perfect CSV passes validation"""
        rows = [
            ["PatientID", "TrialCode", "DrugCode", "Dosage_mg", "StartDate", "EndDate", "Outcome", "SideEffects", "Analyst"],
            ["P001", "TRIAL001", "DRUG001", "100", "2024-01-01", "2024-01-10", "Improved", "None", "Dr. Smith"],
        ]
        
        csv_file = self.create_test_csv("CLINICALDATA20250101120000.CSV", rows)
        
        is_valid, errors, count = self.validator._validate_csv_content(csv_file, status_queue=None)
        
        self.assertTrue(is_valid)
        self.assertEqual(count, 1)
        self.assertEqual(len(errors), 0)
    
    def test_wrong_header(self):
        """Test CSV with wrong header fails"""
        rows = [
            ["Wrong", "Header"],
            ["Data1", "Data2"]
        ]
        
        csv_file = self.create_test_csv("CLINICALDATA20250101120000.CSV", rows)
        
        is_valid, errors, count = self.validator._validate_csv_content(csv_file, status_queue=None)
        
        self.assertFalse(is_valid)
        self.assertIn("Invalid header", errors[0])
    
    def test_empty_file(self):
        """Test empty CSV fails"""
        rows = []  # Empty file
        
        csv_file = self.create_test_csv("CLINICALDATA20250101120000.CSV", rows)
        
        is_valid, errors, count = self.validator._validate_csv_content(csv_file, status_queue=None)
        
        self.assertFalse(is_valid)
        self.assertIn("File is empty", errors[0])
    
    def test_bad_dosage(self):
        """Test CSV with bad dosage fails"""
        rows = [
            ["PatientID", "TrialCode", "DrugCode", "Dosage_mg", "StartDate", "EndDate", "Outcome", "SideEffects", "Analyst"],
            ["P001", "TRIAL001", "DRUG001", "abc", "2024-01-01", "2024-01-10", "Improved", "None", "Dr. Smith"],  # abc is not a number
        ]
        
        csv_file = self.create_test_csv("CLINICALDATA20250101120000.CSV", rows)
        
        is_valid, errors, count = self.validator._validate_csv_content(csv_file, status_queue=None)
        
        self.assertFalse(is_valid)
        self.assertIn("Dosage", errors[0])
    
    def test_bad_date(self):
        """Test CSV with bad date fails"""
        rows = [
            ["PatientID", "TrialCode", "DrugCode", "Dosage_mg", "StartDate", "EndDate", "Outcome", "SideEffects", "Analyst"],
            ["P001", "TRIAL001", "DRUG001", "100", "2024-01-10", "2024-01-01", "Improved", "None", "Dr. Smith"],  # End before start
        ]
        
        csv_file = self.create_test_csv("CLINICALDATA20250101120000.CSV", rows)
        
        is_valid, errors, count = self.validator._validate_csv_content(csv_file, status_queue=None)
        
        self.assertFalse(is_valid)
        self.assertIn("EndDate", errors[0])
    
    def test_bad_outcome(self):
        """Test CSV with bad outcome fails"""
        rows = [
            ["PatientID", "TrialCode", "DrugCode", "Dosage_mg", "StartDate", "EndDate", "Outcome", "SideEffects", "Analyst"],
            ["P001", "TRIAL001", "DRUG001", "100", "2024-01-01", "2024-01-10", "Good", "None", "Dr. Smith"],  # "Good" is not valid
        ]
        
        csv_file = self.create_test_csv("CLINICALDATA20250101120000.CSV", rows)
        
        is_valid, errors, count = self.validator._validate_csv_content(csv_file, status_queue=None)
        
        self.assertFalse(is_valid)
        self.assertIn("outcome", errors[0].lower())
    
    def test_missing_field(self):
        """Test CSV with missing field fails"""
        rows = [
            ["PatientID", "TrialCode", "DrugCode", "Dosage_mg", "StartDate", "EndDate", "Outcome", "SideEffects", "Analyst"],
            ["", "TRIAL001", "DRUG001", "100", "2024-01-01", "2024-01-10", "Improved", "None", "Dr. Smith"],  # Empty PatientID
        ]
        
        csv_file = self.create_test_csv("CLINICALDATA20250101120000.CSV", rows)
        
        is_valid, errors, count = self.validator._validate_csv_content(csv_file, status_queue=None)
        
        self.assertFalse(is_valid)
        self.assertIn("Missing", errors[0])
    
    def test_three_valid_records(self):
        """Test CSV with 3 valid records"""
        rows = [
            ["PatientID", "TrialCode", "DrugCode", "Dosage_mg", "StartDate", "EndDate", "Outcome", "SideEffects", "Analyst"],
            ["P001", "TRIAL001", "DRUG001", "100", "2024-01-01", "2024-01-10", "Improved", "None", "Dr. Smith"],
            ["P002", "TRIAL001", "DRUG002", "150", "2024-01-02", "2024-01-11", "No Change", "Nausea", "Dr. Jones"],
            ["P003", "TRIAL002", "DRUG003", "200", "2024-01-03", "2024-01-12", "Worsened", "Headache", "Dr. Lee"],
        ]
        
        csv_file = self.create_test_csv("CLINICALDATA20250101120000.CSV", rows)
        
        is_valid, errors, count = self.validator._validate_csv_content(csv_file, status_queue=None)
        
        self.assertTrue(is_valid)
        self.assertEqual(count, 3)
        self.assertEqual(len(errors), 0)
    
    def test_one_good_one_bad(self):
        """Test CSV with one good and one bad record"""
        rows = [
            ["PatientID", "TrialCode", "DrugCode", "Dosage_mg", "StartDate", "EndDate", "Outcome", "SideEffects", "Analyst"],
            ["P001", "TRIAL001", "DRUG001", "100", "2024-01-01", "2024-01-10", "Improved", "None", "Dr. Smith"],  # Good
            ["P002", "TRIAL001", "DRUG001", "abc", "2024-01-02", "2024-01-11", "No Change", "Nausea", "Dr. Jones"],  # Bad dosage
        ]
        
        csv_file = self.create_test_csv("CLINICALDATA20250101120000.CSV", rows)
        
        is_valid, errors, count = self.validator._validate_csv_content(csv_file, status_queue=None)
        
        self.assertFalse(is_valid)  # Has errors
        self.assertEqual(count, 1)  # Only 1 valid record
        self.assertGreater(len(errors), 0)  # Has error messages


if __name__ == '__main__':
    print("Running Simple CSV Tests...")
    print("=" * 60)
    unittest.main(verbosity=2)