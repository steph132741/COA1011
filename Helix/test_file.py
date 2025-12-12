import requests
import uuid
from datetime import datetime
from pathlib import Path

# Path for automated test error logs
ERROR_DIR = Path("Errors")
ERROR_DIR.mkdir(exist_ok=True)
ERROR_LOG = ERROR_DIR / "uuid_integration_test.log"


def generate_uuid_from_api():

    response = requests.get("https://www.uuidtools.com/api/generate/v1", timeout=5)

    if response.status_code != 200:
        raise ConnectionError(
            f"API returned status code {response.status_code}"
        )

    data = response.json()
    return data[0]  # UUID string


def log_error(message):
    fallback_uuid = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = (
        f"[{timestamp}] Fallback UUID: {fallback_uuid} "
        f"| Error: {message}\n"
    )

    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(log_entry)

    print("❌ Error logged:", log_entry.strip())


def test_uuid_api_connection():
    print("🧪 Running UUID API Integration Test...")

    try:
        api_uuid = generate_uuid_from_api()
        print("✅ API UUID Generated Successfully:", api_uuid)

    except Exception as e:
        print("❌ API UUID generation failed:", str(e))
        log_error(str(e))


if __name__ == "__main__":
    test_uuid_api_connection()