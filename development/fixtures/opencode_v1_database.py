"""Synthetic OpenCode V1 SQLite database for source and generation-parity tests."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "development/fixtures/opencode_v1/schema.sql"


def _json(value: dict) -> str:
    return json.dumps(value, separators=(",", ":"))


def create_v1_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        sessions = [
            ("ses_root", None, "project-a", "/repo", "Root", 1000, 9000, None),
            ("ses_child", "ses_root", "project-a", "/repo", "Child", 2500, 7000, None),
            ("ses_other", None, "project-b", "/other", "Other", 1500, 3000, 2900),
        ]
        connection.executemany(
            "INSERT INTO session(id,parent_id,project_id,directory,title,time_created,time_updated,time_archived) "
            "VALUES(?,?,?,?,?,?,?,?)",
            sessions,
        )
        messages = [
            (
                "msg_user", "ses_root", 1100, 1100,
                _json({
                    "role": "user", "time": {"created": 1100}, "agent": "build",
                    "model": {"providerID": "github-copilot", "modelID": "gpt-test", "variant": "high"},
                }),
            ),
            (
                "msg_assistant", "ses_root", 1200, 1500,
                _json({
                    "role": "assistant", "time": {"created": 1200, "completed": 1500},
                    "parentID": "msg_user", "providerID": "github-copilot", "modelID": "gpt-test",
                    "variant": "high", "agent": "build", "finish": "stop", "cost": 9.99,
                    "tokens": {"input": 999, "output": 999, "reasoning": 999, "cache": {"read": 999, "write": 999}},
                }),
            ),
            (
                "msg_compact", "ses_root", 2000, 2000,
                _json({"role": "user", "time": {"created": 2000}, "agent": "build"}),
            ),
            (
                "msg_summary", "ses_root", 2100, 2300,
                _json({
                    "role": "assistant", "time": {"created": 2100, "completed": 2300},
                    "parentID": "msg_compact", "providerID": "github-copilot", "modelID": "gpt-test",
                    "summary": True, "finish": "stop", "cost": 0.4,
                    "tokens": {"input": 40, "output": 4, "reasoning": 1, "cache": {"read": 3, "write": 2}},
                }),
            ),
            (
                "msg_synthetic", "ses_root", 2400, 2400,
                _json({"role": "user", "time": {"created": 2400}, "agent": "build"}),
            ),
            (
                "msg_child_user", "ses_child", 2600, 2600,
                _json({"role": "user", "time": {"created": 2600}, "agent": "general"}),
            ),
            (
                "msg_child_assistant", "ses_child", 2700, 2800,
                _json({
                    "role": "assistant", "time": {"created": 2700, "completed": 2800},
                    "parentID": "msg_child_user", "providerID": "github-copilot", "modelID": "claude-test",
                    "finish": "stop", "cost": 0.2,
                    "tokens": {"input": 20, "output": 5, "reasoning": 0, "cache": {"read": 2, "write": 1}},
                }),
            ),
        ]
        connection.executemany(
            "INSERT INTO message(id,session_id,time_created,time_updated,data) VALUES(?,?,?,?,?)",
            messages,
        )
        parts = [
            ("prt_user_text", "msg_user", "ses_root", 1101, 1101, _json({"type": "text", "text": "Hello Cost Guard", "synthetic": False})),
            (
                "prt_step_1", "msg_assistant", "ses_root", 1300, 1300,
                _json({
                    "type": "step-finish", "reason": "tool-calls", "cost": 0.1,
                    "tokens": {"input": 100, "output": 10, "reasoning": 2, "cache": {"read": 30, "write": 5}},
                }),
            ),
            (
                "prt_step_2", "msg_assistant", "ses_root", 1450, 1450,
                _json({
                    "type": "step-finish", "reason": "stop", "cost": 0.2,
                    "tokens": {"input": 40, "output": 7, "reasoning": 3, "cache": {"read": 20, "write": 4}},
                }),
            ),
            ("prt_compact", "msg_compact", "ses_root", 2001, 2001, _json({"type": "compaction", "auto": True, "tail_start_id": "msg_user"})),
            ("prt_summary_text", "msg_summary", "ses_root", 2200, 2200, _json({"type": "text", "text": "summary"})),
            (
                "prt_synthetic", "msg_synthetic", "ses_root", 2401, 2401,
                _json({"type": "text", "synthetic": True, "text": "Summarize the task tool output above and continue with your task."}),
            ),
            (
                "prt_child_subtask", "msg_child_user", "ses_child", 2601, 2601,
                _json({
                    "type": "subtask", "prompt": "Inspect module", "description": "Inspect module",
                    "agent": "general", "command": "task",
                    "model": {"providerID": "github-copilot", "modelID": "claude-test"},
                }),
            ),
            ("prt_child_text", "msg_child_assistant", "ses_child", 2750, 2750, _json({"type": "text", "text": "done"})),
        ]
        connection.executemany(
            "INSERT INTO part(id,message_id,session_id,time_created,time_updated,data) VALUES(?,?,?,?,?,?)",
            parts,
        )
        connection.commit()
    finally:
        connection.close()
