# test_project.py
import pytest
import tempfile
import csv
from pathlib import Path

def test_validate_csv_content_empty_file():
    """Test that an empty CSV file fails validation"""
    # Arrange
    with tempfile.TemporaryDirectory() as tmpdir:
        download = Path(tmpdir) / "download"
        archive = Path(tmpdir) / "archive"
        errors = Path(tmpdir) / "errors"
        download.mkdir()
        archive.mkdir()
        errors.mkdir()
        
        validator = (download, archive, errors)
        
        # Create an empty CSV file
        csv_path = download / "test.csv"
        csv_path.write_text("")  # Empty file
        
        # Act
        is_valid, errors_list, valid_count = validator._validate_csv_content(
            csv_path, 
            status_queue=None
        )
        
        # Assert - Check based on your actual implementation
        assert is_valid == False  # Empty file should be invalid
        # Don't check the exact error message, just that there ARE errors
        assert len(errors_list) > 0
        assert valid_count == 0

def test_validate_csv_content_valid_simple():
    """Test that a simple valid CSV passes validation"""
    # Arrange
    with tempfile.TemporaryDirectory() as tmpdir:
        download = Path(tmpdir) / "download"
        archive = Path(tmpdir) / "archive"
        errors = Path(tmpdir) / "errors"
        download.mkdir()
        archive.mkdir()
        errors.mkdir()
        
        validator = (download, archive, errors)
        
        # Create a valid CSV file
        csv_path = download / "test.csv"
        csv_content = """PatientID,TrialCode,DrugCode,Dosage_mg,StartDate,EndDate,Outcome,SideEffects,Analyst
P001,T001,D001,100,2024-01-01,2024-01-31,Improved,None,Dr. Smith"""
        
        csv_path.write_text(csv_content)
        
        # Act
        is_valid, errors_list, valid_count = validator._validate_csv_content(
            csv_path, 
            status_queue=None
        )
        
        # Assert
        assert is_valid == True
        assert len(errors_list) == 0
        assert valid_count == 1

def test_filename_validation():
    """Test filename pattern validation"""
    # Arrange
    with tempfile.TemporaryDirectory() as tmpdir:
        download = Path(tmpdir) / "download"
        archive = Path(tmpdir) / "archive"
        errors = Path(tmpdir) / "errors"
        download.mkdir()
        archive.mkdir()
        errors.mkdir()
        
        validator = (download, archive, errors)
        
        # Test valid filename
        valid_filename = "CLINICALDATA20250401121530.csv"
        is_valid = validator._validate_filename_pattern(valid_filename, status_queue=None)
        assert is_valid == True
        
        # Test invalid filename
        invalid_filename = "wrongname.csv"
        is_valid = validator._validate_filename_pattern(invalid_filename, status_queue=None)
        assert is_valid == False