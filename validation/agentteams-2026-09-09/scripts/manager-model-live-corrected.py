"""A new, independently identified UTF-8 verification; never resend initial case."""
import importlib.util
import json
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("manager_live", ROOT / "scripts/manager-model-live.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.evidence = ROOT / "evidence/manager-model-live-corrected.json"
marker = m.state.setdefault("corrected_marker", "RV_MODEL_UTF8_20260909_" + secrets.token_hex(4))
m.save()
body = "这是隔离验证，只回复 " + marker + "，不调用工具或创建资源。"
assert "这是隔离验证" in body
item = m.send_once("corrected", body)
readback = m.matrix.ok("a", "GET", "/_matrix/client/v3/rooms/" + m.matrix.q(m.state["room"]) +
    "/event/" + m.matrix.q(item["event_id"]), m.state["token"])
actual = readback["content"]["body"]
m.record({"kind": "corrected-wire-readback", "event_id": item["event_id"], "intended_body": body,
          "actual_body": actual, "exact_body_match": actual == body})
if actual != body:
    raise SystemExit("UTF-8 readback mismatch; no second send")
success = bool(m.state["corrected"].get("matched_reply")) or m.poll("corrected", marker, 180)
m.record({"kind": "corrected-conclusion", "exact_body_match": True, "matching_manager_response": success,
          "marker": marker, "submission_attempts": 1, "request_event_id": item["event_id"]})
raise SystemExit(0 if success else 1)
