"""Exécuter depuis le dépôt : python3 manifests/authentik/tests/run.py."""

import base64
import json
import subprocess
from pathlib import Path


root = Path(__file__).resolve().parents[3]
configuration = dict(
    line.split("=", 1)
    for line in (
        root / "manifests/authentik/integrations/carte-fede-main/base/config.env"
    ).read_text().splitlines()
    if line
)
render = subprocess.run(
    ["kubectl", "kustomize", str(root / "manifests")],
    capture_output=True,
    check=True,
    text=True,
).stdout
payload = {
    "configuration": configuration,
    "blueprint": (root / "manifests/authentik/blueprints/fede.yaml").read_text(),
    "render": render,
}
script = (root / "manifests/authentik/tests/test_blueprint.py").read_bytes()
stdin = base64.b64encode(script) + b"\n" + json.dumps(payload).encode()
command = [
    "kubectl", "-n", "authentik", "exec", "-i", "deployment/authentik-worker",
    "--", "env", "AUTHENTIK_LOG_LEVEL=warning", "ak", "shell", "-c",
    "import sys, base64; source = sys.stdin.readline(); exec(base64.b64decode(source))",
]
result = subprocess.run(command, input=stdin, capture_output=True)
stdout = result.stdout.decode()
if result.returncode:
    print(stdout)
    print(result.stderr.decode())
    raise SystemExit(result.returncode)
passes = [line for line in stdout.splitlines() if line.startswith("PASS :")]
if not passes:
    raise SystemExit("La validation n'a pas confirmé son exécution.")
print("\n".join(passes))
