"""Build a component-only ZIP; never include credentials, tests or local databases."""

import hashlib
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
component = root / "custom_components" / "gridworks_connector"
target = root / "dist"
target.mkdir(exist_ok=True)
path = target / "gridworks-connector-0.1.0-beta.1.zip"
with ZipFile(path, "w", ZIP_DEFLATED) as archive:
    for file in sorted(component.rglob("*")):
        if file.is_file() and "__pycache__" not in file.parts and file.suffix != ".pyc":
            archive.write(file, file.relative_to(root))
digest = hashlib.sha256(path.read_bytes()).hexdigest()
(path.with_suffix(".zip.sha256")).write_text(digest + "  " + path.name + "\n", encoding="utf-8")
print(path)
print("SHA256", digest)
