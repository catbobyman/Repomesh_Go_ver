"""Create a dedicated Matrix room, run race fixture, retain each run's outputs."""
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import secrets
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("matrix_live", ROOT / "scripts/matrix-live-validation.py")
matrix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(matrix)
state = json.loads((ROOT / "private/matrix-live-state.json").read_text(encoding="utf-8-sig"))
a = state["instances"]["a"]
run_id = secrets.token_hex(5)
room = matrix.ok("a", "POST", "/_matrix/client/v3/createRoom", a["users"]["alice"]["token"], {
    "preset": "private_chat", "name": "Controller MCP precise race " + run_id,
    "invite": [a["users"]["bob"]["user_id"]],
    "initial_state": [{"type": "m.room.history_visibility", "state_key": "", "content": {"history_visibility": "joined"}}]})["room_id"]
matrix.ok("a", "POST", "/_matrix/client/v3/join/" + matrix.q(room), a["users"]["bob"]["token"], {})
config = {"run_id": run_id, "room": room, "token": a["users"]["bob"]["token"],
          "user_id": a["users"]["bob"]["user_id"], "source_dir": "/tmp/repomesh-race-mcp-" + run_id}
(ROOT / "private" / ("control-race-" + run_id + ".json")).write_text(json.dumps(config, indent=2), encoding="utf-8")
target = "/tmp/control-race-live-" + run_id + ".py"
for source, destination in ((ROOT / "upstream/plugins/teamharness/mcp", config["source_dir"]),
                            (ROOT / "scripts/control-race-live-container.py", target)):
    done = subprocess.run(["docker", "cp", str(source), "rv-a-controller:" + destination], capture_output=True, text=True)
    if done.returncode:
        raise SystemExit("Copy into run-specific harness path failed; no service configuration modified")
process = subprocess.run(["docker", "exec", "-i", "rv-a-controller", "python3", target],
                         input=json.dumps(config), capture_output=True, text=True, encoding="utf-8", timeout=420)
out = process.stdout.replace(config["token"], "[REDACTED]")
err = process.stderr.replace(config["token"], "[REDACTED]")
stem = ROOT / "evidence" / ("control-race-live-" + run_id)
stem.with_suffix(".stdout.json").write_text(out, encoding="utf-8")
stem.with_suffix(".stderr.log").write_text(err, encoding="utf-8")
stem.with_suffix(".exitcode").write_text(str(process.returncode) + "\n", encoding="utf-8")
try:
    result = json.loads(out)
except ValueError:
    raise SystemExit("Race harness output is not JSON; redacted original output retained")
source_hash = hashlib.sha256((ROOT / "upstream/plugins/teamharness/mcp/server.py").read_bytes()).hexdigest()
summary = {"at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "run_id": run_id,
           "exit_code": process.returncode, "evidence": stem.with_suffix(".stdout.json").name,
           "host_source_sha256": source_hash, "source_matches_host": source_hash == result.get("source_sha256_before"),
           "observations": [{"id": r["id"], "status": r["status"], "classification": r.get("observed", {}).get("classification"),
                             "error": r.get("error")} for r in result.get("results", [])]}
stem.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
sys.exit(process.returncode)
