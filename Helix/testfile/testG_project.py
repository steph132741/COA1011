import pytest
import tempfile
import csv
from pathlib import Path

def test_validate_csv_content_empty_file():

    with tempfile.TemporaryDirectory() as tmpdir:
        download = Path(tmpdir) / "download"
        archive = Path(tmpdir) / "archive"
        errors = Path(tmpdir) / "errors"
        download.mkdir()
        archive.mkdir()
        errors.mkdir()
        
        validator = (download, archive, errors)
        
        csv_path = download / "test.csv"
        csv_path.write_text("") 
        
        is_valid, errors_list, valid_count = validator._validate_csv_content(
            csv_path, 
            status_queue=None
        )
        
        assert is_valid == False 
        assert "File is empty" in errors_list[0]  
        assert valid_count == 0 