# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
LicenseGuard — open-source license-conflict detection by GenLayer validator consensus.

A maintainer submits a project: its own license plus the licenses of every
dependency it pulls in. `check` has every validator independently reason about
license compatibility (e.g. a strong-copyleft GPL dependency dragged into a
proprietary or permissively-licensed project, or two mutually incompatible
copyleft terms) and decide a single boolean: does this dependency set CONFLICT
with the project license? The verdict is accepted only when validators agree on
that boolean `conflict` (comparative equivalence on the decisive field), not on
the wording of the reasoning or the exact offending list.

The decisive field is `conflict` (bool). The offending licenses and the
reasoning are advisory; the boolean is the consensus output.
"""
import json
from genlayer import *

MAX_DEPS = 100
MAX_OFFENDING = 50


def normalize_check(raw) -> dict:
    """Coerce an LLM judgement into the canonical shape. Never raises.

    normalize_check({}) -> {"conflict": False, "offending": [], "reasoning": "no reasoning"}.
    `conflict` is truthy-coerced to a real bool; `offending` is forced to a list
    of non-empty strings (anything else collapses to [])."""
    if not isinstance(raw, dict):
        raw = {}
    conflict = bool(raw.get("conflict", False))          # truthy coercion -> real bool
    offending = raw.get("offending")
    if isinstance(offending, list):
        offending = [x.strip() for x in offending if isinstance(x, str) and x.strip()][:MAX_OFFENDING]
    else:
        offending = []                                   # non-list -> []
    reasoning = raw.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        reasoning = "no reasoning"
    return {"conflict": conflict, "offending": offending, "reasoning": reasoning[:600]}


def validate_check(data) -> bool:
    """Enforce invariants: conflict is a real bool, offending is a list of
    strings, reasoning is a non-empty string."""
    if not isinstance(data, dict):
        return False
    if not isinstance(data.get("conflict"), bool):
        return False
    off = data.get("offending")
    if not isinstance(off, list) or not all(isinstance(x, str) for x in off):
        return False
    r = data.get("reasoning")
    return isinstance(r, str) and bool(r.strip())


class LicenseGuard(gl.Contract):
    projects: TreeMap[str, str]
    project_count: u256
    checked_count: u256
    conflict_count: u256

    def __init__(self):
        self.project_count = u256(0)
        self.checked_count = u256(0)
        self.conflict_count = u256(0)

    # -------------------------------------------------------------- submit
    @gl.public.write
    def submit_project(self, name: str, project_license: str, dep_licenses: list) -> str:
        name = str(name).strip()
        project_license = str(project_license).strip()
        if not name:
            raise Exception("project name required")
        if not project_license:
            raise Exception("project license required")
        if not isinstance(dep_licenses, list):
            raise Exception("dep_licenses must be a list")
        deps = [str(x).strip()[:100] for x in dep_licenses if str(x).strip()][:MAX_DEPS]
        if not deps:
            raise Exception("at least one dependency license required")
        key = str(int(self.project_count))
        rec = {
            "submitter": str(gl.message.sender_address),
            "name": name[:200],
            "project_license": project_license[:100],
            "dep_licenses": deps,
            "state": "open",            # open -> checked
            "conflict": False,
            "offending": [],
            "reasoning": "",
        }
        self.projects[key] = json.dumps(rec)
        self.project_count += u256(1)
        return key

    # -------------------------------------------------------------- check
    @gl.public.write
    def check(self, project_id: str) -> dict:
        """Consensus reasons about license compatibility and decides `conflict`."""
        project_id = str(project_id)
        if project_id not in self.projects:
            raise Exception("unknown project")
        p = json.loads(self.projects[project_id])
        if p["state"] == "checked":
            raise Exception("project already checked")

        verdict = self._check(p["project_license"], p["dep_licenses"])
        p["conflict"] = verdict["conflict"]
        p["offending"] = verdict["offending"]
        p["reasoning"] = verdict["reasoning"]
        p["state"] = "checked"
        self.projects[project_id] = json.dumps(p)
        self.checked_count += u256(1)
        if verdict["conflict"]:
            self.conflict_count += u256(1)
        return {"project": project_id, "conflict": verdict["conflict"], "offending": verdict["offending"]}

    def _check(self, project_license: str, dep_licenses) -> dict:
        deps_block = ", ".join(dep_licenses) if dep_licenses else "(none)"

        def do_check() -> str:
            prompt = f"""You are an open-source license-compliance auditor. Decide whether the project's
own license is in CONFLICT with any of its dependency licenses.

Consider real incompatibilities, for example:
- strong copyleft (GPL-2.0 / GPL-3.0 / AGPL-3.0) pulled into a Proprietary or closed-source project,
- GPL-only code combined with a permissive project that cannot satisfy copyleft redistribution terms,
- mutually incompatible copyleft terms (e.g. GPL-2.0-only vs Apache-2.0 patent clauses),
- otherwise permissive sets (MIT / BSD / Apache-2.0) under a permissive project are NOT a conflict.

PROJECT LICENSE: {project_license}
DEPENDENCY LICENSES: {deps_block}

Reply ONLY JSON: {{"conflict": true|false, "offending": ["<license>", ...], "reasoning": "<short>"}}
List in "offending" only the dependency licenses that actually create the conflict."""
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(raw, dict):
                try:
                    raw = json.loads(str(raw))
                except Exception:
                    raw = {}
            return json.dumps(normalize_check(raw))

        result = gl.eq_principle.prompt_comparative(
            do_check,
            principle="The boolean 'conflict' must be identical across validators. The offending list and reasoning wording may differ.",
        )
        data = json.loads(result) if isinstance(result, str) else result
        if not validate_check(data):
            data = normalize_check(data if isinstance(data, dict) else {})
        return data

    # -------------------------------------------------------------- views
    @gl.public.view
    def get_project(self, project_id: str) -> dict:
        project_id = str(project_id)
        if project_id not in self.projects:
            return {"exists": False}
        p = json.loads(self.projects[project_id])
        p["exists"] = True
        return p

    @gl.public.view
    def stats(self) -> dict:
        return {
            "total_projects": int(self.project_count),
            "checked": int(self.checked_count),
            "conflicts_found": int(self.conflict_count),
        }
