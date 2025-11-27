import os
import re
import csv
import ftplib
import requests
import logging
from tkinter import Tk, Button, Label, messagebox, Listbox, Scrollbar, END, Entry, StringVar, Frame, Toplevel
from datetime import datetime

# === CONFIGURATION ===
VALID_DIR = "valid_files"
ERROR_LOG_DIR = "error_logs"
ERROR_LOG_FILE = os.path.join(ERROR_LOG_DIR, "error_log.txt")
EXPECTED_HEADERS = ["batch_id", "timestamp"] + [f"reading{i}" for i in range(1, 11)]


class FileValidator:
    @staticmethod
    def validate(file_content):
        try:
            reader = csv.reader(file_content.splitlines())
            headers = next(reader, None)

            if headers != EXPECTED_HEADERS:
                return False, f"Incorrect or missing headers: {headers}"

            batch_ids = set()
            for row_num, row in enumerate(reader, start=2):
                if len(row) != 12:
                    return False, f"Row {row_num} has missing columns"

                batch_id = row[0]
                if batch_id in batch_ids:
                    return False, f"Duplicate batch_id {batch_id} on row {row_num}"
                batch_ids.add(batch_id)

                for i, reading in enumerate(row[2:], start=1):
                    try:
                        value = float(reading)
                        if value > 9.9:
                            return False, f"Value exceeds 9.9 in reading{i} on row {row_num}: {value}"
                        if not re.match(r"^\d+(\.\d{1,3})?$", reading):
                            return False, f"Invalid decimal format in reading{i} on row {row_num}: {reading}"
                    except ValueError:
                        return False, f"Non-numeric reading{i} on row {row_num}: {reading}"

        except Exception as e:
            return False, f"Malformed file error: {str(e)}"

        return True, "Valid"


class Logger:
    def __init__(self):
        self.ensure_directories()
        logging.basicConfig(
            filename=ERROR_LOG_FILE,
            filemode='a',
            level=logging.ERROR,
            format="%(asctime)s - ERROR - [UUID: %(uuid)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    def ensure_directories(self):
        os.makedirs(VALID_DIR, exist_ok=True)
        os.makedirs(ERROR_LOG_DIR, exist_ok=True)

    def get_uuid(self):
        try:
            response = requests.get("https://www.uuidtools.com/api/generate/v1")
            response.raise_for_status()
            uuid_list = response.json()
            return uuid_list[0] if uuid_list else "unknown_uuid"
        except:
            return "unknown_uuid"

    def log(self, message):
        uuid = self.get_uuid()
        logging.error(message, extra={"uuid": uuid})


class FTPClient:
    def __init__(self):
        self.ftp = None
        self.remote_files = []
        self.downloaded_files = []

    def connect(self, host, user, password):
        self.ftp = ftplib.FTP(host)
        self.ftp.login(user, password)

    def list_files(self):
        self.remote_files = self.ftp.nlst()
        return self.remote_files

    def download_file(self, filename):
        content = []
        self.ftp.retrlines(f'RETR {filename}', content.append)
        return "\n".join(content)

    def is_connected(self):
        return self.ftp is not None


class App:
    def __init__(self, root):
        self.root = root
        self.ftp_client = FTPClient()
        self.logger = Logger()

        self.file_listbox = None
        self.valid_files_listbox = None
        self.error_logs_listbox = None
        self.build_gui()

    def build_gui(self):
        self.root.title("FTP CSV Validator")
        self.root.geometry("800x600")

        main_frame = Frame(self.root)
        main_frame.pack(padx=10, pady=10, fill="both", expand=True)

        # Connection Frame
        connection_frame = Frame(main_frame)
        connection_frame.pack(fill="x", pady=5)
        Label(connection_frame, text="FTP Connection", font=("Arial", 12, "bold")).pack(anchor="w")
        Button(connection_frame, text="Connect to FTP", command=self.connect_ftp_form, width=20).pack(side="left", padx=5)

        # Available Files Frame
        file_frame = Frame(main_frame)
        file_frame.pack(fill="both", expand=True, pady=5)
        Label(file_frame, text="Available Files", font=("Arial", 12, "bold")).pack(anchor="w", pady=5)

        self.file_listbox = Listbox(file_frame, width=60, height=10)
        self.file_listbox.pack(side="left", fill="both", expand=True)

        scrollbar = Scrollbar(file_frame)
        scrollbar.pack(side="right", fill="y")
        self.file_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.file_listbox.yview)

        # Buttons Frame
        button_frame = Frame(main_frame)
        button_frame.pack(fill="x", pady=5)
        Button(button_frame, text="List Files", command=self.list_files, width=20).pack(side="left", padx=5)
        Button(button_frame, text="Download Selected File", command=self.download_selected_file, width=25).pack(side="left", padx=5)

        # Valid Files Frame
        valid_files_frame = Frame(main_frame)
        valid_files_frame.pack(fill="both", expand=True, pady=5)
        Label(valid_files_frame, text="Valid Files", font=("Arial", 12, "bold")).pack(anchor="w", pady=5)

        self.valid_files_listbox = Listbox(valid_files_frame, width=60, height=5)
        self.valid_files_listbox.pack(side="left", fill="both", expand=True)

        valid_scrollbar = Scrollbar(valid_files_frame)
        valid_scrollbar.pack(side="right", fill="y")
        self.valid_files_listbox.config(yscrollcommand=valid_scrollbar.set)
        valid_scrollbar.config(command=self.valid_files_listbox.yview)

        # Error Logs Frame
        error_logs_frame = Frame(main_frame)
        error_logs_frame.pack(fill="both", expand=True, pady=5)
        Label(error_logs_frame, text="Error Logs", font=("Arial", 12, "bold")).pack(anchor="w", pady=5)

        self.error_logs_listbox = Listbox(error_logs_frame, width=60, height=5)
        self.error_logs_listbox.pack(side="left", fill="both", expand=True)

        error_scrollbar = Scrollbar(error_logs_frame)
        error_scrollbar.pack(side="right", fill="y")
        self.error_logs_listbox.config(yscrollcommand=error_scrollbar.set)
        error_scrollbar.config(command=self.error_logs_listbox.yview)

    def connect_ftp_form(self):
        def connect():
            try:
                self.ftp_client.connect(host_var.get(), user_var.get(), pass_var.get())
                messagebox.showinfo("Success", "Connected to FTP Server")
                ftp_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"FTP connection failed: {e}")

        ftp_window = Toplevel(self.root)
        ftp_window.title("FTP Connection")

        Label(ftp_window, text="Hostname:").grid(row=0, column=0, padx=5, pady=5)
        host_var = StringVar()
        Entry(ftp_window, textvariable=host_var).grid(row=0, column=1, padx=5, pady=5)

        Label(ftp_window, text="Username:").grid(row=1, column=0, padx=5, pady=5)
        user_var = StringVar()
        Entry(ftp_window, textvariable=user_var).grid(row=1, column=1, padx=5, pady=5)

        Label(ftp_window, text="Password:").grid(row=2, column=0, padx=5, pady=5)
        pass_var = StringVar()
        Entry(ftp_window, textvariable=pass_var, show="*").grid(row=2, column=1, padx=5, pady=5)

        Button(ftp_window, text="Connect", command=connect).grid(row=3, column=0, columnspan=2, pady=10)

    def list_files(self):
        if not self.ftp_client.is_connected():
            messagebox.showerror("Error", "Not connected to FTP")
            return
        try:
            self.file_listbox.delete(0, END)
            for file in self.ftp_client.list_files():
                self.file_listbox.insert(END, file)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to list files: {e}")

    def download_selected_file(self):
        if not self.ftp_client.is_connected():
            messagebox.showerror("Error", "Not connected to FTP")
            return

        selected = self.file_listbox.curselection()
        if not selected:
            messagebox.showerror("Error", "No file selected")
            return

        filename = self.file_listbox.get(selected)
        if filename in self.ftp_client.downloaded_files:
            messagebox.showwarning("Warning", f"File '{filename}' already downloaded.")
            return

        try:
            content = self.ftp_client.download_file(filename)
            valid, msg = FileValidator.validate(content)

            if valid:
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                new_filename = f"MED_DATA_{timestamp}.csv"
                path = os.path.join(VALID_DIR, new_filename)
                with open(path, 'w') as f:
                    f.write(content)
                self.ftp_client.downloaded_files.append(filename)
                self.valid_files_listbox.insert(END, new_filename)
                messagebox.showinfo("Success", f"File saved as '{new_filename}' in '{VALID_DIR}'.")
            else:
                self.logger.log(msg)
                self.error_logs_listbox.insert(END, f"[{filename}] {msg}")
                messagebox.showerror("Error", f"Validation failed: {msg}")
        except Exception as e:
            self.logger.log(f"Download error: {str(e)}")
            self.error_logs_listbox.insert(END, f"[{filename}] {str(e)}")
            messagebox.showerror("Error", f"Failed to download/process file: {e}")


if __name__ == '__main__':
    root = Tk()
    app = App(root)
    root.mainloop()