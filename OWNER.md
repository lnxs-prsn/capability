# Curator decisions and fixed publications

The capability supplies mechanisms, not authority. The admitting executive reviews full context and evidence, then decides admission, merge and retirement with reasons. The CEO decides global or per-project exclusions. A project's executive declines only for that project (USE.md). Actor text is attribution, not authentication; filesystem access can edit records. The capability holds no organization capacity state or pause/stop mechanism.

Use Python 3.9+, standard library only, no network. Replace `CODE` with the capability source or a verified fixed edition, and `CURATOR` with the running curator's own project root. Every command writes only beneath `CURATOR`. Initialize it with `python "CODE/knowhow.py" init --project "CURATOR"`. No curator command searches a projects tree or reads a supplier's private working collection.

## Intake and inspection

Obtain a list of published parts from your organization's arrangement. There is no required service or tooling. Example `parts.json`:

```json
{"format":1,"published_parts":["relative/path/to/project/published"]}
```

Locators resolve relative to that list file; absolute locators are also accepted. Supply actual published roots, never project roots. The reader opens only their `INDEX.md` and explicitly named offers and manifest files. An index without a know-how block advertises no offers and is counted as a nonparticipant; a malformed block is an error. A missing list performs no other work, including no cost write; an explicitly empty list is valid. List failures and invalid offers are reported. Independent valid offers can be retained with a nonzero partial-failure exit status; inspect the summary. Source omissions do not delete retained offers or decisions.

```
python "CODE/knowhow.py" ingest --project "CURATOR" --published-parts "parts.json"
python "CODE/knowhow.py" decisions --project "CURATOR"
python "CODE/knowhow.py" decisions ID --project "CURATOR"
```

`decisions` lists pending content IDs, recorded presence, known project UUIDs and events. `decisions ID` is also full curator inspection: retained PATTERN, check/context, kit path, supplying origins and decision reasons. This serves review without a separate command. Read evidence, counter-evidence and generic assets. Manifest verification establishes integrity, not authenticity or truth. Checks never execute kits or fetch evidence. Complete recorded presence and verified retained bytes are prerequisites for admission, not admission itself.

## Decisions

```
python "CODE/knowhow.py" admit ID --project "CURATOR" --actor "admitting executive" --reason "Evidence and fit reviewed"
python "CODE/knowhow.py" merge OLD_ID --into SURVIVING_ID --project "CURATOR" --actor "admitting executive" --reason "Evidence of equivalence"
python "CODE/knowhow.py" retire ID --project "CURATOR" --actor "admitting executive" --reason "Why withdrawn, including adverse evidence"
python "CODE/knowhow.py" exclude ID --all --project "CURATOR" --actor "CEO" --reason "Why unavailable everywhere"
python "CODE/knowhow.py" exclude ID --project-id PROJECT_UUID --project "CURATOR" --actor "CEO" --reason "Why unavailable to this project"
```

The curator learns a project's UUID from that project's published `INDEX.md`, by ingesting its listed published part. `init` publishes the identity even with no offers. A project that has published nothing cannot be excluded by ID until it does; the curator rejects unknown UUIDs. Do not infer UUIDs from folder names or private records. `--project` always identifies the running curator; `--project-id` identifies an exclusion's target. Moving or reassigning projects retains UUIDs. Correct the supplied locators; simultaneous different published roots claiming one UUID are a conflict, not two projects. A deliberate fork needs a new UUID.

Each decision requires a nonempty actor/reason. Append `--undo` with a new reason to record reversal, including `--into` for merge reversal and the exact scope for exclusion reversal. Global and project exclusions act independently. Reversing retirement does not invent admission; reversing admission withdraws access. A changed content ID inherits no admission.

Merge is a reasoned relationship, not synthesized advice. Both source and separately admitted target stay retained. The source stops being offered; any source restriction also suppresses the target, including takers' local declines. A target cannot itself be merged; a source with incoming merges cannot merge onward until they are undone. No content or adverse evidence is deleted.

## Catalogue publication

```
python "CODE/knowhow.py" publish-catalogue --project "CURATOR" --edition catalogue-001
```

This freezes a self-contained edition at `CURATOR/published/knowhow/catalogues/catalogue-001/` and updates only the know-how block of its `published/INDEX.md`. The edition includes discovery, full bundles/checks/context for admitted history and merge relationships, origins, decision reasons and policy. Unadmitted pending material is retained privately until reviewed, unless needed to preserve a merge relationship. Retired/excluded bytes are retained; eligibility governs the commands. It remains usable when suppliers disappear. A changed edition name must be new; an existing edition is never overwritten with different bytes.

Readers resolve the current catalogue for every ask/select; decisions become effective for takers after publication. Publish a new catalogue after changing decisions. A disconnected old copy cannot learn a new exclusion; the capability cannot stop direct reading of bytes already published. Invalid/unavailable current policy does not fall back to an old catalogue. Publication is a complete staged directory followed by an atomic index replacement; interruption can leave an unindexed complete edition, never a pointer to partial content. Retry unchanged content or inspect that orphan before proceeding.

Retained offers and SQLite history live in `.knowhow/curator/`. Preserve the whole curator project to recover personal decisions and knowledge; deleting the database loses authoritative decisions. SQLite transactions protect decision history; interrupted intake can leave a complete unindexed retained offer which the next identical intake can reuse. No deletion, periodic refresh, synchronization or organization-wide cost aggregation runs. The curator's `costs` table records its own output bytes, elapsed time and intake counts. Takers keep their own costs and use accounts.

## Publish the capability itself

From the developing generic source, after checks:

```
python "SOURCE/knowhow.py" pack-capability --project "SOURCE" --edition capability-001
```

This maintenance command requires the loaded developing capability source itself, rejects fixed editions, and stages only beneath its ignored `.staging/`, with its own measured cost journal beside the stages. It does not initialize a project, publish an edition or write anywhere outside the source. A fixed explicit allowlist includes runtime code, standard/template, checks, guides, tests and UPDATE.md; excludes state, repositories, real offers and personal paths. The output gives the manifest hash. Verify every listed file and report that hash to the publishing executive, who installs the complete fixed stage under its own published part and indexes it with that external hash. Keep the same source-relative layout. Changing any file requires a new fixed edition; deterministic manifest bytes identify the same inputs identically.

`UPDATE.md` explains this edition's changes and taking impact. Keep external capability edition identity beside its locator; after movement verify the same manifest and file hashes before repointing. A clone recovers the generic capability empty and working, with no personal catalogue required. It never restores private decisions or innovations from GitHub. Only the assigned publisher commits/pushes; these commands do neither.

Validation from the source or a disposable copy: `python -B -m unittest discover -s tests -v` and `python -B -m standard.render --check`. Tests use invented publications in temporary directories; `self-check` exercises the current machine. Python 3.9 syntax checks do not prove a run on Python 3.9 or Windows. To update generated standard files, use the developing source's `standard/definition.py` and `python -B -m standard.render`; never edit a fixed edition.
