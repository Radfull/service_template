import hashlib
import io
import subprocess
from pathlib import Path

import pandas as pd

raw = subprocess.check_output([
    "git",
    "show",
    "b027c70161b45d5ee715cde48c0fcb9580950912^:pipelines/data/data.csv",
])

frame = pd.read_csv(io.BytesIO(raw)).drop_duplicates()

content = frame.to_csv(
    index=False,
    lineterminator="\r\n",
).encode("utf-8")

expected_md5 = "c8ee98fd8ec9efea7ba7aca7c9e99198"
actual_md5 = hashlib.md5(content).hexdigest()

if actual_md5 != expected_md5:
    raise RuntimeError(
        f"Wrong dataset: expected {expected_md5}, got {actual_md5}"
    )

path = Path("pipelines/data/data.csv")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_bytes(content)

print(f"Rows: {len(frame)}")
print(f"MD5: {actual_md5}")