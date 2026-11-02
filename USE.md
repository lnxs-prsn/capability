Find reusable project know-how with its context; open this file before reusing a technique or adding to your project's innovations.

Run the single command with Python 3.9 or newer and the path to this clone's `knowhow.py`, from any directory. It uses Python's standard library and local files. Nothing runs in the background. Nothing is written into your project, and kits are never executed.

Replace `CLONE` below with this clone's path; quote paths containing spaces. Use `python` or your machine's Python 3.9+ launcher. The examples are command invocations, not shell scripts.

On first use, the command asks for the folder containing your projects. With no interactive input it asks you to run `python "CLONE/knowhow.py" configure --projects-folder "PROJECTS"`. It never searches for this folder. A changed projects-folder path starts a separate local namespace.

Ask for what fits the task:

```
python "CLONE/knowhow.py" ask --task "repeatable fixture setup" --project "PROJECT" --limit 5
```

`--project` names an existing project directory inside the configured projects folder, including a new project without `innovations/`. If omitted, the nearest ancestor of your working directory with `.git` or a direct `innovations/` is used. A nested project's nearest marker wins. Without a marker, supply the project explicitly. Project identity is its relative path, not its name; renaming a project changes its identity.

Every ask refreshes all discovered collections, even if their projects are closed. Unchanged bundle hashes reuse snapshots and check results. Discovery uses deterministic lexical matches, weighted toward title, problem and positive suitability. Matching terms are reasons to inspect, not proof of fit. Synonyms may be missed. Negative-condition matches are warnings to read those conditions. No match returns no offer; rephrase the task. Default limit is 5, maximum 20; the candidate list is also capped at 12000 serialized UTF-8 bytes. `omitted` says how many matches did not fit. Increase the limit where helpful or make the task more specific. Discovery is deliberately lossy.

Use the full content ID from an offer to read its context:

```
python "CLONE/knowhow.py" select FULL_CONTENT_ID --project "PROJECT"
```

Selection returns full PATTERN text, the full structured context, check/review state, decision reasons, source locations and a resolvable local bundle path containing the kit. Inspect relevant kit files there. Evidence references are not fetched or independently verified. Read circumstances, prerequisites, negative evidence, limits, adaptations and drift before deciding what to apply. Selection logs an inspection; it does not assert successful reuse. Restrictions are checked again at selection, so an old offer can become unavailable.

Only admitted material is offered to other projects. Your own supplied material can appear as `own-unadmitted`, with missing-context diagnostics. Copies are one content identity with several locations, not several independent successes. Changed bytes become a new identity with no inherited admission. Source removal never deletes retained versions. A retained location may be historical (`current: 0`). Similar contributions remain separate until the owner decides otherwise.

Before adding a contribution to your own `innovations/`, read [the standard](standard/STANDARD.md) and start from [its template](standard/PATTERN.template.md). Check your addition:

```
python "CLONE/knowhow.py" check "PROJECT/innovations/my-technique"
```

The response shows missing, invalid or unknown items and what to supply, then required human review; it emits no successful field checks. Complete recorded presence proves neither truth nor admission. Exit status is 0 for complete presence, 1 for incomplete/invalid material and 2 for usage/read failure. The check neither gathers other projects nor requires projects-folder configuration. `--json` returns the same compact diagnostic content in machine-readable form.

Your project's executive can decline a contribution for this project:

```
python "CLONE/knowhow.py" decline FULL_CONTENT_ID --project "PROJECT" --actor "project executive" --reason "Why it does not fit"
```

A decline suppresses offers and selection for that project without deleting anything. Append `--undo` with a reason to reverse it. This command records attribution; it does not authenticate a role.

After actual use, record the result and optional estimate of resources saved:

```
python "CLONE/knowhow.py" log-use FULL_CONTENT_ID --project "PROJECT" --outcome "What happened, including failures" --saving-note "Estimated time or attention saved, and basis"
```

Output bytes, elapsed time and gathering counts are logged automatically; savings are caller-reported estimates. Bytes are not model tokens. Inspection alone is not evidence of savings. Add `--json` to any command for a structured response. `self-check` reports the interpreter, platform, local storage and an isolated synthetic gather/check/selection exercise on the current machine.

Owner decisions are documented separately in [OWNER.md](OWNER.md).

State lives only in this clone's git-ignored `.local/`: settings, content snapshots, decision history and use/cost records. A fresh clone starts empty and works without another project or this clone's original parent. Configure its projects folder to gather what exists on that machine. Cloning does not restore personal state or decisions: separately preserve `.local/` if those histories are needed. Do not force-add it to version control. Symlinks/reparse points, repository metadata, standard dependency environments and secret entries are skipped; unreadable or omitted bundle material is diagnosed and prevents admission. Only safely readable material can be retained. Hashing buffers one bundle at a time in memory.
