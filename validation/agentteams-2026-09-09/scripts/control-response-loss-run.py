"""Run abrupt MCP-response-loss fixtures in new room/prefix; keep every output."""
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
a = json.loads((ROOT / "private/matrix-live-state.json").read_text(encoding="utf-8-sig"))["instances"]["a"]
run_id = secrets.token_hex(5)
room = matrix.ok("a", "POST", "/_matrix/client/v3/createRoom", a["users"]["alice"]["token"], {
    "preset": "private_chat", "name": "MCP response loss " + run_id, "invite": [a["users"]["bob"]["user_id"]],
    "initial_state": [{"type": "m.room.history_visibility", "state_key": "", "content": {"history_visibility": "joined"}}]})["room_id"]
matrix.ok("a", "POST", "/_matrix/client/v3/join/" + matrix.q(room), a["users"]["bob"]["token"], {})
config = {"run_id": run_id, "room": room, "token": a["users"]["bob"]["token"], "user_id": a["users"]["bob"]["user_id"],
          "team": "coverage-race-32447df06f", "source_dir": "/tmp/repomesh-response-loss-mcp-" + run_id,
          "shared_prefix": "agentteams/rv-a-storage/teams/coverage-race-32447df06f/shared/response-loss-" + run_id}
(ROOT / "private" / ("control-response-loss-" + run_id + ".json")).write_text(json.dumps(config, indent=2), encoding="utf-8")
target = "/tmp/control-response-loss-" + run_id + ".py"
for source, destination in ((ROOT / "upstream/plugins/teamharness/mcp", config["source_dir"]),
                            (ROOT / "scripts/control-response-loss-container.py", target)):
    process = subprocess.run(["docker", "cp", str(source), "rv-a-controller:" + destination], capture_output=True)
    if process.returncode:
        raise SystemExit("Copy to dedicated response-loss fixture failed")
process = subprocess.run(["docker", "exec", "-i", "rv-a-controller", "python3", target], input=json.dumps(config),
                         capture_output=True, text=True, encoding="utf-8", timeout=240)
out, err = process.stdout.replace(config["token"], "[REDACTED]"), process.stderr.replace(config["token"], "[REDACTED]")
stem = ROOT / "evidence" / ("control-response-loss-" + run_id)
stem.with_suffix(".stdout.json").write_text(out, encoding="utf-8")
stem.with_suffix(".stderr.log").write_text(err, encoding="utf-8")
stem.with_suffix(".exitcode").write_text(str(process.returncode) + "\n", encoding="utf-8")
data = json.loads(out)
children = ROOT / "evidence" / ("control-response-loss-" + run_id + "-children")
children.mkdir(exist_ok=True)
for entry in data["trace"]:
    if entry.get("operation") == "MCP-subprocess":
        child = children / (entry["case"] + "-" + entry["mode"])
        child.with_suffix(".stdout.txt").write_text(entry["stdout"], encoding="utf-8")
        child.with_suffix(".stderr.log").write_text(entry["stderr"], encoding="utf-8")
        child.with_suffix(".exitcode").write_text(str(entry["returncode"]) + "\n", encoding="utf-8")
        child.with_suffix(".observer.json").write_text(json.dumps(entry["observer_sidechannel"], indent=2) + "\n", encoding="utf-8")
summary = {"run_id": run_id, "exit_code": process.returncode, "evidence": stem.with_suffix(".stdout.json").name,
           "source_matches_host": data["source_sha256_before"] == hashlib.sha256((ROOT / "upstream/plugins/teamharness/mcp/server.py").read_bytes()).hexdigest(),
           "observations": [{"id": r["id"], "status": r["status"], "classification": r.get("observed", {}).get("classification"),
                             "error": r.get("error")} for r in data["results"]]}
stem.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
sys.exit(process.returncode)
