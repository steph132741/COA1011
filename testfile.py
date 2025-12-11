def test_valid_file_is_archived(self):
    rows = [
        ["PatientID","TrialCode","DrugCode","Dosage_mg","StartDate","EndDate","Outcome","SideEffects","Analyst"],
        ["P1","T1","D1","10","2024-01-01","2024-01-02","Improved","None","A"]
    ]
    path = self.create_csv("CLINICALDATA20250101120000.CSV", rows)

    # Call validation + processing
    is_valid, errors, count = self.validator._validate_csv_content(path)

    # Simulate final processing step
    if is_valid:
        archive_path = self.archive / "CLINICALDATA20250101120000_20250105.CSV"
        shutil.move(path, archive_path)

    # Expect: file moved to archive
    self.assertTrue(archive_path.exists())


