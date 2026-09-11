#!/usr/bin/env python3
"""Offline safety checks for enable-managers.py; never call Docker or write secrets."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("enable_managers", Path(__file__).with_name("enable-managers.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SafetyChecks(unittest.TestCase):
    def setUp(self):
        self.config = module.deploy.plan(module.ROOT, "a")
        self.values = {key: "fixture-only-" + "x" * 64 for key in module.deploy.SECRET_KEYS}
        self.env = module.deploy.environment(self.config, self.values, {})
        self.image = {"Id": "sha256:fixture", "Config": {"Env": [], "Entrypoint": None, "Cmd": None,
                                                       "User": None, "WorkingDir": None}}
        self.hostpaths = {}
        mounts = []
        for target, key, envkey in ((module.WORKSPACE_TARGET, "workspace", "AGENTTEAMS_WORKSPACE_DIR"),
                                   (module.SHARE_TARGET, "host_share", "AGENTTEAMS_HOST_SHARE_DIR")):
            local = Path(self.config[key]).resolve()
            source = "/run/desktop/mnt/host/" + local.drive[0].lower() + "/" + "/".join(local.parts[1:]) if local.drive else str(local)
            self.hostpaths[envkey] = source
            mounts.append({"Type": "bind", "Source": source, "Destination": target, "RW": True})
        for target, key in (("/data", "data_volume"), ("/root/agentteams-fs", "agentfs_volume")):
            mounts.append({"Type": "volume", "Source": "/fixture/" + self.config[key],
                           "Name": self.config[key], "Destination": target, "RW": True})
        mounts.append({"Type": "bind", "Source": "//var/run/docker.sock", "Destination": "/var/run/docker.sock", "RW": True})
        self.current = {"Id": "fixture-original", "Name": "/rv-a-controller", "Image": self.image["Id"],
                        "State": {"Running": True}, "Mounts": mounts,
                        "Config": {"Image": module.deploy.IMAGE, "Labels": module.deploy.labels_for("a"),
                                   "Env": [f"{k}={v}" for k, v in self.env.items()]},
                        "HostConfig": {"RestartPolicy": {"Name": "unless-stopped", "MaximumRetryCount": 0},
                                       "PortBindings": {target: [{"HostIp": "127.0.0.1", "HostPort": str(port)}]
                                                        for target, port in self.config["published_ports"].items()}},
                        "NetworkSettings": {"Networks": {"rv-a-net": {"Aliases": ["rv-a.matrix.invalid"], "NetworkID": "fixture-network"}}}}

    def validate(self, current=None):
        return module.validate_base_configuration(current or self.current, self.config, self.image,
                                                  self.env, self.values, self.hostpaths)

    def test_expected_layout_is_accepted(self):
        effective, mounts = self.validate()
        self.assertEqual(effective, self.env)
        self.assertEqual(len(mounts), 5)

    def test_wrong_instance_label_is_rejected(self):
        bad = copy.deepcopy(self.current)
        bad["Config"]["Labels"][module.deploy.INSTANCE_KEY] = "b"
        with self.assertRaises(module.Error):
            self.validate(bad)

    def test_changed_image_is_rejected(self):
        bad = copy.deepcopy(self.current)
        bad["Image"] = "sha256:older"
        with self.assertRaises(module.Error):
            self.validate(bad)

    def test_wrong_volume_is_rejected(self):
        bad = copy.deepcopy(self.current)
        next(m for m in bad["Mounts"] if m["Destination"] == "/data")["Name"] = "another-project-data"
        with self.assertRaises(module.Error):
            self.validate(bad)

    def test_home_fallback_is_rejected(self):
        bad = copy.deepcopy(self.current)
        next(m for m in bad["Mounts"] if m["Destination"] == module.WORKSPACE_TARGET)["Source"] = "/root/.agentteams/manager"
        with self.assertRaises(module.Error):
            self.validate(bad)

    def test_added_env_and_ports_are_rejected(self):
        for extra in ("env", "port"):
            bad = copy.deepcopy(self.current)
            if extra == "env":
                bad["Config"]["Env"].append("AGENTTEAMS_UNREVIEWED=1")
            else:
                bad["HostConfig"]["PortBindings"]["9999/tcp"] = [{"HostIp": "0.0.0.0", "HostPort": "9999"}]
            with self.subTest(extra=extra), self.assertRaises(module.Error):
                self.validate(bad)

    def test_stale_container_identity_never_stops_or_removes(self):
        current = copy.deepcopy(self.current)
        current["Id"] = "replaced-after-review"
        prepared = {"configuration": self.config, "before": self.current, "saved_env": self.env,
                    "effective_env": self.env, "desired_env": self.env, "mounts": {},
                    "changed_env_keys": [], "manager_crs_before": [],
                    "embedded_image_id": self.image["Id"], "manager_image_id": "fixture-manager", "worker_image_id": "fixture-worker"}
        with patch.object(module.deploy, "write_environment"), patch.object(module.deploy, "write_json"), \
                patch.object(module.deploy, "inspect", return_value=current), patch.object(module.deploy, "docker") as docker:
            with self.assertRaises(module.Error):
                module.replace_controller(prepared, "fixture-fingerprint")
            docker.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
