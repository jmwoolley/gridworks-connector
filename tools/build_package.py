"""Build deterministic component and review ZIPs, with immutable source metadata."""

import hashlib
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
component = root / "custom_components" / "gridworks_connector"
target = root / "dist"
target.mkdir(exist_ok=True)
commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
metadata = {
    "source_repository": "https://github.com/jmwoolley/gridworks-connector",
    "source_commit": commit,
    "version": "0.1.0-beta.3",
    "target_ha": "2026.11.0",
    "protocol_revision": "draft-2026-11-05",
    "protocol_status": "proposed_not_registered",
    "shadow_only": True,
    "physical_actions_supported": False,
}


def package(name, files):
    path = target / name
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        entries = [(file.relative_to(root).as_posix(), file.read_bytes()) for file in files]
        entries.append(("BUILD_INFO.json", (json.dumps(metadata, indent=2) + "\n").encode()))
        for relative, content in sorted(entries):
            if Path(relative).suffix in {".py", ".json", ".yaml", ".yml", ".md", ".toml", ".lock"}:
                content = content.replace(b"\r\n", b"\n")
            info = ZipInfo(relative, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(".zip.sha256").write_text(digest + "  " + path.name + "\n", encoding="utf-8")
    print(path.name, digest)


files = [
    file
    for file in component.rglob("*")
    if file.is_file() and "__pycache__" not in file.parts and file.suffix != ".pyc"
]
package("gridworks-connector-0.1.0-beta.3.zip", files)
review = [file for file in (root / "docs").rglob("*") if file.is_file()]
review += [root / "README.md", root / "pyproject.toml", root / "uv.lock"]
review += [file for file in files if file.suffix in {".py", ".js"}]
review += [root / "tools/shadow_peer.py"]
package("gridworks-connector-review-0.1.0-beta.3.zip", review)
