"""Host orchestration. Dedicated room and state; credentials never printed."""
import importlib.util
import json
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("matrix_live", ROOT / "scripts/matrix-live-validation.py")
matrix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(matrix)
state = json.loads((ROOT / "private/matrix-live-state.json").read_text())
a = state["instances"]["a"]
private = ROOT / "private/teamharness-live-state.json"
if private.exists():
    config = json.loads(private.read_text())
else:
    run_id = secrets.token_hex(5)
    room = matrix.ok("a", "POST", "/_matrix/client/v3/createRoom", a["users"]["alice"]["token"], {
        "preset": "private_chat", "name": "TeamHarness isolated native validation " + run_id,
        "invite": [a["users"]["bob"]["user_id"]]})["room_id"]
    matrix.ok("a", "POST", "/_matrix/client/v3/join/" + matrix.q(room), a["users"]["bob"]["token"], {})
    config = {"run_id": run_id, "room": room, "token": a["users"]["bob"]["token"], "user_id": a["users"]["bob"]["user_id"]}
    private.write_text(json.dumps(config, indent=2))
for source, target in [(ROOT / "upstream/plugins/teamharness/mcp", "/tmp/repomesh-live-mcp"),
                       (ROOT / "scripts/teamharness-live-container.py", "/tmp/teamharness-live-container.py")]:
    done = subprocess.run(["docker", "cp", str(source), f"rv-a-controller:{target}"], capture_output=True, text=True)
    if done.returncode:
        raise SystemExit("Copy into dedicated container failed; output suppressed")
run = subprocess.run(["docker", "exec", "-i", "rv-a-controller", "python3", "/tmp/teamharness-live-container.py"],
                     input=json.dumps(config), capture_output=True, text=True, encoding="utf-8", timeout=300)
output = run.stdout.replace(config["token"], "[REDACTED]")
path = ROOT / "evidence/teamharness-live-results.json"
try:
    result = json.loads(output)
except ValueError:
    (ROOT / "evidence/teamharness-live-harness-error.txt").write_text((run.stderr + output).replace(config["token"], "[REDACTED]"))
    raise SystemExit("Container harness did not return JSON; redacted error saved")
path.write_text(output + "\n", encoding="utf-8")
for case in result["results"]:
    print(json.dumps(case, ensure_ascii=False), flush=True)
print(json.dumps({"exit_code": run.returncode, "evidence": str(path), "trace_entries": len(result["trace"])}))
sys.exit(run.returncode)
