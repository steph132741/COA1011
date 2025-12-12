import uuid
from datetime import datetime
from pathlib import Path


class ErrorLoggerTest:
    def __init__(self):
        # Create an Errors folder for testing
        self.error_dir = Path("Errors")
        self.error_dir.mkdir(exist_ok=True)

    def _generate_guid(self):
        """Generate a simple UUID for testing."""
        return str(uuid.uuid4())

    def _log_error(self, filename, error_details):
        """
        Test version of the logging function.
        Writes a timestamp, GUID, file name and error message.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        guid = self._generate_guid()
        log_entry = (
            f"[{timestamp}] GUID: {guid} | File: {filename} | Error: {error_details}\n"
        )

        error_log_path = self.error_dir / "error_report.log"
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(log_entry)

        return guid, log_entry


def run_test():
    print("🔍 Running Error Logging Test...")

    tester = ErrorLoggerTest()

    # Test values
    filename = "test_data.csv"
    error_details = "Missing required column: patient_id"

    guid, entry = tester._log_error(filename, error_details)

    print("✅ GUID Generated:", guid)
    print("📄 Log Entry Written:")
    print(entry)

    log_path = Path("Errors/error_report.log")
    if log_path.exists():
        print("📁 Test Passed: error_report.log created.")
    else:
        print("❌ Test Failed: Log file not found.")


if __name__ == "__main__":
    run_test()
