Before drawing on shared know-how or offering yours, read INDEX.md at the listed location, or USE.md in a clone.

At a publisher's location, read its INDEX.md for the current fixed capability edition, its manifest hash and USE.md, and its current catalogue. Resolve paths from that index's directory; verify the capability manifest and listed files before use. Give the index to ask/select as INDEX. Fixed editions cannot name future editions or catalogues.

With only a clone, read this USE.md and use the clone directly wherever the examples say EDITION. You can initialize your own project, check and offer without a catalogue. Without a curator's published index naming a catalogue, there is nothing yet to ask or select; obtain that index through your arrangement when available. To curate for yourself, follow [OWNER.md](OWNER.md).

If your executive is considering know-how your project already holds, read [Existing know-how](EXISTING.md); otherwise continue below.

Use Python 3.9+ and an explicit path to the chosen edition's or clone's `knowhow.py`. Replace `EDITION`, `PROJECT`, `INDEX` and `ID` in the examples; quote paths containing spaces. `PROJECT` is your own project's existing root, `INDEX` is the curator's published `INDEX.md`, and `ID` is a full content SHA-256 from a candidate. No network, dependencies beyond Python's standard library, background work or kit execution. Add `--json` for structured output.

1. Initialize your own project once:

   ```
   python "EDITION/knowhow.py" init --project "PROJECT"
   ```

   This creates `.knowhow/project.json` with a stable random project UUID and adds a machine-readable identity/offer block to your `published/INDEX.md`. Existing prose and method declarations remain. Keep the UUID when moving or reassigning the project. A deliberate fork initializes a new UUID before publishing; a missing local identity with an existing public declaration must be restored, not regenerated. Project identity is independent of its name, folder and organization.

2. Ask for a compact screening list relevant to your task:

   ```
   python "EDITION/knowhow.py" ask --project "PROJECT" --catalogue "INDEX" --task "repeatable setup" --limit 5
   ```

   Only admitted, eligible content is offered. An empty catalogue returns no candidates. Matching is deterministic and lexical; synonyms can be missed. Matching words are reasons to inspect, not proof of fit. Positive conditions, negative-condition matches, limits and unknowns support screening. The discovery projection truncates conditions. Default five candidates, maximum twenty, and at most 12000 UTF-8 bytes for the candidate list; `omitted` counts matches that did not fit. Rephrase when no useful match appears.

3. Select only relevant candidates to load full context:

   ```
   python "EDITION/knowhow.py" select ID --project "PROJECT" --catalogue "INDEX"
   ```

   Read the full PATTERN and structured record, prerequisites, adaptations, adverse evidence, verification scope, limits and evolution account. Inspect the kit in the returned `bundle` path. Evidence locators are never fetched or independently verified. Selection verifies the selected bytes and records inspection; it claims no successful reuse. Nothing is copied into your working files automatically. Exact copies have one content identity and several supplying origins; copies are not independent successes.

4. Your project's executive may decline content for this project:

   ```
   python "EDITION/knowhow.py" decline ID --project "PROJECT" --actor "project executive" --reason "Why it does not fit"
   ```

   Append `--undo` and a new reason to reverse. A decline suppresses both screening and selection, including a merged successor. Other projects' records are unaffected; nothing is deleted. Actor strings record attribution and do not authenticate authority.

5. After actual use, record its outcome and estimated saving:

   ```
   python "EDITION/knowhow.py" log-use ID --project "PROJECT" --outcome "Observed result, including failures" --saving-note "Estimated saving and its basis"
   ```

   Outcomes and savings are caller reports. Command output bytes and elapsed time are measured separately; bytes are not model tokens. An inspection alone establishes no savings.

6. Before offering your own addition, read [the standard](standard/STANDARD.md), start with [its template](standard/PATTERN.template.md), complete your contribution in your own working collection, then check:

   ```
   python "EDITION/knowhow.py" check "PROJECT/innovations/my-technique" --project "PROJECT"
   ```

   This checks your supplied addition only. It reports missing, invalid and unknown items and required human review; complete presence proves neither truth nor admission. The standard's parent-index, layout and contribution-procedure duties apply to your working collection. Verify evidence and generic assets before offering. The collection's private index need not be published. Exit codes: 0 complete, 1 incomplete/invalid, 2 usage/read failure. For a check with no initialization, records or writes, use `python "EDITION/check_contribution.py" "PROJECT/innovations/my-technique" --json`.

7. Publish your checked addition deliberately:

   ```
   python "EDITION/knowhow.py" offer "PROJECT/innovations/my-technique" --project "PROJECT"
   ```

   This checks before offering, freezes PATTERN (including its context) and the whole kit into `published/knowhow/offers/<manifest-hash>/`, and adds its relative path/hash to your public index. Nothing is read from other projects. All kit files must be declared. Keep the working bundle separate; a change produces a new content identity requiring a fresh admission. Offers already published stay fixed. Repeating an unchanged offer is idempotent. Share your published part through your organization's arrangement; the capability never searches for projects. Offering does not automatically admit content.

Each agent writes only in its own project. All commands require an explicit `--project`; this is the caller's ownership assertion, not an authentication boundary. The code rejects links/reparse points, traversal, prohibited names and special files. Never point a writable project at an executable edition. Running from a fixed edition creates no state or bytecode there. Local state is `.knowhow/`: UUID, declines, inspections/costs, actual-use accounts and catalogue identity/locator history. Preserve it with your project. The code's clone needs none of those personal records to work empty.

Every ask and select resolves the current catalogue through the supplied public index and rechecks its published policy. An earlier ID does not bypass a later published exclusion. Invalid or unavailable current policy fails closed. Curator decisions reach takers when published; a disconnected copy cannot learn of later exclusions, and already published bytes remain directly readable. Local declines take effect immediately for this project's commands.

A catalogue's manifest hash is its identity, separately recorded in your history. When its project moves, explicitly supply the new published index and verify the previously recorded edition hash before accepting the locator change; do not guess from a directory name. A new current edition has a new verified hash and is recorded as such. Keep the capability edition identity and external manifest hash supplied by its publisher too; verify its `EDITION.json` and listed files after movement before using it. Capability updates never mutate the edition you took.

Run `python "EDITION/knowhow.py" self-check --project "PROJECT" --json` for a temporary invented offer-to-selection exercise on this machine. It records its cost in your project and removes its synthetic projects. It proves no real savings or operation on another OS. See [publication formats](PUBLICATION.md) for portable records.
