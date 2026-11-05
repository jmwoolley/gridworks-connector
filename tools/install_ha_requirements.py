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
    constraints = files("homeassistant").joinpath("package_constraints.txt")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--constraint",
            str(constraints),
            *manifest["requirements"],
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
