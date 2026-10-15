"""Isolated API tests: never load local credentials or connect to MySQL."""
import os
import sys
from pathlib import Path

os.environ["DB_PASSWORD"] = "unused-test-value"
os.environ["SECRET_KEY"] = "isolated-upload-validation-test-key"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
