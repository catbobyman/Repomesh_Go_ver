#!/usr/bin/env python3
"""Review, then explicitly replace selected validation Controllers to enable Managers.

Default only reads Docker state and writes a redacted plan. --apply requires the
exact review fingerprint from that plan. No pull, volume removal, worker/manager
container removal, automatic rollback, or model task submission is performed.
Starting the enabled Controller lets upstream create its default Manager, whose
bootstrap may contact the configured provider. Only isolated c may be selected with --instances c.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import subprocess
import sys

sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location("validation_deploy", Path(__file__).with_name("deploy-instances.py"))
deploy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deploy)
Error = deploy.DeploymentError
ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_TARGET = "/root/agentteams-fs/agents/manager"
SHARE_TARGET = "/validation-host-share"
CHANGED_KEYS = set(deploy.PROVIDER_KEYS) | {
    "AGENTTEAMS_MANAGER_ENABLED", "AGENTTEAMS_MANAGER_MODEL",
    "AGENTTEAMS_WORKSPACE_DIR", "AGENTTEAMS_HOST_SHARE_DIR",
}
PUBLIC_ENV = {
    "AGENTTEAMS_MANAGER_ENABLED", "AGENTTEAMS_MANAGER_MODEL", "AGENTTEAMS_DEFAULT_MODEL",
    "AGENTTEAMS_LLM_PROVIDER", "AGENTTEAMS_MANAGER_RUNTIME", "AGENTTEAMS_MANAGER_IMAGE",
    "AGENTTEAMS_DEFAULT_WORKER_RUNTIME", "AGENTTEAMS_QWENPAW_WORKER_IMAGE",
    "AGENTTEAMS_WORKSPACE_DIR", "AGENTTEAMS_HOST_SHARE_DIR", "AGENTTEAMS_PORT_MANAGER_CONSOLE",
    "AGENTTEAMS_MATRIX_DOMAIN", "AGENTTEAMS_CONTROLLER_NAME", "AGENTTEAMS_CONTROLLER_URL",
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_json(path):
    if not path.is_file() or path.is_symlink():
        raise Error(f"Required regular file missing or redirected: {path.name}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_env(path):
    if not path.is_file() or path.is_symlink():
        raise Error("Saved Controller env file must be a regular file")
    result = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise Error("Saved Controller env contains a malformed line")
        key, value = line.split("=", 1)
        if key in result:
            raise Error("Saved Controller env contains duplicate keys")
        result[key] = value
    return result


def container_env(current):
    values = current["Config"].get("Env") or []
    result = dict(value.split("=", 1) for value in values if "=" in value)
    if len(result) != len(values):
        raise Error("Controller effective environment contains duplicate/malformed entries")
    return result


def source_is_local_path(source, local_path):
    """Check the observed Desktop mapping; never supply a guessed path to Docker."""
    if os.name == "nt":
        local = PureWindowsPath(str(local_path))
        if not local.drive or len(local.drive) != 2 or local.drive[1] != ":":
            return False
        expected = "/run/desktop/mnt/host/" + local.drive[0].lower() + "/" + "/".join(local.parts[1:])
        return source.replace("\\", "/").casefold() == expected.casefold()
    return source == str(Path(local_path).resolve())


def validate_mounts(current, configuration, hostpaths):
    expected_targets = {"/data", "/root/agentteams-fs", WORKSPACE_TARGET, SHARE_TARGET, "/var/run/docker.sock"}
    mounts = {mount["Destination"]: mount for mount in current.get("Mounts", [])}
    if len(mounts) != len(current.get("Mounts", [])) or set(mounts) != expected_targets:
        raise Error("Controller mount destinations differ from the reviewed five-mount layout")
    for target, key in (("/data", "data_volume"), ("/root/agentteams-fs", "agentfs_volume")):
        mount = mounts[target]
        if mount.get("Type") != "volume" or mount.get("Name") != configuration[key] or not mount.get("RW"):
            raise Error("Controller persistent volume mount differs from the instance plan")
    for target, key, envkey in ((WORKSPACE_TARGET, "workspace", "AGENTTEAMS_WORKSPACE_DIR"),
                               (SHARE_TARGET, "host_share", "AGENTTEAMS_HOST_SHARE_DIR")):
        mount = mounts[target]
        local = Path(configuration[key])
        if not local.is_dir() or not local.resolve().is_relative_to(ROOT / "runtime" / ("instance-" + configuration["instance"])):
            raise Error("Instance bind directory is absent or resolves outside its dedicated runtime directory")
        if mount.get("Type") != "bind" or not mount.get("RW") or not mount["Source"].startswith("/"):
            raise Error("Controller workspace/share must be writable Linux daemon bind mounts")
        if hostpaths.get(envkey) != mount["Source"] or not source_is_local_path(mount["Source"], local.resolve()):
            raise Error("Observed bind Source does not match both saved hostpaths and this instance directory")
    socket = mounts["/var/run/docker.sock"]
    if socket.get("Type") != "bind" or socket.get("Source") not in {"/var/run/docker.sock", "//var/run/docker.sock"} or not socket.get("RW"):
        raise Error("Controller Docker socket differs from the reviewed bind")
    return mounts


def manager_inventory(container):
    result = deploy.docker("exec", container, "agt", "get", "managers", "-o", "json")
    data = json.loads(result.stdout)
    if not isinstance(data.get("managers"), list):
        raise Error("Manager list did not return the expected API schema")
    # Enabling the reconciler acts on all matching existing Manager CRs. This
    # first-enable script requires an empty set instead of quietly waking one.
    if data["managers"]:
        raise Error("Manager CRs already exist; inspect their model/image/state separately before enabling")
    return []


def validate_base_configuration(current, configuration, embedded, saved, values, hostpaths):
    deploy.require_owned(current, configuration["instance"], configuration["container"], "container")
    if current.get("Name") != "/" + configuration["container"]:
        raise Error("Container name differs from the exact selected Controller")
    if not current.get("State", {}).get("Running"):
        raise Error("Controller must already be running and available for first-enable preflight")
    if current.get("Image") != embedded["Id"]:
        raise Error("Controller is not using the current locally built embedded image ID")
    if current["Config"].get("Image") not in {deploy.IMAGE, embedded["Id"]}:
        raise Error("Controller image reference is outside this validation build")
    baseline = deploy.environment(configuration, values, {})
    # This script only transitions from the original no-provider baseline.
    if saved != baseline:
        raise Error("Saved Controller env no longer matches the original no-provider, Manager=false baseline")
    effective = container_env(current)
    image_env = dict(item.split("=", 1) for item in embedded.get("Config", {}).get("Env", []) if "=" in item)
    expected_effective = {**image_env, **saved}
    if effective != expected_effective:
        raise Error("Controller effective env has unreviewed additions or differences from its image and saved env")
    deploy.check_existing_container(current, configuration, embedded["Id"], saved)
    mounts = validate_mounts(current, configuration, hostpaths)
    host = current["HostConfig"]
    if host.get("RestartPolicy") != {"Name": "unless-stopped", "MaximumRetryCount": 0}:
        raise Error("Controller restart policy differs from its original deployment")
    for field in ("Privileged", "ReadonlyRootfs", "AutoRemove"):
        if host.get(field):
            raise Error("Controller has an unexpected Docker host setting")
    for field in ("CapAdd", "CapDrop", "Devices", "DeviceRequests", "SecurityOpt", "ExtraHosts", "VolumesFrom", "Links"):
        if host.get(field):
            raise Error("Controller has additional Docker host settings requiring separate review")
    for field in ("Entrypoint", "Cmd", "User", "WorkingDir"):
        if current["Config"].get(field) != embedded.get("Config", {}).get(field):
            raise Error("Controller overrides an image execution setting")
    network = current["NetworkSettings"]["Networks"][configuration["network"]]
    if network.get("Aliases") != [configuration["name"] + ".matrix.invalid"]:
        raise Error("Controller network aliases differ from the dedicated Matrix domain")
    return effective, mounts


def prepare(instance, embedded, manager_image, worker_image, provider):
    configuration = deploy.plan(ROOT, instance)
    current = deploy.inspect("container", configuration["container"])
    if not current:
        raise Error("Selected Controller does not exist; this script never installs a replacement for a missing instance")
    values = read_json(ROOT / "private" / f"rv-{instance}-secrets.json")
    hostpaths = read_json(ROOT / "private" / f"rv-{instance}-hostpaths.json")
    for value in (values, hostpaths):
        if value.get("run_id") != deploy.RUN_ID or value.get("instance") != instance:
            raise Error("Private config ownership does not match the selected instance")
    if any(not isinstance(values.get(key), str) or len(values[key]) < 32 for key in deploy.SECRET_KEYS):
        raise Error("Existing secrets are incomplete; no key is generated by this script")
    saved = parse_env(Path(configuration["env_file"]))
    effective, mounts = validate_base_configuration(current, configuration, embedded, saved, values, hostpaths)
    for kind, key in (("network", "network"), ("volume", "data_volume"), ("volume", "agentfs_volume")):
        resource = deploy.inspect(kind, configuration[key])
        if not resource:
            raise Error("Required existing network or volume is missing")
        deploy.require_owned(resource, instance, configuration[key], kind)
    if not deploy.port_free(configuration["manager_console_port_reserved"]):
        raise Error("Reserved localhost Manager console port is occupied")
    managers = manager_inventory(configuration["container"])
    desired = {**effective, **provider,
               "AGENTTEAMS_MANAGER_ENABLED": "true",
               "AGENTTEAMS_MANAGER_MODEL": provider["AGENTTEAMS_DEFAULT_MODEL"],
               "AGENTTEAMS_WORKSPACE_DIR": mounts[WORKSPACE_TARGET]["Source"],
               "AGENTTEAMS_HOST_SHARE_DIR": mounts[SHARE_TARGET]["Source"]}
    changed = sorted(key for key in set(effective) | set(desired) if effective.get(key) != desired.get(key))
    if set(changed) - CHANGED_KEYS:
        raise Error("Desired environment changes contain an unexpected field")
    return {"configuration": configuration, "before": current, "saved_env": saved,
            "effective_env": effective, "desired_env": desired, "mounts": mounts,
            "changed_env_keys": changed, "manager_crs_before": managers,
            "embedded_image_id": embedded["Id"], "manager_image_id": manager_image["Id"] if manager_image else None,
            "worker_image_id": worker_image["Id"] if worker_image else None}


def review_payload(prepared):
    return [{"instance": p["configuration"]["instance"], "container_id": p["before"]["Id"],
             "image_id": p["embedded_image_id"], "manager_image_id": p["manager_image_id"],
             "worker_image_id": p["worker_image_id"], "effective_env_digest": digest(p["effective_env"]),
             "desired_env_digest": digest(p["desired_env"]), "mounts": p["mounts"],
             "network_id": p["before"]["NetworkSettings"]["Networks"][p["configuration"]["network"]]["NetworkID"],
             "ports": p["before"]["HostConfig"]["PortBindings"]} for p in prepared]


def redact_prepared(p):
    c = p["configuration"]
    return {"instance": c["instance"], "controller": c["container"], "container_id_before": p["before"]["Id"],
            "image_id": p["embedded_image_id"], "manager_image_id": p["manager_image_id"],
            "worker_image_id": p["worker_image_id"], "changed_env_keys": p["changed_env_keys"],
            "public_configuration_before": {k: v for k, v in p["effective_env"].items() if k in PUBLIC_ENV},
            "public_configuration_after": {k: v for k, v in p["desired_env"].items() if k in PUBLIC_ENV},
            "provider_api_key_present": bool(p["desired_env"].get("AGENTTEAMS_LLM_API_KEY")),
            "provider_endpoint_recorded_privately": True, "volumes_preserved": [c["data_volume"], c["agentfs_volume"]],
            "network_preserved": c["network"], "ports_preserved": c["published_ports"],
            "mounts_before": list(p["mounts"].values()), "manager_crs_before": p["manager_crs_before"],
            "secrets_regenerated": False, "model_task_submitted": False}


def create_arguments(p, env_path):
    c = p["configuration"]
    arguments = ["create", "--name", c["container"], "--network", c["network"],
                 "--network-alias", c["name"] + ".matrix.invalid", "--env-file", str(env_path),
                 "--restart", "unless-stopped"]
    for key, value in p["before"]["Config"].get("Labels", {}).items():
        arguments += ["--label", f"{key}={value}"]
    for target in ("/data", "/root/agentteams-fs", WORKSPACE_TARGET, SHARE_TARGET, "/var/run/docker.sock"):
        mount = p["mounts"][target]
        if target == "/var/run/docker.sock":
            arguments += ["-v", mount["Source"] + ":" + target]
        else:
            source = mount["Name"] if mount["Type"] == "volume" else mount["Source"]
            arguments += ["--mount", f"type={mount['Type']},source={source},target={target}"]
    for target, host in c["published_ports"].items():
        arguments += ["-p", f"127.0.0.1:{host}:{target}"]
    arguments.append(p["embedded_image_id"])
    return arguments


def replace_controller(p, fingerprint):
    c = p["configuration"]
    tag = f"{c['name']}-enable-{fingerprint[:12]}"
    env_path = ROOT / "private" / (tag + ".env")
    deploy.write_environment(env_path, p["desired_env"])
    deploy.write_json(ROOT / "private" / (tag + "-before-inspect.json"), p["before"], private=True)
    deploy.write_json(ROOT / "private" / (tag + "-before-env.json"), p["saved_env"], private=True)
    evidence_path = ROOT / "evidence" / (tag + ".json")
    evidence = {"run_id": deploy.RUN_ID, "review_sha256": fingerprint, "recorded_at_utc": utc(),
                "status": "PREPARED_NO_STOP_YET", **redact_prepared(p)}
    deploy.write_json(evidence_path, evidence)
    # Re-read identity immediately before stop; use immutable ID for both stop/rm.
    now = deploy.inspect("container", c["container"])
    if not now or now["Id"] != p["before"]["Id"] or container_env(now) != p["effective_env"]:
        raise Error("Controller changed after preflight; no stop or removal performed")
    deploy.require_owned(now, c["instance"], c["container"], "container")
    # Docker inspect emits this array from a map, so order can change between
    # consecutive reads. Compare complete mount entries by destination while
    # retaining duplicates/entry count, rather than weakening the drift guard.
    mounts_now = sorted(now.get("Mounts", []), key=lambda item: item["Destination"])
    mounts_before = sorted(p["before"].get("Mounts", []), key=lambda item: item["Destination"])
    if now.get("Image") != p["embedded_image_id"] or mounts_now != mounts_before:
        raise Error("Controller image or mounts changed after preflight")
    deploy.check_existing_container(now, c, p["embedded_image_id"], p["effective_env"])
    for image_name, image_id in ((deploy.IMAGE, p["embedded_image_id"]),
                                 (deploy.MANAGER_IMAGE, p["manager_image_id"]),
                                 (deploy.WORKER_IMAGE, p["worker_image_id"])):
        image = deploy.inspect("image", image_name)
        if not image or image["Id"] != image_id:
            raise Error("A reviewed local image tag changed before replacement")
    manager_inventory(c["container"])
    try:
        deploy.docker("stop", "--time", "30", now["Id"])
        evidence["status"] = "CONTROLLER_STOPPED_DATA_PRESERVED"
        deploy.write_json(evidence_path, evidence)
        # Deliberately no --force and no --volumes; no other container is named.
        deploy.docker("rm", now["Id"])
        evidence["status"] = "OLD_CONTROLLER_REMOVED_DATA_PRESERVED"
        deploy.write_json(evidence_path, evidence)
        deploy.docker(*create_arguments(p, env_path))
        after = deploy.inspect("container", c["container"])
        deploy.require_owned(after, c["instance"], c["container"], "container")
        deploy.check_existing_container(after, c, p["embedded_image_id"], p["desired_env"])
        validate_mounts(after, c, {"AGENTTEAMS_WORKSPACE_DIR": p["desired_env"]["AGENTTEAMS_WORKSPACE_DIR"],
                                   "AGENTTEAMS_HOST_SHARE_DIR": p["desired_env"]["AGENTTEAMS_HOST_SHARE_DIR"]})
        if container_env(after) != p["desired_env"]:
            raise Error("Replacement effective environment differs from the reviewed environment; not started")
        evidence["status"] = "REPLACEMENT_CREATED_AND_CONFIG_VERIFIED_NOT_STARTED"
        evidence["container_id_after"] = after["Id"]
        deploy.write_json(evidence_path, evidence)
        # New Controller now owns the planned env; preserve original separately.
        deploy.write_environment(Path(c["env_file"]), p["desired_env"])
        deploy.docker("start", after["Id"])
        after = deploy.inspect("container", c["container"])
        deploy.write_json(ROOT / "private" / (tag + "-after-inspect.json"), after, private=True)
        hostpaths_path = ROOT / "private" / (c["name"] + "-hostpaths.json")
        hostpaths = read_json(hostpaths_path)
        hostpaths.update({"manager_enabled": True,
                          "status": "Controller configured with observed daemon paths; actual Manager child mounts still require verification"})
        deploy.write_json(hostpaths_path, hostpaths, private=True)
        evidence.update({"status": "ENABLED_CONTROLLER_STARTED_INITIALIZATION_UNVERIFIED", "completed_at_utc": utc(),
                         "container_running": after["State"]["Running"], "mounts_after": after["Mounts"],
                         "health": "NOT_CHECKED", "manager_runtime": "NOT_YET_VERIFIED", "model_execution": "NOT_TESTED"})
        deploy.write_json(evidence_path, evidence)
        return evidence
    except Exception:
        evidence["failed_at_utc"] = utc()
        evidence["automatic_rollback"] = "NOT_ATTEMPTED; inspect this selected Controller and preserved data before recovery"
        deploy.write_json(evidence_path, evidence)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instances", required=True, choices=("c",))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--review-sha256", help="Exact fingerprint printed by the current read-only plan")
    options = parser.parse_args()
    if options.apply and not options.review_sha256:
        raise Error("--apply requires a reviewed --review-sha256 fingerprint")
    if not deploy.docker("info", "--format", "{{.OSType}}").stdout.strip() == "linux":
        raise Error("The validation deployment requires a Linux Docker daemon")
    embedded = deploy.inspect("image", deploy.IMAGE)
    if not embedded:
        raise Error("Current validation embedded image is absent; no image is pulled")
    manager = deploy.inspect("image", deploy.MANAGER_IMAGE)
    worker = deploy.inspect("image", deploy.WORKER_IMAGE)
    provider = deploy.load_provider(ROOT, True)
    prepared = [prepare(instance, embedded, manager, worker, provider) for instance in options.instances.split(",")]
    fingerprint = digest(review_payload(prepared))
    public_plan = {"run_id": deploy.RUN_ID, "recorded_at_utc": utc(), "mode": "PLAN_NO_DOCKER_MUTATION",
                   "review_sha256": fingerprint, "instances": [redact_prepared(p) for p in prepared],
                   "apply_ready": bool(manager and worker),
                   "note": "Enabling reconciliation can start Manager bootstrap/provider activity. No task is submitted by this script."}
    if not options.apply:
        path = ROOT / "evidence" / ("manager-enable-plan-" + options.instances.replace(",", "-") + ".json")
        deploy.write_json(path, public_plan)
        print(json.dumps(public_plan, ensure_ascii=False, indent=2))
        return 0
    if not manager or not worker:
        raise Error("Both current Manager and Worker image tags must exist before enabling; no image is pulled")
    if options.review_sha256 != fingerprint:
        raise Error("Reviewed fingerprint no longer matches current container/images/env/mounts; review a new plan")
    for p in prepared:
        result = replace_controller(p, fingerprint)
        print(f"{p['configuration']['container']}: {result['status']}; evidence written; Manager/model readiness not asserted")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Error, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        # Avoid raw Docker/HTTP outputs, effective env and provider material.
        print(f"Manager enablement stopped: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
