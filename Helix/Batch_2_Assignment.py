import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, Listbox, SINGLE
import ftplib
import csv
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
import threading
import queue

class ClinicalDataProcessor:
    """Handles FTP connection and file operations"""
    def __init__(self, ftp_host, ftp_user, ftp_pass, remote_dir=""):
        self.ftp_host = ftp_host
        self.ftp_user = ftp_user
        self.ftp_pass = ftp_pass
        self.remote_dir = remote_dir
        self.ftp = None
        self.connected = False
    
    def connect(self, status_queue=None):
        """Connect to FTP server with passive mode"""
        try:
            if self.ftp:
                try:
                    self.ftp.quit()
                except:
                    pass
            
            self.ftp = ftplib.FTP(self.ftp_host, timeout=30)
            self.ftp.set_pasv(True)
            self.ftp.login(self.ftp_user, self.ftp_pass)
            
            if self.remote_dir:
                try:
                    self.ftp.cwd(self.remote_dir)
                except:
                    if status_queue:
                        status_queue.put((f"Warning: Could not change to remote dir '{self.remote_dir}'", "warning"))
            
            self.connected = True
            if status_queue:
                status_queue.put(("✅ FTP connection successful", "success"))
                status_queue.put((f"Current directory: {self.ftp.pwd()}", "info"))
            
            return True
        except Exception as e:
            self.connected = False
            if status_queue:
                status_queue.put((f"❌ Connection failed: {e}", "error"))
            return False
    
    def disconnect(self):
        """Safely disconnect from FTP"""
        if self.ftp:
            try:
                self.ftp.quit()
                self.connected = False
            except:
                pass
    
    def get_file_list(self, status_queue=None):
        """Get list of CSV files from server"""
        if not self.ftp or not self.connected:
            if status_queue:
                status_queue.put(("Not connected to FTP server", "error"))
            return []
        
        try:
            files = self.ftp.nlst()
            csv_files = [f for f in files if f.upper().endswith('.CSV')]
            
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
    """Handles file validation logic"""
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
    
    def _generate_guid(self):
        return str(uuid.uuid4())
    
    def _log_error(self, filename, error_details):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        guid = self._generate_guid()
        log_entry = f"[{timestamp}] GUID: {guid} | File: {filename} | Error: {error_details}\n"
        
        error_log_path = self.error_dir / "error_report.log"
        with open(error_log_path, "a") as f:
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
    
    def _validate_csv_content(self, file_path, status_queue=None):
        errors = []
        valid_records = []
        seen_records = set()
        
        if status_queue:
            status_queue.put((f"  → Validating content...", "info"))
        
        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                
                try:
                    header = next(reader)
                    expected_fields = ["PatientID", "TrialCode", "DrugCode", "Dosage_mg", 
                                     "StartDate", "EndDate", "Outcome", "SideEffects", "Analyst"]
                    if header != expected_fields:
                        errors.append(f"Invalid header. Expected {len(expected_fields)} fields: {expected_fields}")
                        if status_queue:
                            status_queue.put((f"  ✗ Header mismatch", "error"))
                        return False, errors, 0
                    elif status_queue:
                        status_queue.put((f"  ✓ Header valid ({len(header)} fields)", "success"))
                except StopIteration:
                    errors.append("File is empty")
                    if status_queue:
                        status_queue.put((f"  ✗ File is empty", "error"))
                    return False, errors, 0
                
                row_num = 1
                error_counts = {
                    'field_count': 0, 'missing_fields': 0, 'dosage': 0,
                    'date_range': 0, 'date_format': 0, 'outcome': 0,
                    'duplicate': 0
                }
                
                for row in reader:
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
                    except:
                        error_counts['dosage'] += 1
                        record_errors.append(f"Non-numeric dosage: '{dosage}'")
                    
                    try:
                        if datetime.strptime(end_date, "%Y-%m-%d") < datetime.strptime(start_date, "%Y-%m-%d"):
                            error_counts['date_range'] += 1
                            record_errors.append(f"EndDate ({end_date}) before StartDate ({start_date})")
                    except:
                        error_counts['date_format'] += 1
                        record_errors.append(f"Invalid date format (expected YYYY-MM-DD)")
                    
                    if outcome not in ["Improved", "No Change", "Worsened"]:
                        error_counts['outcome'] += 1
                        record_errors.append(f"Invalid outcome '{outcome}'")
                    
                    key = f"{patient_id}_{trial_code}_{drug_code}"
                    if key in seen_records:
                        error_counts['duplicate'] += 1
                        record_errors.append(f"Duplicate record")
                    else:
                        seen_records.add(key)
                    
                    if record_errors:
                        errors.append(f"Row {row_num}: {'; '.join(record_errors)}")
                    else:
                        valid_records.append(row)
                
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
            
            if errors:
                return False, errors, len(valid_records)
            return True, [], len(valid_records)
            
        except UnicodeDecodeError:
            return False, ["File is not valid UTF-8 encoded CSV"], 0
        except Exception as e:
            return False, [f"File read error: {str(e)}"], 0
    
    def validate_selected_files(self, ftp, files, status_queue):
        """Validate specific files without archiving"""
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
                    ftp.retrbinary(f'RETR {filename}', f.write)
                
                if self._validate_filename_pattern(filename, status_queue):
                    is_valid, errors, record_count = self._validate_csv_content(temp_path, status_queue)
                    
                    if is_valid:
                        status_queue.put((f"✅ VALID: {filename} ({record_count} records)", "success"))
                        valid_count += 1
                    else:
                        status_queue.put((f"❌ INVALID: {filename} ({len(errors)} errors)", "error"))
                        invalid_count += 1
                
                temp_path.unlink()
            except Exception as e:
                status_queue.put((f"❌ Error validating {filename}: {e}", "error"))
                invalid_count += 1
                if temp_path.exists():
                    temp_path.unlink()
        
        status_queue.put(("\n" + "="*60, "info"))
        status_queue.put(("✅ Validation complete!", "complete"))
        status_queue.put((f"📊 Results: {valid_count} valid, {invalid_count} invalid", "summary"))
    
    def process_selected_files(self, ftp, files, status_queue):
        """Process files: download, validate, archive or reject"""
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
                # Download file
                with open(local_path, 'wb') as f:
                    ftp.retrbinary(f'RETR {filename}', f.write)
                status_queue.put((f"  📥 Downloaded successfully", "success"))
                
                # Validate filename
                if not self._validate_filename_pattern(filename, status_queue):
                    error_file = self.error_dir / filename
                    local_path.rename(error_file)
                    guid, _ = self._log_error(filename, "Invalid filename pattern")
                    status_queue.put((f"  ❌ Rejected - Invalid pattern (GUID: {guid})", "error"))
                    error_count += 1
                    continue
                
                # Validate content
                is_valid, errors, record_count = self._validate_csv_content(local_path, status_queue)
                
                if is_valid:
                    # Archive valid file to root archive folder with current date suffix
                    try:
                        current_date = datetime.now().strftime("%Y%m%d")
                        base_name = filename.replace('.CSV', '').replace('.csv', '')
                        archive_filename = f"{base_name}_{current_date}.CSV"
                        archive_path = self.archive_dir / archive_filename
                        
                        local_path.rename(archive_path)
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
                    # Move invalid file to error directory
                    error_file = self.error_dir / filename
                    local_path.rename(error_file)
                    
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
    """Main GUI application"""
    def __init__(self, root):
        self.root = root
        self.root.title("HelixSoft Clinical Data Processor")
        self.root.geometry("1100x850")
        
        self.processor = None
        self.validator = None
        self.is_processing = False
        
        self.all_files = []
        self.displayed_files = []
        
        self.ftp_host = tk.StringVar(value="localhost")
        self.ftp_user = tk.StringVar(value="Steph")
        self.ftp_pass = tk.StringVar(value="lolol132")
        self.remote_dir = tk.StringVar(value="")
        self.download_dir = tk.StringVar(value=str(Path.home() / "ClinicalData" / "Downloads"))
        self.archive_dir = tk.StringVar(value=str(Path.home() / "ClinicalData" / "Archive"))
        self.error_dir = tk.StringVar(value=str(Path.home() / "ClinicalData" / "Errors"))
        self.search_var = tk.StringVar()
        
        self.create_widgets()
        self.setup_directories()
    
    def setup_directories(self):
        for var in [self.download_dir, self.archive_dir, self.error_dir]:
            Path(var.get()).mkdir(parents=True, exist_ok=True)
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ftp_frame = ttk.LabelFrame(main_frame, text="FTP Connection Settings", padding="15")
        ftp_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        ttk.Label(ftp_frame, text="Host:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Entry(ftp_frame, textvariable=self.ftp_host, width=30).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(ftp_frame, text="Username:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Entry(ftp_frame, textvariable=self.ftp_user, width=30).grid(row=1, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(ftp_frame, text="Password:").grid(row=2, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Entry(ftp_frame, textvariable=self.ftp_pass, show="*", width=30).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Connect/Disconnect buttons side by side
        btn_frame_ftp = ttk.Frame(ftp_frame)
        btn_frame_ftp.grid(row=2, column=2, padx=(10, 0))
        
        self.connect_btn = ttk.Button(btn_frame_ftp, text="🔌 Connect", command=self.connect_to_server, width=12)
        self.connect_btn.pack(side=tk.LEFT, padx=2)
        
        self.disconnect_btn = ttk.Button(btn_frame_ftp, text="❌ Disconnect", command=self.disconnect_from_server, width=12, state=tk.DISABLED)
        self.disconnect_btn.pack(side=tk.LEFT, padx=2)
        
        file_frame = ttk.LabelFrame(main_frame, text="Server Files", padding="15")
        file_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))
        
        search_frame = ttk.Frame(file_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 10))
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=35)
        self.search_entry.pack(side=tk.LEFT)
        self.search_entry.bind('<KeyRelease>', self.filter_file_list)
        
        ttk.Button(search_frame, text="🔍 Search", command=self.filter_file_list).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(search_frame, text="🔄 Refresh", command=self.refresh_file_list).pack(side=tk.RIGHT)
        
        list_container = ttk.Frame(file_frame)
        list_container.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Changed to SINGLE selection mode
        self.file_listbox = Listbox(list_container, selectmode=SINGLE, yscrollcommand=scrollbar.set, height=12, width=50)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar.config(command=self.file_listbox.yview)
        self.file_listbox.bind('<<ListboxSelect>>', self.on_file_selection_change)
        
        dir_frame = ttk.LabelFrame(main_frame, text="Local Directories", padding="15")
        dir_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15), padx=(15, 0))
        
        directories = [
            ("Download:", self.download_dir),
            ("Archive:", self.archive_dir),
            ("Errors:", self.error_dir)
        ]
        
        for i, (label, var) in enumerate(directories):
            ttk.Label(dir_frame, text=label).grid(row=i, column=0, sticky=tk.W, padx=(0, 10))
            ttk.Entry(dir_frame, textvariable=var, width=45).grid(row=i, column=1, sticky=tk.W, pady=5, padx=(0, 5))
            ttk.Button(dir_frame, text="Browse...", command=lambda v=var: self.browse_directory(v)).grid(row=i, column=2)
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(0, 15))
        
        self.validate_btn = ttk.Button(btn_frame, text="🔍 Validate Selected File", command=self.validate_selected, state=tk.DISABLED)
        self.validate_btn.grid(row=0, column=0, padx=5)
        
        self.process_btn = ttk.Button(btn_frame, text="🚀 Process Selected File", command=self.process_selected, state=tk.DISABLED)
        self.process_btn.grid(row=0, column=1, padx=5)
        
        ttk.Button(btn_frame, text="📂 Open Error Log", command=self.open_error_log).grid(row=0, column=2, padx=5)
        ttk.Button(btn_frame, text="🗑️ Clear Log", command=self.clear_log).grid(row=0, column=3, padx=5)
        
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=2, column=0, columnspan=2, sticky=tk.E, pady=(0, 10))
        
        self.status_label = ttk.Label(status_frame, text="Disconnected", foreground="red")
        self.status_label.pack()
        
        log_frame = ttk.LabelFrame(main_frame, text="Processing Log", padding="10")
        log_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=18, width=110, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        self.log_text.tag_configure("info", foreground="#0066cc")
        self.log_text.tag_configure("success", foreground="#009900")
        self.log_text.tag_configure("warning", foreground="#ff9900")
        self.log_text.tag_configure("error", foreground="#cc0000")
        self.log_text.tag_configure("complete", foreground="#0099cc", font=("TkDefaultFont", 10, "bold"))
        self.log_text.tag_configure("summary", foreground="#9900cc", font=("TkDefaultFont", 10, "bold"))
        self.log_text.tag_configure("file", font=("TkDefaultFont", 9, "bold"))
        
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.status_queue = queue.Queue()
        self.root.after(100, self.check_queue)
    
    def browse_directory(self, var):
        path = filedialog.askdirectory()
        if path:
            var.set(path)
    
    def log_message(self, message, tag="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n", tag)
        self.log_text.see(tk.END)
    
    def check_queue(self):
        try:
            while True:
                message, tag = self.status_queue.get_nowait()
                self.log_message(message, tag)
                
                if tag in ["complete", "error"]:
                    if hasattr(self, 'validate_btn'):
                        self.validate_btn.config(state=tk.NORMAL, text="🔍 Validate Selected File")
                    if hasattr(self, 'process_btn'):
                        self.process_btn.config(state=tk.NORMAL, text="🚀 Process Selected File")
                    if hasattr(self, 'progress'):
                        self.progress.stop()
                    self.is_processing = False
        except queue.Empty:
            pass
        
        self.root.after(100, self.check_queue)
    
    def update_status_label(self):
        """Update connection status and button states immediately"""
        if self.processor and self.processor.connected:
            self.status_label.config(text=f"🟢 Connected to {self.ftp_host.get()}", foreground="green")
            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
        else:
            self.status_label.config(text="🔴 Disconnected", foreground="red")
            self.connect_btn.config(state=tk.NORMAL)
            self.disconnect_btn.config(state=tk.DISABLED)
            self.validate_btn.config(state=tk.DISABLED)
            self.process_btn.config(state=tk.DISABLED)
    
    def on_file_selection_change(self, event):
        selection = self.file_listbox.curselection()
        # Enable buttons only if connected AND a file is selected
        if selection and self.processor and self.processor.connected:
            self.validate_btn.config(state=tk.NORMAL)
            self.process_btn.config(state=tk.NORMAL)
        else:
            self.validate_btn.config(state=tk.DISABLED)
            self.process_btn.config(state=tk.DISABLED)
    
    def connect_to_server(self):
        if self.is_processing:
            return
        
        if not all([self.ftp_host.get(), self.ftp_user.get(), self.ftp_pass.get()]):
            messagebox.showerror("Missing Information", "Please fill in all FTP connection fields.")
            return
        
        self.log_text.delete(1.0, tk.END)
        self.is_processing = True
        self.progress.start()
        
        thread = threading.Thread(target=self._connect_and_load_files)
        thread.daemon = True
        thread.start()
    
    def _connect_and_load_files(self):
        try:
            if not self.processor:
                self.processor = ClinicalDataProcessor(
                    self.ftp_host.get(),
                    self.ftp_user.get(),
                    self.ftp_pass.get(),
                    self.remote_dir.get()
                )
            
            if self.processor.connect(self.status_queue):
                self.all_files = self.processor.get_file_list(self.status_queue)
                # Keep connection alive
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
        """Manually disconnect from FTP server"""
        if self.is_processing:
            return
        
        if not self.processor:
            messagebox.showwarning("Not Connected", "You are not connected to any server.")
            return
        
        self.log_text.delete(1.0, tk.END)
        self.is_processing = True
        self.progress.start()
        
        thread = threading.Thread(target=self._disconnect_worker)
        thread.daemon = True
        thread.start()
    
    def _disconnect_worker(self):
        """Worker thread for disconnect"""
        try:
            if self.processor:
                self.processor.disconnect()
                self.all_files = []
                self.root.after(0, self.update_file_listbox)
                self.root.after(0, self.update_status_label)  # Force immediate status update
                self.status_queue.put(("✅ Disconnected from FTP server", "success"))
            
            self.status_queue.put(("complete", "complete"))
        except Exception as e:
            self.status_queue.put((f"🚨 Disconnect failed: {e}", "error"))
            self.status_queue.put(("complete", "complete"))
    
    def update_file_listbox(self):
        self.file_listbox.delete(0, tk.END)
        self.displayed_files = self.all_files.copy()
        for file in self.displayed_files:
            self.file_listbox.insert(tk.END, file)
        self.log_message(f"📁 Loaded {len(self.displayed_files)} files from server", "info")
        self.filter_file_list()
    
    def filter_file_list(self, event=None):
        """Filter files and show error if no results"""
        search_term = self.search_var.get().lower()
        self.file_listbox.delete(0, tk.END)
        self.displayed_files = [f for f in self.all_files if search_term in f.lower()]
        
        for file in self.displayed_files:
            self.file_listbox.insert(tk.END, file)
        
        # Show error if search yields no results
        if search_term and not self.displayed_files:
            self.log_message(f"❌ No files found matching '{search_term}'", "error")
        elif search_term and self.displayed_files:
            self.log_message(f"🔍 Filtered: showing {len(self.displayed_files)} files matching '{search_term}'", "info")
    
    def refresh_file_list(self):
        """Refresh file list and clear search box"""
        if not self.processor:
            messagebox.showwarning("Not Connected", "Please connect to the FTP server first.")
            return
        
        if self.is_processing:
            return
        
        # Clear search entry
        self.search_var.set("")
        
        self.log_text.delete(1.0, tk.END)
        self.is_processing = True
        self.progress.start()
        
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
        
        # Get single selected file
        selected_file = self.displayed_files[selection[0]]
        
        self.log_text.delete(1.0, tk.END)
        self.is_processing = True
        self.validate_btn.config(state=tk.DISABLED, text="⏳ Validating...")
        self.process_btn.config(state=tk.DISABLED)
        self.progress.start()
        
        self.validator = ClinicalDataValidator(
            self.download_dir.get(),
            self.archive_dir.get(),
            self.error_dir.get()
        )
        
        thread = threading.Thread(target=self._validate_selected_worker, args=([selected_file],))
        thread.daemon = True
        thread.start()
    
    def _validate_selected_worker(self, files):
        try:
            if not self.processor.connected:
                self.processor.connect(self.status_queue)
            
            self.validator.validate_selected_files(self.processor.ftp, files, self.status_queue)
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
        
        # Get single selected file
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
        self.process_btn.config(state=tk.DISABLED, text="⏳ Processing...")
        self.progress.start()
        
        self.validator = ClinicalDataValidator(
            self.download_dir.get(),
            self.archive_dir.get(),
            self.error_dir.get()
        )
        
        thread = threading.Thread(target=self._process_selected_worker, args=([selected_file],))
        thread.daemon = True
        thread.start()
    
    def _process_selected_worker(self, files):
        try:
            if not self.processor.connected:
                self.processor.connect(self.status_queue)
            
            self.validator.process_selected_files(self.processor.ftp, files, self.status_queue)
            self.status_queue.put(("complete", "complete"))
        except Exception as e:
            self.status_queue.put((f"🚨 Processing failed: {e}", "error"))
            self.status_queue.put(("complete", "complete"))
    
    def open_error_log(self):
        error_log_path = Path(self.error_dir.get()) / "error_report.log"
        if error_log_path.exists():
            os.startfile(error_log_path) if os.name == 'nt' else os.system(f'open "{error_log_path}"')
        else:
            messagebox.showinfo("Error Log", "No errors have been logged yet.")
    
    def clear_log(self):
        self.log_text.delete(1.0, tk.END)

def main():
    root = tk.Tk()
    app = ClinicalDataGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()