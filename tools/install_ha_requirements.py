"""Install manifest requirements through the selected HA release constraints.

Do not bypass Home Assistant package_constraints.txt as a plain development pip
install can pass while the actual HA installer rejects a custom integration.
"""

import json
from importlib.resources import files
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (root / "custom_components/gridworks_connector/manifest.json").read_text()
    )
    requirements = list(manifest["requirements"])
    seen = set()
    pending = list(manifest.get("dependencies", []))
    while pending:
        domain = pending.pop()
        if domain in seen:
            continue
        seen.add(domain)
        source = files("homeassistant").joinpath("components", domain, "manifest.json")
        core_manifest = json.loads(source.read_text())
        requirements.extend(core_manifest.get("requirements", []))
        pending.extend(core_manifest.get("dependencies", []))
    constraints = files("homeassistant").joinpath("package_constraints.txt")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--constraint",
            str(constraints),
            *requirements,
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
