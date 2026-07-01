# LicenseGuard

**Detects open-source license conflicts across a dependency set by GenLayer validator consensus.**

[![GenLayer](https://img.shields.io/badge/GenLayer-Bradbury-ff4d6d)](https://genlayer.com) [![chainId](https://img.shields.io/badge/chainId-4221-4dd0e1)](https://docs.genlayer.com) [![contract](https://img.shields.io/badge/contract-Python%20GenVM-8a63d2)](https://docs.genlayer.com) [![tests](https://img.shields.io/badge/tests-10%2F10%20passing-3fb950)](tests) [![License](https://img.shields.io/badge/license-MIT-2dd4bf)](LICENSE)

A maintainer submits a project — its own license plus the licenses of every dependency it pulls in.
`check` has every validator independently reason about license compatibility (e.g. a strong-copyleft
**GPL** dependency dragged into a **proprietary** or permissively-licensed project, or two mutually
incompatible copyleft terms) and decide a single boolean: **does this dependency set conflict with the
project license?** The verdict is accepted only when validators agree on that boolean `conflict` —
comparative equivalence on the decisive field, not on the wording of the reasoning or the exact
offending list. The offending licenses and reasoning are advisory; `conflict` is the consensus output.

- **Contract (Bradbury, chain 4221):** `0xAF6f834f40D5855e9B18e1c199Bff16B1B1f72E7`
- **Explorer:** https://explorer-bradbury.genlayer.com/contract/0xAF6f834f40D5855e9B18e1c199Bff16B1B1f72E7

---

## Why GenLayer is essential

Judging whether a license A is compatible with license B is qualitative reasoning over natural-language
legal terms — there is no deterministic lookup table that captures every copyleft/permissive/proprietary
interaction, dual-licensing nuance, or patent clause. A normal EVM cannot make that call. GenLayer has
every validator independently reason about the licenses and accept a result **only when they agree on the
boolean `conflict`**, turning a subjective compliance judgement into a reproducible on-chain outcome.

## Workflow

| Step | Method | What happens |
| --- | --- | --- |
| Submit | `submit_project(name, project_license, dep_licenses)` | Store the project license + dependency licenses; state `open`. |
| Check | `check(project_id)` | Consensus reasons about compatibility → `conflict` (bool) + offending licenses + reasoning; state `checked`. |
| Read | `get_project(project_id)` | Full record: submitter, licenses, state, verdict. |
| Read | `stats()` | `total_projects`, `checked`, `conflicts_found`. |

### Correctness check

`_check` wraps the local `do_check` in **`gl.eq_principle.prompt_comparative`** with the principle
*"the boolean `conflict` must be identical across validators"* — so a validator that returns the WRONG
verdict (say, calling a GPL-in-proprietary set clean) is caught because its decisive boolean diverges from
the honest majority, **not** because its JSON is shaped differently. The offending list and reasoning
wording are free to vary. `normalize_check` guarantees a safe default (`normalize_check({})` →
`{"conflict": False, "offending": [], "reasoning": "no reasoning"}`), truthy-coerces `conflict` to a real
bool, and forces `offending` to a list of strings; `validate_check` enforces those invariants before the
verdict is stored. State transitions (`open → checked`, no double-check, unknown-id guard) are enforced
on-chain.

## Architecture

```
LicenseGuard/
├── contracts/license_guard.py  ← GenLayer Intelligent Contract (dependency set + consensus conflict verdict)
└── tests/                      ← pytest: normalize/validate guards + full submit → check flow
```

Contract-only — **no frontend**. Nondeterminism is confined to `gl.nondet.exec_prompt` +
`gl.eq_principle.prompt_comparative`; everything else is deterministic and unit-tested.

## Tests

```bash
cd LicenseGuard
python3 -m venv .venv && .venv/bin/pip install pytest -q
.venv/bin/python -m pytest tests -q
```

Covers `normalize_check` / `validate_check` on good and adversarial inputs (non-dict, `offending` not a
list → `[]`, `conflict` truthy coercion), plus a full **submit → check → stats** integration run with
state-transition and re-check guards (the shim auto-inits `TreeMap` and varies `sender_address`).
**10/10 passing.**

## Deploy

```bash
genlayer deploy --contract contracts/license_guard.py
```

After deployment, replace every `0xAF6f834f40D5855e9B18e1c199Bff16B1B1f72E7` token (in this README and `.env.example`) with the
deployed contract address.
