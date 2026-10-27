import os
import tempfile
from pathlib import Path

_TEST_DIR = tempfile.TemporaryDirectory(
    prefix="coworkeros_test_"
)

os.environ["COWORKEROS_TEST_MODE"] = "1"
os.environ["COWORKEROS_DB_PATH"] = str(
    Path(_TEST_DIR.name) / "coworkeros_test.db"
)
