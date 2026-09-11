"""Dedicated room/paths for real artifact tests; retain outputs per run."""
import base64
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
    "preset": "private_chat", "name": "Attachment attempts validation " + run_id,
    "invite": [a["users"]["bob"]["user_id"]],
    "initial_state": [{"type": "m.room.history_visibility", "state_key": "", "content": {"history_visibility": "joined"}}]})["room_id"]
matrix.ok("a", "POST", "/_matrix/client/v3/join/" + matrix.q(room), a["users"]["bob"]["token"], {})
config = {"run_id": run_id, "room": room, "publisher_token": a["users"]["bob"]["token"],
          "publisher_id": a["users"]["bob"]["user_id"], "recipient_token": a["users"]["alice"]["token"],
          "recipient_id": a["users"]["alice"]["user_id"], "source_dir": "/tmp/repomesh-artifacts-mcp-" + run_id,
          "team": "coverage-race-32447df06f", "shared_prefix": "agentteams/rv-a-storage/teams/coverage-race-32447df06f/shared"}
(ROOT / "private" / ("control-artifacts-" + run_id + ".json")).write_text(json.dumps(config, indent=2), encoding="utf-8")
target = "/tmp/control-artifacts-live-" + run_id + ".py"
for source, destination in ((ROOT / "upstream/plugins/teamharness/mcp", config["source_dir"]),
                            (ROOT / "scripts/control-artifacts-live-container.py", target)):
    p = subprocess.run(["docker", "cp", str(source), "rv-a-controller:" + destination], capture_output=True)
    if p.returncode:
        raise SystemExit("Copy into isolated fixture path failed")
process = subprocess.run(["docker", "exec", "-i", "rv-a-controller", "python3", target], input=json.dumps(config),
                         capture_output=True, text=True, encoding="utf-8", timeout=240)
out, err = process.stdout, process.stderr
for token in (config["publisher_token"], config["recipient_token"]):
    out, err = out.replace(token, "[REDACTED]"), err.replace(token, "[REDACTED]")
stem = ROOT / "evidence" / ("control-artifacts-live-" + run_id)
stem.with_suffix(".stdout.json").write_text(out, encoding="utf-8")
stem.with_suffix(".stderr.log").write_text(err, encoding="utf-8")
stem.with_suffix(".exitcode").write_text(str(process.returncode) + "\n", encoding="utf-8")
result = json.loads(out)
downloads = ROOT / "evidence" / ("control-artifacts-live-" + run_id + "-downloads")
downloads.mkdir(exist_ok=True)
for index, item in enumerate(result.get("downloads", []), 1):
    if item["http_status"] == 200:
        (downloads / (f"{index:02d}-" + Path(item["source_path"]).name)).write_bytes(base64.b64decode(item["bytes_b64"]))
summary = {"run_id": run_id, "exit_code": process.returncode, "error": result.get("error"),
           "source_matches_host": result.get("source_sha256_before") == hashlib.sha256((ROOT / "upstream/plugins/teamharness/mcp/server.py").read_bytes()).hexdigest(),
           "new_metadata_and_files_unchanged": result.get("new_metadata_and_files_unchanged"),
           "old_original_media_still_original": result.get("old_original_media_still_original"),
           "downloads": len(result.get("downloads", [])),
           "permission_observation": result.get("recipient_leave_observation"),
           "evidence": stem.with_suffix(".stdout.json").name}
stem.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
sys.exit(process.returncode)
