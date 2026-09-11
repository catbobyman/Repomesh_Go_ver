#!/usr/bin/env python3
"""Prepare/start only rv-c AgentTeams validation instances.

Default is a read-only plan. --apply is required for resource creation/start.
No deletion, image pulling, broad cleanup, Manager activation, or model request.
All resource reuse requires exact validation ownership labels.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

RUN_ID = "agentteams-2026-09-10"
OWNER_KEY = "repomesh.validation.run"
INSTANCE_KEY = "repomesh.validation.instance"
IMAGE = "repomesh-validation/embedded:517caff9"
MANAGER_IMAGE = "repomesh-validation/manager-qwenpaw:517caff9"
WORKER_IMAGE = "repomesh-validation/qwenpaw-worker:eeaab643"
OLD_COMMIT = "eeaab64391ccaec9118e84977f538aefd40720d6"
NEW_COMMIT = "517caff9280242a00a4d4c06365352b9e41659c6"
REUSED_IMAGE_IDS = {
    WORKER_IMAGE: "sha256:4951052caa5ee7e3ea33a823f5f630de358bda31cd672d1d4a736d88d2ed0d58",
}
PROVIDER_KEYS = ("AGENTTEAMS_LLM_PROVIDER", "AGENTTEAMS_OPENAI_BASE_URL",
                 "AGENTTEAMS_DEFAULT_MODEL", "AGENTTEAMS_LLM_API_KEY")
SECRET_KEYS = ("admin_password", "minio_password", "registration_token",
               "manager_password", "manager_gateway_key", "as_token", "hs_token")


class DeploymentError(Exception):
    pass


def docker(*arguments, allow_failure=False):
    result = subprocess.run(["docker", *map(str, arguments)], capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=120)
    if result.returncode and not allow_failure:
        # No docker inspect JSON or container logs are emitted here: either can
        # contain credentials. The caller can inspect its own run separately.
        raise DeploymentError(f"Docker {arguments[0]} failed (exit {result.returncode}); inspect the named validation resource locally")
    return result


def inspect(kind, name):
    result = docker(kind, "inspect", name, allow_failure=True)
    if result.returncode:
        return None
    values = json.loads(result.stdout)
    return values[0] if isinstance(values, list) else values


def write_json(path, value, private=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if private and path.parent != path.parent.resolve():
        raise DeploymentError("Private directory must not be a redirected path")
    temporary = path.with_name(path.name + ".new")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        temporary.chmod(0o600 if private else 0o644)
    os.replace(temporary, path)


def restrict_private_directory(path):
    path.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        path.chmod(0o700)
        return
    identity = subprocess.run(["whoami"], capture_output=True, text=True, timeout=15)
    if identity.returncode:
        raise DeploymentError("Cannot determine current Windows identity for private directory ACL")
    current = identity.stdout.strip()
    # Only changes ACL on this validation private directory, never ancestors.
    # Preserve explicit entries already set by the parent task; remove inherited
    # entries and grant the executing user, SYSTEM and local Administrators.
    result = subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r",
                             f"{current}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F",
                             "*S-1-5-32-544:(OI)(CI)F"], capture_output=True,
                            text=True, timeout=20)
    if result.returncode:
        raise DeploymentError("Cannot restrict validation private directory ACL; no secrets written")


def labels_for(instance):
    return {OWNER_KEY: RUN_ID, INSTANCE_KEY: instance}


def image_provenance(root):
    source = root / "upstream"
    scopes = ["manager", "qwenpaw", "copaw", "plugins", "shared/lib", ".dockerignore"]
    check = subprocess.run(["git", "-c", f"safe.directory={source.as_posix()}", "-C", str(source),
                            "diff", "--name-only", OLD_COMMIT, NEW_COMMIT, "--", *scopes],
                           capture_output=True, text=True, timeout=20)
    if check.returncode or check.stdout.strip():
        raise DeploymentError("Runtime build inputs differ or could not be verified; do not reuse old runtime images")
    values = []
    for tag, expected in REUSED_IMAGE_IDS.items():
        img = inspect("image", tag)
        if not img or img["Id"] != expected:
            raise DeploymentError(f"Expected reused runtime image ID not present for {tag}")
        values.append({"tag": tag, "image_id": img["Id"], "image_created": img["Created"],
                       "status": "REUSED_2026_09_09_IMAGE_NOT_NEW_BUILD", "runtime_source_unchanged": True})
    manager = inspect("image", MANAGER_IMAGE)
    return {"old_commit": OLD_COMMIT, "new_commit": NEW_COMMIT, "compared_source_scopes": scopes,
            "git_diff_names": [], "runtime_images": values,
            "manager_image": {"tag": MANAGER_IMAGE, "image_present": manager is not None,
                              "image_id": manager["Id"] if manager else None,
                              "status": "NEW_TAG_PRESENT_BUILD_PROVENANCE_OWNED_BY_ROOT" if manager else "WAITING_FOR_ROOT_NEW_MANAGER_BUILD",
                              "reason": "Manager must rebuild with 517caff9 controller because its Dockerfile copies the agt CLI"},
            "dependency_caveat": "Existing image dependencies/artifacts are reused exactly; this does not attest to a fresh rebuild or refreshed dependencies"}


def require_owned(resource, instance, name, kind):
    labels = resource.get("Labels") if kind in {"network", "volume"} else resource.get("Config", {}).get("Labels")
    labels = labels or {}
    if any(labels.get(key) != value for key, value in labels_for(instance).items()):
        raise DeploymentError(f"Refusing to reuse unrelated {kind} {name}; no resource was deleted")


def ensure_resource(kind, name, instance):
    current = inspect(kind, name)
    if current:
        require_owned(current, instance, name, kind)
        return "reused"
    args = [kind, "create"]
    for key, value in labels_for(instance).items():
        args += ["--label", f"{key}={value}"]
    if kind == "network":
        args += ["--driver", "bridge"]
    docker(*args, name)
    return "created"


def plan(root, instance):
    if instance != "c":
        raise DeploymentError("Only isolated instance c is permitted")
    base = 48000
    name = f"rv-{instance}"
    directory = root / "runtime" / f"instance-{instance}"
    return {"instance": instance, "name": name, "container": f"{name}-controller",
            "network": f"{name}-net", "data_volume": f"{name}-data",
            "agentfs_volume": f"{name}-agentfs", "directory": str(directory),
            "workspace": str(directory / "workspace"), "host_share": str(directory / "host-share"),
            "env_file": str(root / "private" / f"{name}-controller.env"),
            "gateway_port": base + 80, "console_port": base + 1,
            "api_port": base + 90, "element_port": base + 88,
            "manager_console_port_reserved": base + 99,
            "manager_enabled": False, "image": IMAGE,
            "published_ports": {"8080/tcp": base + 80, "8001/tcp": base + 1,
                                "8090/tcp": base + 90, "8088/tcp": base + 88}}


def port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def get_secrets(root, instance):
    path = root / "private" / f"rv-{instance}-secrets.json"
    if path.exists():
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if value.get("run_id") != RUN_ID or value.get("instance") != instance:
            raise DeploymentError("Existing validation secret file has unexpected ownership")
        if any(not isinstance(value.get(key), str) or len(value[key]) < 32 for key in SECRET_KEYS):
            raise DeploymentError("Existing validation secret file is incomplete; refusing to regenerate keys")
        return value
    value = {"run_id": RUN_ID, "instance": instance,
             **{key: secrets.token_hex(32) for key in SECRET_KEYS}}
    write_json(path, value, private=True)
    return value


def load_provider(root, enabled):
    if not enabled:
        return {}
    path = root / "private" / "provider.json"
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if any(not isinstance(data.get(key), str) or not data[key].strip() for key in PROVIDER_KEYS):
        raise DeploymentError("Saved provider.json must contain the four required nonempty provider fields")
    if any("\n" in data[key] or "\r" in data[key] for key in PROVIDER_KEYS):
        raise DeploymentError("Saved provider fields cannot contain newline characters")
    return {key: data[key] for key in PROVIDER_KEYS}


def environment(configuration, values, provider):
    name = configuration["name"]
    result = {
        "AGENTTEAMS_KUBE_MODE": "embedded", "AGENTTEAMS_DATA_DIR": "/data/agentteams-controller",
        "AGENTTEAMS_CONTROLLER_NAME": name, "AGENTTEAMS_RESOURCE_PREFIX": name + "-",
        "AGENTTEAMS_RESOURCE_AUTOPREFIX": "true", "AGENTTEAMS_PROXY_CONTAINER_PREFIX": name + "-worker-",
        "AGENTTEAMS_DOCKER_NETWORK": configuration["network"],
        "AGENTTEAMS_CONTROLLER_URL": f"http://{configuration['container']}:8090",
        "AGENTTEAMS_PROXY_SOCKET": "/var/run/docker.sock", "AGENTTEAMS_HTTP_ADDR": ":8090",
        "AGENTTEAMS_MATRIX_URL": "http://127.0.0.1:6167", "AGENTTEAMS_MATRIX_DOMAIN": f"{name}.matrix.invalid",
        "AGENTTEAMS_FS_ENDPOINT": "http://127.0.0.1:9000", "AGENTTEAMS_FS_BUCKET": name + "-storage",
        "AGENTTEAMS_MINIO_ENDPOINT": "http://127.0.0.1:9000", "AGENTTEAMS_MINIO_BUCKET": name + "-storage",
        "AGENTTEAMS_STORAGE_PREFIX": "agentteams/" + name + "-storage",
        "AGENTTEAMS_AI_GATEWAY_URL": "http://127.0.0.1:8080",
        "AGENTTEAMS_AI_GATEWAY_ADMIN_URL": "http://127.0.0.1:8001",
        "AGENTTEAMS_ADMIN_USER": name + "-admin", "AGENTTEAMS_ADMIN_PASSWORD": values["admin_password"],
        "AGENTTEAMS_MINIO_USER": name + "-minio", "AGENTTEAMS_MINIO_PASSWORD": values["minio_password"],
        "AGENTTEAMS_REGISTRATION_TOKEN": values["registration_token"],
        "AGENTTEAMS_MANAGER_PASSWORD": values["manager_password"],
        "AGENTTEAMS_MANAGER_GATEWAY_KEY": values["manager_gateway_key"],
        "AGENTTEAMS_MATRIX_APPSERVICE_ENABLED": "true",
        "AGENTTEAMS_MATRIX_APPSERVICE_ID": name + "-controller",
        "AGENTTEAMS_MATRIX_APPSERVICE_SENDER_LOCALPART": name + "-controller",
        "AGENTTEAMS_MATRIX_APPSERVICE_AS_TOKEN": values["as_token"],
        "AGENTTEAMS_MATRIX_APPSERVICE_HS_TOKEN": values["hs_token"],
        "AGENTTEAMS_MANAGER_ENABLED": "false", "AGENTTEAMS_MANAGER_RUNTIME": "qwenpaw",
        "AGENTTEAMS_MANAGER_IMAGE": MANAGER_IMAGE, "AGENTTEAMS_DEFAULT_WORKER_RUNTIME": "qwenpaw",
        "AGENTTEAMS_QWENPAW_WORKER_IMAGE": WORKER_IMAGE,
        "AGENTTEAMS_PORT_MANAGER_CONSOLE": str(configuration["manager_console_port_reserved"]),
        "AGENTTEAMS_DEFAULT_MODEL": "qwen3.6-plus", "AGENTTEAMS_LLM_PROVIDER": "openai-compat",
        "AGENTTEAMS_LLM_API_KEY": "", "AGENTTEAMS_EMBEDDING_MODEL": "", "AGENTTEAMS_MATRIX_E2EE": "0",
        "AGENTTEAMS_ELEMENT_HOMESERVER_URL": f"http://127.0.0.1:{configuration['gateway_port']}",
        "AGENTTEAMS_CMS_TRACES_ENABLED": "false", "AGENTTEAMS_CMS_METRICS_ENABLED": "false",
        "AGENTTEAMS_LANGUAGE": "zh", "AGENTTEAMS_MC_MIRROR_SCOPE": "controller", "TZ": "UTC",
    }
    result.update(provider)
    # No WORKSPACE_DIR/HOST_SHARE_DIR is passed yet: Manager is disabled, and
    # a Linux Docker API needs the daemon's source path, not a guessed Windows
    # drive path. We record actual .Mounts.Source after create below for the
    # separate, reviewed Manager enablement step.
    return result


def write_environment(path, env):
    if any("\n" in value or "\r" in value for value in env.values()):
        raise DeploymentError("Container env values cannot contain newline characters")
    temporary = path.with_name(path.name + ".new")
    temporary.write_text("".join(f"{key}={value}\n" for key, value in env.items()), encoding="utf-8")
    if os.name != "nt":
        temporary.chmod(0o600)
    os.replace(temporary, path)


def check_existing_container(current, configuration, image_id, desired_env):
    require_owned(current, configuration["instance"], configuration["container"], "container")
    if current.get("Image") != image_id:
        raise DeploymentError(f"Existing {configuration['container']} image differs; explicit review/recreation required")
    env = dict(value.split("=", 1) for value in current.get("Config", {}).get("Env", []) if "=" in value)
    if any(env.get(key) != value for key, value in desired_env.items()):
        raise DeploymentError(f"Existing {configuration['container']} configuration differs; refusing to silently reuse/recreate")
    networks = current.get("NetworkSettings", {}).get("Networks", {})
    if set(networks) != {configuration["network"]}:
        raise DeploymentError(f"Existing {configuration['container']} has unexpected networks")
    bindings = current.get("HostConfig", {}).get("PortBindings", {})
    for target, host in configuration["published_ports"].items():
        if bindings.get(target) != [{"HostIp": "127.0.0.1", "HostPort": str(host)}]:
            raise DeploymentError(f"Existing {configuration['container']} has unexpected port bindings")
    if set(bindings) != set(configuration["published_ports"]):
        raise DeploymentError(f"Existing {configuration['container']} publishes extra ports")
    mounts = {v["Destination"]: v for v in current.get("Mounts", [])}
    for destination, key in [("/data", "data_volume"), ("/root/agentteams-fs", "agentfs_volume")]:
        if mounts.get(destination, {}).get("Name") != configuration[key]:
            raise DeploymentError("Existing instance mounts unexpected data; no older validation volume may be reused")


def start_instance(root, configuration, image_id, provider):
    instance = configuration["instance"]
    container = configuration["container"]
    current = inspect("container", container)
    if current:
        require_owned(current, instance, container, "container")
    for key in ("workspace", "host_share"):
        directory = Path(configuration[key])
        if not directory.resolve().is_relative_to(root.resolve()):
            raise DeploymentError("Instance directory must remain inside the validation root")
        directory.mkdir(parents=True, exist_ok=True)
    values = get_secrets(root, instance)
    desired_env = environment(configuration, values, provider)
    if current:
        check_existing_container(current, configuration, image_id, desired_env)
    elif any(not port_free(port) for port in configuration["published_ports"].values()):
        raise DeploymentError(f"One of the requested localhost ports is occupied for {container}")
    write_environment(Path(configuration["env_file"]), desired_env)
    resource_actions = {}
    for kind, key in (("network", "network"), ("volume", "data_volume"), ("volume", "agentfs_volume")):
        resource_actions[key] = ensure_resource(kind, configuration[key], instance)
    if not current:
        args = ["create", "--name", container, "--network", configuration["network"],
                "--network-alias", configuration["name"] + ".matrix.invalid",
                "--env-file", configuration["env_file"], "--restart", "unless-stopped"]
        for key, value in labels_for(instance).items():
            args += ["--label", f"{key}={value}"]
        args += ["--mount", f"type=volume,source={configuration['data_volume']},target=/data",
                 "--mount", f"type=volume,source={configuration['agentfs_volume']},target=/root/agentteams-fs",
                 "--mount", f"type=bind,source={configuration['workspace']},target=/root/agentteams-fs/agents/manager",
                 "--mount", f"type=bind,source={configuration['host_share']},target=/validation-host-share",
                 "-v", "//var/run/docker.sock:/var/run/docker.sock"]
        for target, host in configuration["published_ports"].items():
            args += ["-p", f"127.0.0.1:{host}:{target}"]
        docker(*args, IMAGE)
        resource_actions["container"] = "created"
    else:
        resource_actions["container"] = "reused"
    current = inspect("container", container)
    if not current.get("State", {}).get("Running"):
        docker("start", container)
    current = inspect("container", container)
    sources = {mount["Destination"]: mount["Source"] for mount in current.get("Mounts", [])}
    workspace_source = sources.get("/root/agentteams-fs/agents/manager")
    share_source = sources.get("/validation-host-share")
    if not workspace_source or not share_source:
        raise DeploymentError(f"Cannot record required daemon bind sources for {container}")
    write_json(root / "private" / f"{configuration['name']}-hostpaths.json", {
        "run_id": RUN_ID, "instance": instance, "manager_enabled": False,
        "AGENTTEAMS_WORKSPACE_DIR": workspace_source,
        "AGENTTEAMS_HOST_SHARE_DIR": share_source,
        "status": "Observed Controller bind sources; actual child mount must be tested before model tasks",
    }, private=True)
    return {**configuration, "image_id": image_id, "container_id": current["Id"],
            "actions": resource_actions, "container_running": current["State"]["Running"],
            "provider_injected": bool(provider), "manager_enabled": False,
            "health_and_initialization": "NOT_YET_CHECKED", "model_execution": "NOT_TESTED",
            "daemon_hostpaths_recorded": True}


def wait_health(configuration, seconds):
    deadline = time.monotonic() + seconds
    url = f"http://127.0.0.1:{configuration['api_port']}/healthz"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return "HTTP_HEALTHZ_200_ONLY"
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(2)
    return "HEALTHZ_TIMEOUT_OTHER_INITIALIZATION_UNKNOWN"


def service_snapshot(configuration):
    result = {"at_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    for name, url in [("matrix_versions", "http://127.0.0.1:6167/_matrix/client/versions"),
                      ("minio_live", "http://127.0.0.1:9000/minio/health/live")]:
        response = docker("exec", configuration["container"], "curl", "--max-time", "3", "-s", "-o", "/dev/null", "-w", "%{http_code}", url, allow_failure=True)
        result[name] = {"http_status": response.stdout.strip(), "curl_exit": response.returncode}
    for kind in ["workers", "managers"]:
        response = docker("exec", configuration["container"], "agt", "get", kind, "-o", "json", allow_failure=True)
        if response.returncode:
            result[kind] = {"exit_code": response.returncode, "count": None}
        else:
            result[kind] = {"exit_code": 0, "count": len(json.loads(response.stdout).get(kind, []))}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="create/start only exact labeled validation resources")
    parser.add_argument("--instances", default="c", choices=["c"], help="only isolated instance c")
    parser.add_argument("--wait-seconds", type=int, default=0, help="optional healthz wait per instance; never means full Ready")
    options = parser.parse_args()
    instances = options.instances.split(",")
    if instances != ["c"]:
        raise DeploymentError("--instances must be c")
    if not 0 <= options.wait_seconds <= 60:
        raise DeploymentError("--wait-seconds must be between 0 and 60")
    root = Path(__file__).resolve().parents[1]
    if root.name != RUN_ID:
        raise DeploymentError("Deployment root must be the new isolated run directory")
    configurations = [plan(root, instance) for instance in instances]
    provenance = image_provenance(root)
    if not options.apply:
        image = inspect("image", IMAGE)
        resources = {name: inspect(kind, name) is not None for kind, name in
                     [("container", "rv-c-controller"), ("volume", "rv-c-data"),
                      ("volume", "rv-c-agentfs"), ("network", "rv-c-net")]}
        print(json.dumps({"mode": "READ_ONLY_PLAN_NO_RESOURCES_OR_SECRETS_CREATED", "run_id": RUN_ID,
                          "manager_enabled": False, "with_provider": False, "instances": configurations,
                          "embedded_image_present": image is not None,
                          "embedded_image_id": image["Id"] if image else None,
                          "existing_resources": resources,
                          "localhost_ports_available": {str(port): port_free(port) for port in configurations[0]["published_ports"].values()},
                          "image_provenance": provenance}, indent=2))
        return 0
    info = docker("info", "--format", "{{.OSType}} {{.Architecture}}")
    if not info.stdout.strip().startswith("linux "):
        raise DeploymentError("This deployment requires a Linux-container Docker daemon")
    image = inspect("image", IMAGE)
    if not image:
        raise DeploymentError(f"Required newly built image {IMAGE} is absent; no image was pulled")
    if not provenance["manager_image"]["image_present"]:
        raise DeploymentError(f"Required new Manager image {MANAGER_IMAGE} is absent; no resources created")
    restrict_private_directory(root / "private")
    provider = {}
    results = []
    for configuration in configurations:
        value = start_instance(root, configuration, image["Id"], provider)
        if options.wait_seconds:
            value["health_and_initialization"] = wait_health(configuration, options.wait_seconds)
        value["service_snapshot"] = service_snapshot(configuration)
        results.append(value)
        print(f"{configuration['container']}: running={value['container_running']}; manager=false; provider_injected={bool(provider)}; API=http://127.0.0.1:{configuration['api_port']}")
        write_json(root / "evidence" / "deployment-instance-inventory.json", {
            "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "run_id": RUN_ID, "instances": results,
            "image_provenance": provenance,
            "warning": "Container start/health is not initializer, runtime, model, or RepoMesh acceptance",
        })
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DeploymentError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        # Do not dump configs/tracebacks: they may include provider material.
        print(f"Deployment stopped: {exc}", file=sys.stderr)
        raise SystemExit(1)
