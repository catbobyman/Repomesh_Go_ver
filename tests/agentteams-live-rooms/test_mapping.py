#!/usr/bin/env python3
"""Offline mapping rules. Does not start AgentTeams or import product web/."""

import unittest

from mapping import annotate_node_role, annotate_workflows, apply_controller_roles, map_room


class MapRoomTest(unittest.TestCase):
    def test_manager_dm(self):
        mapped = map_room(room_id="!a:hs", name="Manager: default", kind="direct_room", meta={"managerName": "default"})
        self.assertEqual(mapped["repomeshRole"], "manager_admin_dm")

    def test_team_room(self):
        mapped = map_room(room_id="!b:hs", name="Team: demo", kind="team_room", meta={"teamName": "demo"})
        self.assertEqual(mapped["repomeshRole"], "leader_collaboration")

    def test_task_room(self):
        mapped = map_room(room_id="!c:hs", name="TASK：demo-1", kind="task_room", meta={"lifecycle": "ephemeral"})
        self.assertEqual(mapped["repomeshRole"], "issue_work_surface")

    def test_at_docs_leader_room(self):
        mapped = map_room(
            room_id="!d:hs",
            name="Worker: lead",
            kind="worker_room",
            meta={"workerName": "lead", "leaderWorker": {"workerName": "lead"}},
        )
        self.assertEqual(mapped["repomeshRole"], "at_docs_leader_room")

    def test_leader_dm(self):
        mapped = map_room(room_id="!e:hs", name="Leader DM: lead", kind="direct_room", meta={"leaderWorker": {"workerName": "lead"}})
        self.assertEqual(mapped["repomeshRole"], "leader_admin_dm")

    def test_controller_marks_leader_worker_room(self):
        rooms = [
            {
                "roomId": "!lead-room:hs",
                "roomKind": "worker_room",
                "mapping": map_room(room_id="!lead-room:hs", name="Worker: lead", kind="worker_room", meta={"workerName": "lead"}),
            }
        ]
        apply_controller_roles(rooms, {"workers": {"workers": [{"name": "lead", "role": "team_leader", "roomID": "!lead-room:hs"}]}})
        self.assertEqual(rooms[0]["mapping"]["repomeshRole"], "at_docs_leader_room")

    def test_unassigned_node_needs_worker_role(self):
        node = annotate_node_role(
            {"id": "rd-02", "name": "后端", "status": "pending"},
            {"live-dev": {"name": "live-dev", "role": "worker", "matrixUserID": "@live-dev:hs"}},
            {"requiredRole": "worker", "labelZh": "需要 Worker"},
        )
        self.assertTrue(node["needsRoleAssignment"])
        self.assertEqual(node["requiredRole"], "worker")
        self.assertEqual(node["roleLabelZh"], "需要 Worker")

    def test_assigned_leader_matches_controller_role(self):
        node = annotate_node_role(
            {"id": "rd-01", "name": "拆解", "status": "completed", "assignee": "live-lead"},
            {
                "live-lead": {
                    "name": "live-lead",
                    "role": "team_leader",
                    "matrixUserID": "@live-lead:matrix-local.agentteams.io:18080",
                }
            },
            {"requiredRole": "team_leader"},
        )
        self.assertFalse(node["needsRoleAssignment"])
        self.assertEqual(node["assignedRole"], "team_leader")
        self.assertIn("live-lead", node["roleLabelZh"])

    def test_workflow_marks_ready_unassigned(self):
        graphs = [
            {
                "projectId": "live-role-dag",
                "workflow": {
                    "nodes": [
                        {"id": "rd-01", "name": "拆解", "status": "completed", "assignee": "live-lead"},
                        {"id": "rd-02", "name": "后端", "status": "pending"},
                    ],
                    "next": ["rd-02"],
                },
            }
        ]
        spec = {"projectId": "live-role-dag", "nodes": {"rd-02": {"requiredRole": "worker", "labelZh": "需要 Worker"}}}
        controller = {"workers": {"workers": [{"name": "live-lead", "role": "team_leader", "matrixUserID": "@live-lead:hs"}]}}
        out = annotate_workflows(graphs, controller, spec)
        self.assertEqual(out[0]["needsRoleAssignment"], ["rd-02"])
        self.assertTrue(out[0]["workflow"]["nodes"][1]["needsRoleAssignment"])
        self.assertFalse(out[0]["workflow"]["nodes"][0]["needsRoleAssignment"])


if __name__ == "__main__":
    unittest.main()
