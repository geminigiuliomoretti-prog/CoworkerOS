"""
Fixture centralizzata per l'isolamento dei database SQLite durante i test automatici di CoworkerOS.
Garantisce che backend/coworkers.db (produzione) non venga mai aperto o modificato dai test.
"""
import os
import atexit
import tempfile
from pathlib import Path

# Directory temporanea isolata per la sessione di test
_TEST_TEMP_DIR = tempfile.TemporaryDirectory(prefix="coworkeros_isolated_test_")
_TEST_DB_PATH = Path(_TEST_TEMP_DIR.name) / "test_isolated.db"

# Imposta immediatamente la variabile d'ambiente globale per la configurazione DB
os.environ["COWORKEROS_DB_PATH"] = str(_TEST_DB_PATH)

def get_test_db_path() -> Path:
    return _TEST_DB_PATH

def cleanup_test_env():
    try:
        _TEST_TEMP_DIR.cleanup()
    except Exception:
        pass

atexit.register(cleanup_test_env)
