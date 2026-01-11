"""
clinical_data_processor.py (modified - short stage logs, no progress bar)
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, Listbox, SINGLE
import ftplib
import csv
import os
import re
import requests
import uuid
import shutil
import argparse
from datetime import datetime
from pathlib import Path
import threading
import queue
import io
import sys
import unittest
import tempfile

COLORS = {
    'primary': '#8B7355','secondary': '#A52A2A','accent': '#D2691E','dark_bg': '#2F4F4F',
    'medium_bg': '#708090','light_bg': '#F5F5F5','card_bg': '#FFFFFF','text_dark': '#2F4F4F',
    'text_light': '#FFFFFF','text_muted': '#696969','success': '#228B22','warning': '#FF8C00',
    'error': '#DC143C','border': '#C0C0C0','btn_connect': '#27AE60','btn_disconnect': '#E74C3C',
    'btn_validate': '#3498DB','btn_process': '#9B59B6','btn_search': '#16A085','btn_refresh': '#F39C12',
    'btn_browse': '#95A5A6','btn_utility': '#34495E','btn_disabled': '#BDC3C7',
}

class ClinicalDataProcessor:
    def __init__(self, ftp_host, ftp_user, ftp_pass, remote_dir=""):
        self.ftp_host = ftp_host
        self.ftp_user = ftp_user
        self.ftp_pass = ftp_pass
        self.remote_dir = remote_dir
        self.ftp = None
        self.connected = False

    def connect(self, status_queue=None, passive=True, timeout=30):
        try:
            if self.ftp:
                try:
                    self.ftp.quit()
                except Exception:
                    pass
            self.ftp = ftplib.FTP(timeout=timeout)
            self.ftp.connect(self.ftp_host)
            self.ftp.set_pasv(passive)
            self.ftp.login(self.ftp_user, self.ftp_pass)
            if self.remote_dir:
                try:
                    self.ftp.cwd(self.remote_dir)
                except Exception as e:
                    if status_queue:
                        status_queue.put((f"Warning: Could not change to remote dir '{self.remote_dir}': {e}", "warning"))
            self.connected = True
            if status_queue:
                status_queue.put(("✅ FTP connection successful", "success"))
                try:
                    status_queue.put((f"Current directory: {self.ftp.pwd()}", "info"))
                except Exception:
                    pass
            return True
        except Exception as e:
            self.connected = False
            if status_queue:
                status_queue.put((f"❌ Connection failed: {e}", "error"))
            return False

    def disconnect(self):
        if self.ftp:
            try:
                self.ftp.quit()
            except Exception:
                try:
                    self.ftp.close()
                except Exception:
                    pass
        self.connected = False
        self.ftp = None

    def get_file_list(self, status_queue=None):
        if not self.ftp or not self.connected:
            if status_queue:
                status_queue.put(("Not connected to FTP server", "error"))
            return []
        try:
            files = self.ftp.nlst()
            # simple CSV detection; keep case-insensitive
            csv_files = [f for f in files if re.search(r'\.csv$', f, re.IGNORECASE)]
            if status_queue and csv_files:
                status_queue.put((f"Found {len(csv_files)} CSV files", "success"))
            elif status_queue:
                status_queue.put(("No CSV files found", "warning"))
            return sorted(csv_files)
        except Exception as e:
            if status_queue:
                status_queue.put((f"Failed to retrieve file list: {e}", "error"))
            return []

class ClinicalDataValidator:
    def __init__(self, download_dir, archive_dir, error_dir):
        self.download_dir = Path(download_dir)
        self.archive_dir = Path(archive_dir)
        self.error_dir = Path(error_dir)
        for directory in [self.download_dir, self.archive_dir, self.error_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        self.processed_files_log = self.download_dir / "processed_files.txt"
        self.processed_files = self._load_processed_files()

    def _load_processed_files(self):
        if self.processed_files_log.exists():
            return set(self.processed_files_log.read_text().splitlines())
        return set()

    def _save_processed_file(self, filename):
        self.processed_files.add(filename)
        self.processed_files_log.write_text("\n".join(sorted(self.processed_files)))

    def generate_uuid_from_api():
        try:
            response = requests.get("https://www.uuidtools.com/api/generate/v4", timeout=5)
            response.raise_for_status()
            uuids = response.json()
        

            if isinstance(uuid, list) and len(uuid) > 0:
                return uuid[0]
        except requests.exceptions.Timeout: 
             pass
        except requests. exceptions.ConnectionError: 
            pass
        except Exception as e: 
            pass

        return str(uuid.uuid4())

        if response.status_code != 200:
            raise ConnectionError(
                    f"API returned status code {response.status_code}"
                )

            data = response.json()
            return data[0] 


    def _log_error(self, filename, error_details):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        guid = self._generate_guid()
        log_entry = f"[{timestamp}] GUID: {guid} | File: {filename} | Error: {error_details}\n"
        error_log_path = self.error_dir / "error_report.log"
        with open(error_log_path, "a", encoding='utf-8') as f:
            f.write(log_entry)
        return guid, log_entry

    def _validate_filename_pattern(self, filename, status_queue=None):
        pattern = r'^CLINICALDATA\d{14}\.CSV$'
        is_valid = re.match(pattern, filename, re.IGNORECASE) is not None
        if status_queue:
            if is_valid:
                status_queue.put((f"  ✓ Filename pattern valid", "success"))
            else:
                status_queue.put((f"  ✗ Invalid pattern (expected CLINICALDATAYYYYMMDDHHMMSS.CSV)", "error"))
        return is_valid

    def _validate_csv_content(self, file_path, status_queue=None, progress_callback=None):
        """
        Returns: (is_valid: bool, errors: [str], valid_count: int)
        Uses short stage-based logs instead of progress percentages.
        """
        errors = []
        valid_records = []
        seen_records = set()

        if status_queue:
            status_queue.put((f"  → Validating content...", "info"))

        try:
            # Accept paths or file-like object
            if isinstance(file_path, (str, Path)):
                with open(file_path, 'r', newline='', encoding='utf-8') as fobj:
                    reader = csv.reader(fobj)
                    try:
                        header = next(reader)
                    except StopIteration:
                        if status_queue:
                            status_queue.put((f"  ✗ File is empty", "error"))
                        return False, ["File is empty"], 0

                    expected_fields = ["PatientID", "TrialCode", "DrugCode", "Dosage_mg",
                                       "StartDate", "EndDate", "Outcome", "SideEffects", "Analyst"]
                    # Stage: Checking header
                    if status_queue:
                        status_queue.put(("→ Checking header...", "info"))
                    if header != expected_fields:
                        errors.append(f"Invalid header. Expected fields: {expected_fields}")
                        if status_queue:
                            status_queue.put((f"  ✗ Header mismatch", "error"))
                        return False, errors, 0
                    else:
                        if status_queue:
                            status_queue.put((f"  ✓ Header valid ({len(header)} fields)", "success"))

                    # Stage: Validating rows
                    if status_queue:
                        status_queue.put(("→ Validating rows...", "info"))

                    rows = list(reader)
                    total_rows = len(rows)
                    if total_rows == 0:
                        if status_queue:
                            status_queue.put((f"  ✗ No data rows found", "error"))
                        return False, ["No data rows"], 0

                    row_num = 1
                    error_counts = {
                        'field_count': 0, 'missing_fields': 0, 'dosage': 0,
                        'date_range': 0, 'date_format': 0, 'outcome': 0,
                        'duplicate': 0
                    }

                    for idx, row in enumerate(rows, start=1):
                        row_num += 1
                        record_errors = []
                        if len(row) != 9:
                            error_counts['field_count'] += 1
                            errors.append(f"Row {row_num}: Expected 9 fields, got {len(row)}")
                            continue

                        (patient_id, trial_code, drug_code, dosage,
                         start_date, end_date, outcome, side_effects, analyst) = row

                        if not all([patient_id, trial_code, drug_code, dosage,
                                    start_date, end_date, outcome, side_effects, analyst]):
                            error_counts['missing_fields'] += 1
                            record_errors.append("Missing required fields")

                        try:
                            dosage_val = int(dosage)
                            if dosage_val <= 0:
                                error_counts['dosage'] += 1
                                record_errors.append(f"Dosage must be positive integer, got '{dosage}'")
                        except Exception:
                            error_counts['dosage'] += 1
                            record_errors.append(f"Non-numeric dosage: '{dosage}'")

                        try:
                            sd = datetime.strptime(start_date, "%Y-%m-%d")
                            ed = datetime.strptime(end_date, "%Y-%m-%d")
                            if ed < sd:
                                error_counts['date_range'] += 1
                                record_errors.append(f"EndDate ({end_date}) before StartDate ({start_date})")
                        except Exception:
                            error_counts['date_format'] += 1
                            record_errors.append("Invalid date format (expected YYYY-MM-DD)")

                        if outcome not in ["Improved", "No Change", "Worsened"]:
                            error_counts['outcome'] += 1
                            record_errors.append(f"Invalid outcome '{outcome}'")

                        key = f"{patient_id}_{trial_code}_{drug_code}"
                        if key in seen_records:
                            error_counts['duplicate'] += 1
                            record_errors.append("Duplicate record")
                        else:
                            seen_records.add(key)

                        if record_errors:
                            errors.append(f"Row {row_num}: {'; '.join(record_errors)}")
                        else:
                            valid_records.append(row)

                    # Stage: Checking duplicates (summary stage)
                    if status_queue:
                        status_queue.put(("→ Checking duplicates...", "info"))

                    # Final summary messages
                    if status_queue:
                        status_queue.put((f"  → Scanned {row_num - 1} rows", "info"))
                        status_queue.put((f"  → Valid records: {len(valid_records)}", "success"))
                        if error_counts['dosage'] > 0:
                            status_queue.put((f"    • Dosage errors: {error_counts['dosage']}", "error"))
                        if error_counts['date_range'] > 0:
                            status_queue.put((f"    • Date range errors: {error_counts['date_range']}", "error"))
                        if error_counts['date_format'] > 0:
                            status_queue.put((f"    • Date format errors: {error_counts['date_format']}", "error"))
                        if error_counts['outcome'] > 0:
                            status_queue.put((f"    • Outcome errors: {error_counts['outcome']}", "error"))
                        if error_counts['duplicate'] > 0:
                            status_queue.put((f"    • Duplicates: {error_counts['duplicate']}", "error"))
                        if error_counts['missing_fields'] > 0:
                            status_queue.put((f"    • Missing fields: {error_counts['missing_fields']}", "error"))

                    # Stage: Finalizing
                    if status_queue:
                        status_queue.put(("→ Finalizing...", "info"))

                    if errors:
                        return False, errors, len(valid_records)
                    return True, [], len(valid_records)

            else:
                # file-like object branch
                fobj = file_path
                reader = csv.reader(fobj)
                try:
                    header = next(reader)
                except StopIteration:
                    if status_queue:
                        status_queue.put((f"  ✗ File is empty", "error"))
                    return False, ["File is empty"], 0

                expected_fields = ["PatientID", "TrialCode", "DrugCode", "Dosage_mg",
                                   "StartDate", "EndDate", "Outcome", "SideEffects", "Analyst"]
                if status_queue:
                    status_queue.put(("→ Checking header...", "info"))
                if header != expected_fields:
                    errors.append(f"Invalid header. Expected fields: {expected_fields}")
                    if status_queue:
                        status_queue.put((f"  ✗ Header mismatch", "error"))
                    return False, errors, 0
                else:
                    if status_queue:
                        status_queue.put((f"  ✓ Header valid ({len(header)} fields)", "success"))

                if status_queue:
                    status_queue.put(("→ Validating rows...", "info"))

                rows = list(reader)
                total_rows = len(rows)
                if total_rows == 0:
                    if status_queue:
                        status_queue.put((f"  ✗ No data rows found", "error"))
                    return False, ["No data rows"], 0

                row_num = 1
                error_counts = {
                    'field_count': 0, 'missing_fields': 0, 'dosage': 0,
                    'date_range': 0, 'date_format': 0, 'outcome': 0,
                    'duplicate': 0
                }
                for idx, row in enumerate(rows, start=1):
                    row_num += 1
                    record_errors = []

                    if len(row) != 9:
                        error_counts['field_count'] += 1
                        errors.append(f"Row {row_num}: Expected 9 fields, got {len(row)}")
                        continue

                    (patient_id, trial_code, drug_code, dosage,
                     start_date, end_date, outcome, side_effects, analyst) = row

                    if not all([patient_id, trial_code, drug_code, dosage,
                                start_date, end_date, outcome, side_effects, analyst]):
                        error_counts['missing_fields'] += 1
                        record_errors.append("Missing required fields")

                    try:
                        dosage_val = int(dosage)
                        if dosage_val <= 0:
                            error_counts['dosage'] += 1
                            record_errors.append(f"Dosage must be positive integer, got '{dosage}'")
                    except Exception:
                        error_counts['dosage'] += 1
                        record_errors.append(f"Non-numeric dosage: '{dosage}'")

                    try:
                        sd = datetime.strptime(start_date, "%Y-%m-%d")
                        ed = datetime.strptime(end_date, "%Y-%m-%d")
                        if ed < sd:
                            error_counts['date_range'] += 1
                            record_errors.append(f"EndDate ({end_date}) before StartDate ({start_date})")
                    except Exception:
                        error_counts['date_format'] += 1
                        record_errors.append("Invalid date format (expected YYYY-MM-DD)")

                    if outcome not in ["Improved", "No Change", "Worsened"]:
                        error_counts['outcome'] += 1
                        record_errors.append(f"Invalid outcome '{outcome}'")

                    key = f"{patient_id}_{trial_code}_{drug_code}"
                    if key in seen_records:
                        error_counts['duplicate'] += 1
                        record_errors.append("Duplicate record")
                    else:
                        seen_records.add(key)

                    if record_errors:
                        errors.append(f"Row {row_num}: {'; '.join(record_errors)}")
                    else:
                        valid_records.append(row)

                if status_queue:
                    status_queue.put(("→ Checking duplicates...", "info"))
                    status_queue.put((f"  → Scanned {row_num - 1} rows", "info"))
                    status_queue.put((f"  → Valid records: {len(valid_records)}", "success"))
                    if error_counts['dosage'] > 0:
                        status_queue.put((f"    • Dosage errors: {error_counts['dosage']}", "error"))
                    if error_counts['date_range'] > 0:
                        status_queue.put((f"    • Date range errors: {error_counts['date_range']}", "error"))
                    if error_counts['date_format'] > 0:
                        status_queue.put((f"    • Date format errors: {error_counts['date_format']}", "error"))
                    if error_counts['outcome'] > 0:
                        status_queue.put((f"    • Outcome errors: {error_counts['outcome']}", "error"))
                    if error_counts['duplicate'] > 0:
                        status_queue.put((f"    • Duplicates: {error_counts['duplicate']}", "error"))
                    if error_counts['missing_fields'] > 0:
                        status_queue.put((f"    • Missing fields: {error_counts['missing_fields']}", "error"))
                    status_queue.put(("→ Finalizing...", "info"))

                if errors:
                    return False, errors, len(valid_records)
                return True, [], len(valid_records)

        except UnicodeDecodeError:
            if status_queue:
                status_queue.put((f"  ✗ File is not valid UTF-8 encoded CSV", "error"))
            return False, ["File is not valid UTF-8 encoded CSV"], 0
        except Exception as e:
            if status_queue:
                status_queue.put((f"  ✗ File read error: {str(e)}", "error"))
            return False, [f"File read error: {str(e)}"], 0

    def validate_selected_files(self, ftp_obj, files, status_queue):
        valid_count = 0
        invalid_count = 0
        for filename in files:
            if filename in self.processed_files:
                status_queue.put((f"\n⏭️ Skipping: {filename} (already processed)", "warning"))
                continue
            status_queue.put((f"\n{'='*60}", "info"))
            status_queue.put((f"🔍 Validating: {filename}", "info"))
            temp_path = self.download_dir / f"temp_validate_{filename}"
            try:
                with open(temp_path, 'wb') as f:
                    ftp_obj.retrbinary(f'RETR {filename}', f.write)
                if self._validate_filename_pattern(filename, status_queue):
                    is_valid, errors, record_count = self._validate_csv_content(
                        temp_path, status_queue=status_queue, progress_callback=None
                    )
                    if is_valid:
                        status_queue.put((f"✅ VALID: {filename} ({record_count} records)", "success"))
                        valid_count += 1
                    else:
                        status_queue.put((f"❌ INVALID: {filename} ({len(errors)} errors)", "error"))
                        invalid_count += 1
                if temp_path.exists():
                    temp_path.unlink()
            except Exception as e:
                status_queue.put((f"❌ Error validating {filename}: {e}", "error"))
                invalid_count += 1
                if temp_path.exists():
                    temp_path.unlink()
            status_queue.put(("\n" + "="*60, "info"))
        status_queue.put(("✅ Validation complete!", "complete"))
        status_queue.put((f"📊 Results: {valid_count} valid, {invalid_count} invalid", "summary"))

    def process_selected_files(self, ftp_obj, files, status_queue):
        processed_count = 0
        error_count = 0
        for filename in files:
            if filename in self.processed_files:
                status_queue.put((f"\n⏭️ Skipping: {filename} (already processed)", "warning"))
                continue
            status_queue.put((f"\n{'='*60}", "info"))
            status_queue.put((f"Processing: {filename}", "info"))
            local_path = self.download_dir / filename
            try:
                with open(local_path, 'wb') as f:
                    ftp_obj.retrbinary(f'RETR {filename}', f.write)
                status_queue.put((f"  📥 Downloaded successfully", "success"))
                if not self._validate_filename_pattern(filename, status_queue):
                    error_file = self.error_dir / filename
                    shutil.move(str(local_path), str(error_file))
                    guid, _ = self._log_error(filename, "Invalid filename pattern")
                    status_queue.put((f"  ❌ Rejected - Invalid pattern (GUID: {guid})", "error"))
                    error_count += 1
                    continue
                is_valid, errors, record_count = self._validate_csv_content(
                    local_path, status_queue=status_queue, progress_callback=None
                )
                if is_valid:
                    try:
                        current_date = datetime.now().strftime("%Y%m%d")
                        base_name = filename[:-4]
                        archive_filename = f"{base_name}_{current_date}.CSV"
                        archive_path = self.archive_dir / archive_filename
                        shutil.move(str(local_path), str(archive_path))
                        self._save_processed_file(filename)
                        status_queue.put((f"  ✅ Archived as: {archive_filename} ({record_count} records)", "success"))
                        processed_count += 1
                    except Exception as e:
                        guid, _ = self._log_error(filename, f"Archival failed: {e}")
                        status_queue.put((f"  ❌ Archival error (GUID: {guid})", "error"))
                        error_count += 1
                        if local_path.exists():
                            local_path.unlink()
                else:
                    error_file = self.error_dir / filename
                    shutil.move(str(local_path), str(error_file))
                    summary = " | ".join(errors[:3])
                    if len(errors) > 3:
                        summary += f" ... and {len(errors) - 3} more"
                    guid, _ = self._log_error(filename, summary)
                    status_queue.put((f"  ❌ Rejected ({len(errors)} errors)", "error"))
                    for error in errors[:3]:
                        status_queue.put((f"    • {error}", "error"))
                    error_count += 1
            except Exception as e:
                status_queue.put((f"  ❌ Fatal error: {e}", "error"))
                error_count += 1
                if local_path.exists():
                    local_path.unlink()
            status_queue.put(("\n" + "="*60, "info"))
        status_queue.put(("✅ Processing complete!", "complete"))
        status_queue.put((f"📊 Summary: {processed_count} archived, {error_count} rejected", "summary"))

class ClinicalDataGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("HelixSoft Clinical Data Processor")
        self.root.geometry("1100x800")
        self.root.configure(bg=COLORS['light_bg'])
        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except Exception:
            pass
        self.configure_styles()
        self.processor = None
        self.validator = None
        self.is_processing = False
        self.all_files = []
        self.displayed_files = []
        home = Path.home()
        self.ftp_host = tk.StringVar(value="localhost")
        self.ftp_user = tk.StringVar(value="anonymous")
        self.ftp_pass = tk.StringVar(value="")
        self.remote_dir = tk.StringVar(value="")
        self.download_dir = tk.StringVar(value=str(home / "ClinicalData" / "Downloads"))
        self.archive_dir = tk.StringVar(value=str(home / "ClinicalData" / "Archive"))
        self.error_dir = tk.StringVar(value=str(home / "ClinicalData" / "Errors"))
        self.search_var = tk.StringVar()
        self.setup_directories()
        self.create_widgets()
        self.status_queue = queue.Queue()
        self.root.after(100, self.check_queue)

    def configure_styles(self):
        s = self.style
        s.configure('Modern.TFrame', background=COLORS['light_bg'])
        s.configure('Card.TFrame', background=COLORS['card_bg'], relief='raised', borderwidth=1)
        s.configure('Header.TLabel', font=('Segoe UI', 16, 'bold'), background=COLORS['light_bg'], foreground=COLORS['dark_bg'])
        s.configure('Subheader.TLabel', font=('Segoe UI', 10, 'bold'), background=COLORS['light_bg'], foreground=COLORS['text_dark'])
        btn_map = {'Connect': COLORS['btn_connect'],'Disconnect': COLORS['btn_disconnect'],'Validate': COLORS['btn_validate'],'Process': COLORS['btn_process'],'Search': COLORS['btn_search'],'Refresh': COLORS['btn_refresh'],'Browse': COLORS['btn_browse'],'Utility': COLORS['btn_utility'],}
        for name, bg in btn_map.items():
            s.configure(f'{name}.TButton', padding=(8, 6), font=('Segoe UI', 9, 'bold'), background=bg, foreground=COLORS['text_light'], relief='raised', borderwidth=1)
            s.map(f'{name}.TButton', background=[('disabled', COLORS['btn_disabled'])], relief=[('pressed', 'sunken'), ('!pressed', 'raised')])
        s.configure('Modern.TEntry', padding=(6, 6), font=('Segoe UI', 10), fieldbackground=COLORS['card_bg'])

    def setup_directories(self):
        for var in [self.download_dir, self.archive_dir, self.error_dir]:
            Path(var.get()).mkdir(parents=True, exist_ok=True)

    def create_widgets(self):
        main_container = ttk.Frame(self.root, style='Modern.TFrame')
        main_container.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        header_frame = ttk.Frame(main_container, style='Modern.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(header_frame, text="🧬 HELIXSOFT CLINICAL DATA PROCESSOR", style='Header.TLabel').pack(side=tk.LEFT)
        self.status_label = ttk.Label(header_frame, text="● DISCONNECTED", foreground=COLORS['error'], font=('Segoe UI', 10, 'bold'), background=COLORS['light_bg'])
        self.status_label.pack(side=tk.RIGHT)
        content_frame = ttk.Frame(main_container, style='Modern.TFrame')
        content_frame.pack(fill=tk.BOTH, expand=True)
        left_panel = ttk.Frame(content_frame, style='Modern.TFrame')
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))
        right_panel = ttk.Frame(content_frame, style='Modern.TFrame')
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(12, 0))

        ftp_card = ttk.LabelFrame(left_panel, text="🔌 FTP CONNECTION", style='Modern.TFrame', padding=12)
        ftp_card.pack(fill=tk.X, pady=(0, 12))
        form_frame = ttk.Frame(ftp_card, style='Modern.TFrame'); form_frame.pack(fill=tk.X)
        host_frame = ttk.Frame(form_frame, style='Modern.TFrame'); host_frame.pack(fill=tk.X, pady=4)
        ttk.Label(host_frame, text="Host:", style='Subheader.TLabel', width=12).pack(side=tk.LEFT)
        ttk.Entry(host_frame, textvariable=self.ftp_host, style='Modern.TEntry', width=28).pack(side=tk.LEFT, fill=tk.X, padx=(6, 0))
        user_frame = ttk.Frame(form_frame, style='Modern.TFrame'); user_frame.pack(fill=tk.X, pady=4)
        ttk.Label(user_frame, text="Username:", style='Subheader.TLabel', width=12).pack(side=tk.LEFT)
        ttk.Entry(user_frame, textvariable=self.ftp_user, style='Modern.TEntry', width=28).pack(side=tk.LEFT, fill=tk.X, padx=(6, 0))
        pass_frame = ttk.Frame(form_frame, style='Modern.TFrame'); pass_frame.pack(fill=tk.X, pady=4)
        ttk.Label(pass_frame, text="Password:", style='Subheader.TLabel', width=12).pack(side=tk.LEFT)
        ttk.Entry(pass_frame, textvariable=self.ftp_pass, show="*", style='Modern.TEntry', width=28).pack(side=tk.LEFT, fill=tk.X, padx=(6, 0))
        conn_btn_frame = ttk.Frame(ftp_card, style='Modern.TFrame'); conn_btn_frame.pack(fill=tk.X, pady=(8, 0))
        self.connect_btn = ttk.Button(conn_btn_frame, text="🔌 CONNECT", command=self.connect_to_server, style='Connect.TButton'); self.connect_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.disconnect_btn = ttk.Button(conn_btn_frame, text="❌ DISCONNECT", command=self.disconnect_from_server, style='Disconnect.TButton', state=tk.DISABLED); self.disconnect_btn.pack(side=tk.LEFT)

        file_card = ttk.LabelFrame(left_panel, text="📁 SERVER FILES", style='Modern.TFrame', padding=12); file_card.pack(fill=tk.BOTH, expand=True, pady=(0, 12))
        controls_frame = ttk.Frame(file_card, style='Modern.TFrame'); controls_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(controls_frame, text="Search:", style='Subheader.TLabel').pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(controls_frame, textvariable=self.search_var, style='Modern.TEntry', width=28); self.search_entry.pack(side=tk.LEFT, padx=(6, 6), fill=tk.X, expand=True)
        self.search_entry.bind('<KeyRelease>', self.filter_file_list)
        ttk.Button(controls_frame, text="🔍 SEARCH", command=self.filter_file_list, style='Search.TButton').pack(side=tk.LEFT, padx=(6, 6))
        ttk.Button(controls_frame, text="🔄 REFRESH", command=self.refresh_file_list, style='Refresh.TButton').pack(side=tk.RIGHT)

        list_container = ttk.Frame(file_card, style='Modern.TFrame'); list_container.pack(fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(list_container); scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox = Listbox(list_container, selectmode=SINGLE, yscrollcommand=scrollbar.set, height=12, width=48, font=('Segoe UI', 10), bg=COLORS['card_bg'], relief='flat', highlightthickness=1, selectbackground=COLORS['btn_validate'], selectforeground=COLORS['text_light'])
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.file_listbox.yview)
        self.file_listbox.bind('<<ListboxSelect>>', self.on_file_selection_change)

        action_card = ttk.LabelFrame(left_panel, text="⚡ ACTIONS", style='Modern.TFrame', padding=12); action_card.pack(fill=tk.X)
        action_btn_frame = ttk.Frame(action_card, style='Modern.TFrame'); action_btn_frame.pack(fill=tk.X)
        self.validate_btn = ttk.Button(action_btn_frame, text="🔍 VALIDATE SELECTED FILE", command=self.validate_selected, style='Validate.TButton', state=tk.DISABLED); self.validate_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.process_btn = ttk.Button(action_btn_frame, text="🚀 PROCESS SELECTED FILE", command=self.process_selected, style='Process.TButton', state=tk.DISABLED); self.process_btn.pack(side=tk.LEFT)

        dir_card = ttk.LabelFrame(right_panel, text="📂 LOCAL DIRECTORIES", style='Modern.TFrame', padding=12); dir_card.pack(fill=tk.X, pady=(0, 12))
        directories = [("📥 Download:", self.download_dir),("📦 Archive:", self.archive_dir),("❌ Errors:", self.error_dir)]
        for i, (label, var) in enumerate(directories):
            row_frame = ttk.Frame(dir_card, style='Modern.TFrame'); row_frame.pack(fill=tk.X, pady=6)
            ttk.Label(row_frame, text=label, style='Subheader.TLabel', width=12).pack(side=tk.LEFT)
            entry = ttk.Entry(row_frame, textvariable=var, style='Modern.TEntry'); entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6))
            ttk.Button(row_frame, text="📁", command=lambda v=var: self.browse_directory(v), style='Browse.TButton', width=4).pack(side=tk.RIGHT)

        util_frame = ttk.Frame(dir_card, style='Modern.TFrame'); util_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(util_frame, text="📋 OPEN ERROR LOG", command=self.open_error_log, style='Utility.TButton').pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(util_frame, text="🗑️ CLEAR LOG", command=self.clear_log, style='Utility.TButton').pack(side=tk.LEFT)

        log_card = ttk.LabelFrame(right_panel, text="📝 PROCESSING LOG", style='Modern.TFrame', padding=12); log_card.pack(fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(log_card, height=20, width=65, wrap=tk.WORD, font=('Consolas', 9), bg=COLORS['card_bg'], relief='flat', padx=10, pady=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.tag_configure("info", foreground=COLORS['dark_bg'], font=('Consolas', 9))
        self.log_text.tag_configure("success", foreground=COLORS['success'], font=('Consolas', 9))
        self.log_text.tag_configure("warning", foreground=COLORS['warning'], font=('Consolas', 9))
        self.log_text.tag_configure("error", foreground=COLORS['error'], font=('Consolas', 9))
        self.log_text.tag_configure("complete", foreground=COLORS['primary'], font=('Consolas', 10, 'bold'))
        self.log_text.tag_configure("summary", foreground=COLORS['secondary'], font=('Consolas', 10, 'bold'))

        # Note: Progress bar removed (short stage-based logs will be used instead)

    def browse_directory(self, var):
        path = filedialog.askdirectory()
        if path:
            var.set(path)

    def log_message(self, message, tag="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        try:
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n", tag)
            self.log_text.see(tk.END)
        except Exception:
            print(f"[{timestamp}] {message}")

    def check_queue(self):
        try:
            while True:
                message, tag = self.status_queue.get_nowait()
                # Removed "progress" handling; logs drive all feedback now.

                # Special case: a "complete" code separate from tag
                if message == "complete" and tag == "complete":
                    self.is_processing = False
                    self.update_status_label()
                    continue

                self.log_message(message, tag)

                if tag in ["complete", "error"]:
                    self.update_status_label()
                    self.is_processing = False

        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.check_queue)

    def update_status_label(self):
        if self.processor and getattr(self.processor, "connected", False):
            self.status_label.config(text="● CONNECTED", foreground=COLORS['success'])
            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
            sel = self.file_listbox.curselection()
            if sel:
                self.validate_btn.config(state=tk.NORMAL)
                self.process_btn.config(state=tk.NORMAL)
        else:
            self.status_label.config(text="● DISCONNECTED", foreground=COLORS['error'])
            self.connect_btn.config(state=tk.NORMAL)
            self.disconnect_btn.config(state=tk.DISABLED)
            self.validate_btn.config(state=tk.DISABLED)
            self.process_btn.config(state=tk.DISABLED)

    def on_file_selection_change(self, event):
        selection = self.file_listbox.curselection()
        if selection and self.processor and getattr(self.processor, "connected", False):
            self.validate_btn.config(state=tk.NORMAL)
            self.process_btn.config(state=tk.NORMAL)
        else:
            self.validate_btn.config(state=tk.DISABLED)
            self.process_btn.config(state=tk.DISABLED)

    def connect_to_server(self):
        if self.is_processing:
            return
        self.log_text.delete(1.0, tk.END)
        self.is_processing = True
        thread = threading.Thread(target=self._connect_and_load_files)
        thread.daemon = True
        thread.start()

    def _connect_and_load_files(self):
        try:
            self.processor = ClinicalDataProcessor(
                self.ftp_host.get(),
                self.ftp_user.get(),
                self.ftp_pass.get(),
                self.remote_dir.get()
            )
            if self.processor.connect(self.status_queue):
                self.all_files = self.processor.get_file_list(self.status_queue)
                self.root.after(0, self.update_file_listbox)
                self.root.after(0, self.update_status_label)
                self.status_queue.put(("✅ File list loaded successfully", "success"))
                self.status_queue.put(("🟢 Ready to validate/process files", "info"))
            else:
                self.status_queue.put(("❌ Failed to connect", "error"))
            self.status_queue.put(("complete", "complete"))
        except Exception as e:
            self.status_queue.put((f"🚨 Connection error: {e}", "error"))
            self.status_queue.put(("complete", "complete"))

    def disconnect_from_server(self):
        if self.is_processing:
            return
        if not self.processor:
            messagebox.showwarning("Not Connected", "You are not connected to any server.")
            return
        self.log_text.delete(1.0, tk.END)
        self.is_processing = True
        thread = threading.Thread(target=self._disconnect_worker)
        thread.daemon = True
        thread.start()

    def _disconnect_worker(self):
        try:
            if self.processor:
                try:
                    if isinstance(self.processor, ClinicalDataProcessor):
                        self.processor.disconnect()
                except Exception:
                    pass
                self.processor.connected = False
                self.all_files = []
                self.root.after(0, self.update_file_listbox)
                self.root.after(0, self.update_status_label)
                self.status_queue.put(("✅ Disconnected from FTP server", "success"))
            self.status_queue.put(("complete", "complete"))
        except Exception as e:
            self.status_queue.put((f"🚨 Disconnect failed: {e}", "error"))
            self.status_queue.put(("complete", "complete"))

    def update_file_listbox(self):
        self.file_listbox.delete(0, tk.END)
        self.displayed_files = list(self.all_files.copy())
        for file in self.displayed_files:
            self.file_listbox.insert(tk.END, file)
        self.log_message(f"📁 Loaded {len(self.displayed_files)} files from server", "info")
        self.filter_file_list()

    def filter_file_list(self, event=None):
        search_term = self.search_var.get().lower()
        self.file_listbox.delete(0, tk.END)
        self.displayed_files = [f for f in self.all_files if search_term in f.lower()]
        for file in self.displayed_files:
            self.file_listbox.insert(tk.END, file)
        if search_term and not self.displayed_files:
            self.log_message(f"❌ No files found matching '{search_term}'", "error")
        elif search_term and self.displayed_files:
            self.log_message(f"🔍 Filtered: showing {len(self.displayed_files)} files matching '{search_term}'", "info")

    def refresh_file_list(self):
        if not (self.processor and getattr(self.processor, "connected", False)):
            messagebox.showwarning("Not Connected", "Please connect to the FTP server first.")
            return
        if self.is_processing:
            return
        self.search_var.set("")
        self.log_text.delete(1.0, tk.END)
        self.is_processing = True
        thread = threading.Thread(target=self._refresh_files)
        thread.daemon = True
        thread.start()

    def _refresh_files(self):
        try:
            if not self.processor.connected:
                self.processor.connect(self.status_queue)
            self.all_files = self.processor.get_file_list(self.status_queue)
            self.root.after(0, self.update_file_listbox)
            self.status_queue.put(("✅ File list refreshed", "success"))
            self.status_queue.put(("complete", "complete"))
        except Exception as e:
            self.status_queue.put((f"🚨 Refresh failed: {e}", "error"))
            self.status_queue.put(("complete", "complete"))

    def validate_selected(self):
        if self.is_processing:
            return
        selection = self.file_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a file to validate.")
            return
        selected_file = self.displayed_files[selection[0]]
        self.log_text.delete(1.0, tk.END)
        self.is_processing = True
        self.validate_btn.config(state=tk.DISABLED, text="⏳ VALIDATING...")
        self.process_btn.config(state=tk.DISABLED)
        self.validator = ClinicalDataValidator(self.download_dir.get(), self.archive_dir.get(), self.error_dir.get())
        thread = threading.Thread(target=self._validate_selected_worker, args=([selected_file],))
        thread.daemon = True
        thread.start()

    def _validate_selected_worker(self, files):
        try:
            if not self.processor or not getattr(self.processor, "connected", False):
                if not self.processor:
                    self.processor = ClinicalDataProcessor(
                        self.ftp_host.get(),
                        self.ftp_user.get(),
                        self.ftp_pass.get(),
                        self.remote_dir.get()
                    )
                self.processor.connect(self.status_queue)
            ftp_obj = self.processor.ftp
            self.validator.validate_selected_files(ftp_obj, files, self.status_queue)
            self.status_queue.put(("complete", "complete"))
        except Exception as e:
            self.status_queue.put((f"🚨 Validation failed: {e}", "error"))
            self.status_queue.put(("complete", "complete"))

    def process_selected(self):
        if self.is_processing:
            return
        selection = self.file_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a file to process.")
            return
        selected_file = self.displayed_files[selection[0]]
        confirm = messagebox.askyesno("Confirm Processing",
                                      f"Process file '{selected_file}'?\n\n"
                                      "✓ If valid, will be archived with date suffix\n"
                                      "✗ If invalid, will be moved to error folder\n"
                                      "⏭ Already processed files will be skipped")
        if not confirm:
            return
        self.log_text.delete(1.0, tk.END)
        self.is_processing = True
        self.validate_btn.config(state=tk.DISABLED)
        self.process_btn.config(state=tk.DISABLED, text="⏳ PROCESSING...")
        self.validator = ClinicalDataValidator(self.download_dir.get(), self.archive_dir.get(), self.error_dir.get())
        thread = threading.Thread(target=self._process_selected_worker, args=([selected_file],))
        thread.daemon = True
        thread.start()

    def _process_selected_worker(self, files):
        try:
            if not self.processor or not getattr(self.processor, "connected", False):
                if not self.processor:
                    self.processor = ClinicalDataProcessor(
                        self.ftp_host.get(),
                        self.ftp_user.get(),
                        self.ftp_pass.get(),
                        self.remote_dir.get()
                    )
                self.processor.connect(self.status_queue)
            ftp_obj = self.processor.ftp
            self.validator.process_selected_files(ftp_obj, files, self.status_queue)
            self.status_queue.put(("complete", "complete"))
        except Exception as e:
            self.status_queue.put((f"🚨 Processing failed: {e}", "error"))
            self.status_queue.put(("complete", "complete"))

    def open_error_log(self):
        error_log_path = Path(self.error_dir.get()) / "error_report.log"
        if error_log_path.exists():
            try:
                if os.name == 'nt':
                    os.startfile(error_log_path)
                elif sys.platform == 'darwin':
                    os.system(f'open "{error_log_path}"')
                else:
                    os.system(f'xdg-open "{error_log_path}"')
            except Exception as e:
                messagebox.showinfo("Open Error Log", f"Cannot open log file directly: {e}\nPath: {error_log_path}")
        else:
            messagebox.showinfo("Error Log", "No errors have been logged yet.")

    def clear_log(self):
        self.log_text.delete(1.0, tk.END)

class ValidatorUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="clinical_test_"))
        self.download = self.tmpdir / "down"
        self.archive = self.tmpdir / "arc"
        self.errors = self.tmpdir / "err"
        for p in [self.download, self.archive, self.errors]:
            p.mkdir(parents=True, exist_ok=True)
        self.validator = ClinicalDataValidator(self.download, self.archive, self.errors)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def create_csv(self, name, rows):
        path = self.download / name
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            for r in rows:
                w.writerow(r)
        return path

    def test_valid_file_passes(self):
        rows = [
            ["PatientID", "TrialCode", "DrugCode", "Dosage_mg", "StartDate", "EndDate", "Outcome", "SideEffects", "Analyst"],
            ["P1", "T1", "D1", "10", "2024-01-01", "2024-01-02", "Improved", "None", "A"]
        ]
        path = self.create_csv("CLINICALDATA20250101120000.CSV", rows)
        ok, errors, count = self.validator._validate_csv_content(path, status_queue=None)
        self.assertTrue(ok)
        self.assertEqual(count, 1)

    def test_invalid_header(self):
        rows = [["Bad", "Header"],]
        path = self.create_csv("CLINICALDATA20250101120001.CSV", rows)
        ok, errors, count = self.validator._validate_csv_content(path, status_queue=None)
        self.assertFalse(ok)
        self.assertTrue(any("Invalid header" in e for e in errors) or len(errors) > 0)

    def test_bad_dosage_and_date(self):
        rows = [
            ["PatientID", "TrialCode", "DrugCode", "Dosage_mg", "StartDate", "EndDate", "Outcome", "SideEffects", "Analyst"],
            ["P2", "T1", "D1", "-5", "2024-01-10", "2024-01-01", "Improved", "None", "B"],
            ["P3", "T1", "D2", "abc", "2024-01-05", "2024-01-10", "No Change", "SE", "C"]
        ]
        path = self.create_csv("CLINICALDATA20250101120002.CSV", rows)
        ok, errors, count = self.validator._validate_csv_content(path, status_queue=None)
        self.assertFalse(ok)
        self.assertTrue(any("Dosage" in e or "EndDate" in e or "Non-numeric dosage" in e for e in errors))

def main():
    parser = argparse.ArgumentParser(description="Clinical Data Processor (GUI)")
    parser.add_argument('--test', action='store_true', help='Run unit tests instead of GUI')
    args = parser.parse_args()
    if args.test:
        suite = unittest.TestLoader().loadTestsFromTestCase(ValidatorUnitTests)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)
    else:
        root = tk.Tk()
        app = ClinicalDataGUI(root)
        root.mainloop()

if __name__ == "__main__":
    main()