"""Print the SHA-256 of a question file, to send before the file itself.

    python seal.py questions_template.csv
"""
import hashlib
import sys
from pathlib import Path

data = Path(sys.argv[1]).read_bytes()
print(f"{hashlib.sha256(data).hexdigest()}  {sys.argv[1]}  ({len(data)} bytes)")
