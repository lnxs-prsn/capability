# Capability owner decisions

This command supplies mechanisms, not authority. The capability's owner assigns decision rights. The admitting executive reviews evidence and full context and decides admission, merge and retirement. The CEO decides exclusions. Project executives decide only their own project's declines (see USE.md). Actor strings are attribution, not authentication; anyone with local filesystem access can edit state.

Use Python 3.9+ and the explicit clone path to `knowhow.py`. These examples use `CLONE` for that path and `ID` for a full immutable content hash. No command changes project files. Every decision requires `--actor` and a nonempty `--reason`; events remain in the namespace's catalog and are never erased by reversal.

```
python "CLONE/knowhow.py" admit ID --actor "admitting executive" --reason "Evidence reviewed and why it fits the admission standard"
python "CLONE/knowhow.py" merge OLD_ID --into SURVIVING_ID --actor "admitting executive" --reason "Evidence of equivalence and why this version survives"
python "CLONE/knowhow.py" retire ID --actor "admitting executive" --reason "Why withdrawn, with adverse evidence"
python "CLONE/knowhow.py" exclude ID --all --actor "CEO" --reason "Why unavailable everywhere"
python "CLONE/knowhow.py" exclude ID --project "PROJECT" --actor "CEO" --reason "Why unavailable to this project"
python "CLONE/knowhow.py" decisions ID
```

Admission requires complete recorded presence and a safe complete snapshot, followed by the executive's semantic review. Passing the check is never automatic admission. A changed contribution needs a new admission. To collect IDs initially, ask from a supplying project with a task describing its contribution; its unadmitted material remains visible there with diagnostics.

Merge is an explicit relationship, not text synthesis: all source bundles and reasons survive, sources stop being offered, and the separately admitted target remains. A merge target must be admitted, available and not itself merged. To keep relationships clear, a source already serving as a merge target cannot be merged onward until its incoming merges are undone. Restrictions on any merged source also suppress its target, preventing a merge from bypassing a decline or exclusion. Merging does not independently approve any evidence from the inputs.

Append `--undo` to admit, merge, retire or exclude (and a new reason/actor) to record a reversal. Merge reversal still accepts `--into` to describe the relationship being reversed. Undoing admission withdraws cross-project access; undoing retirement does not invent admission. Reversing an exclusion is scoped to the exact `--all` or `--project` scope supplied. Global and project restrictions act independently. Retirement prevents offers even to suppliers; all retained material and decisions remain on disk. `decisions` without an ID lists all events.

The local catalog is SQLite at `.local/namespaces/<root-hash>/catalog.sqlite`; immutable bundle directories are beside it. Tables `events` and `uses` retain decision and cost/use records. Each event includes actor, reason, timestamp, subject, target and scope. Ask/select output bytes are exact UTF-8 response bytes, including the final newline, and elapsed time includes refresh and rendering before logging/output. The `uses.details` JSON holds those measurements; `log-use` adds the caller's outcome/savings account. Configuration also has a cost record; checks and self-checks use `.local/command-uses.jsonl` without needing configuration. Help/usage failures are not use records.

Changing the absolute configured projects root selects a new namespace; there is no relocation or decision migration. Project names/paths inside each namespace stay local. SQLite owns authoritative events as well as derived check/discovery data: do not delete a catalog expecting to recover decisions from source projects. Preserve all of `.local/` separately if personal history matters. It is ignored by git. No automatic deletion or network synchronization occurs.
