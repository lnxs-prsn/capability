# Contribution standard 1.0

This check establishes recorded presence, not truth, fitness or admission.

Use Python 3.9 or newer. Run `python /path/to/clone/check_contribution.py /path/to/contribution` from any directory; add `--json` for machine-readable output.

The command reads the supplied bundle without executing kits, following symlinks, fetching evidence or writing into projects. Exit 0 means complete recorded presence, 1 means incomplete or invalid material, and 2 means usage or read failure. Human review remains required after exit 0.

## Bundle and explanation

Use one lowercase kebab directory containing PATTERN.md and a kit directory with at least one ordinary deployable file. Declare every kit file once. Asset paths use forward slashes below kit/, with no absolute paths, traversal, symlinks or Windows-reserved names.

Give PATTERN.md a level-one title and these first six level-two sections in order, each with a nonempty explanation. Additional sections may follow. Finish with one Context record section containing exactly one fenced JSON object. Nulls in the generated skeleton are blanks to complete, never evidence.

- `What it is`: Explain the technique and its intended effect.
- `Problem it solves`: Describe the difficulty that makes the technique useful.
- `How to use it`: Give actionable steps and the expected result.
- `Fits projects like`: Explain how a receiver should judge applicability.
- `Proven in`: Explain real use, including failures and the basis for the claims.
- `Kit (deployable files in `kit/`)`: Explain the supplied assets and their connection to the advice.

## Full context

Full contribution context. All named keys are required; unknown values use null and remain visibly incomplete.

The JSON does not duplicate title, summary, problem, mechanism or instructions. Empty lists mean none identified and require review. Null means unknown and prevents completeness except for verification details explicitly inapplicable to an unchecked or unavailable account.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | integer | Record format version. Value: 1. |
| `standard_version` | text | Standard used for this contribution. Value: 1.0. |
| `id` | id | Lowercase kebab identifier matching the contribution directory. |
| `origin` | object | Where and why the contribution developed. |
| `origin.project` | text | Identify the developing project, separately from supplying copies. |
| `origin.situation` | text | Describe the circumstances that led to the technique. |
| `origin.environment` | text | Record relevant operating conditions. |
| `origin.developed_on` | date | Date of development; null explicitly records an unknown date. |
| `origin.development_kind` | text | Real project development, not merely imported advice. Values: invented, materially_refined. |
| `origin.development_account` | text | Explain the development and any uncertainty, including an unknown development date. |
| `applicability` | object | Structured suitability conditions, available before selection. |
| `applicability.fits` | list | Conditions under which reuse makes sense. Minimum items: 1. |
| `applicability.does_not_fit` | list | Technical exclusions; empty means none identified, not universal fitness. Minimum items: 0. |
| `applicability.prerequisites` | list | Conditions needed before use; empty means none identified. Minimum items: 0. |
| `applicability.adaptations` | list | Changes the receiver must make; empty means none identified. Minimum items: 0. |
| `evidence` | list | Retain positive and negative evidence. At least one successful real-use account is required. Minimum items: 1. |
| `evidence[].claim` | text | The specific assertion supported by this account. |
| `evidence[].outcome` | text | Reported outcome of real use. Values: success, failure, mixed. |
| `evidence[].project` | text | Project where the reported use occurred, not the copy's host. |
| `evidence[].situation` | text | Circumstances and scope of that use. |
| `evidence[].occurred_on` | date | Date of use, separately from verification. |
| `evidence[].locators` | list | Citable supporting facts; this check does not fetch or verify them. Minimum items: 1. |
| `evidence[].verification` | object | Keep claims distinct from verification and access. |
| `evidence[].verification.status` | text | Contributor-reported verification status, never inferred from presence. Values: unchecked, checked, unavailable. |
| `evidence[].verification.checked_on` | date | Verification date; null when no verification occurred. |
| `evidence[].verification.checked_by` | text | Who performed the reported verification; null if not checked. |
| `evidence[].verification.scope` | text | What was verified; null if not checked. |
| `evidence[].verification.result` | text | What verification established; null if not checked. |
| `evidence[].verification.reason` | text | Explain unavailable evidence or lack of checking; null after a reported check. |
| `limits` | list | Residual limits; empty means none identified and requires review. Minimum items: 0. |
| `evolution` | object | Make drift visible rather than silently claiming freshness. |
| `evolution.origin_state` | text | Relationship to current originating practice. Values: aligned, diverged, unknown. |
| `evolution.assessed_on` | date | Date alignment was assessed; null if unknown. |
| `evolution.locators` | list | Basis for the alignment account. Minimum items: 0. |
| `evolution.deltas` | list | Known differences; required when diverged. Minimum items: 0. |
| `evolution.reason` | text | Explain alignment, divergence or unresolved knowledge. |
| `assets` | list | At least one supplied deployable file; list every kit file. Minimum items: 1. |
| `assets[].path` | asset_path | Portable relative path below kit/; identifies a supplied deployable file. |
| `assets[].kind` | text | Asset type, such as template, script or checklist. |
| `assets[].purpose` | text | What this asset supplies. |
| `assets[].adaptations` | list | How to adapt this asset; empty means none identified. Minimum items: 0. |
| `assets[].dependencies` | list | What this asset needs; empty means none identified. Minimum items: 0. |
| `assets[].context_ref` | context_ref | PATTERN.md#<section-slug> or PATTERN.md#/field/path, resolving to this explanation or record. |

## Conditional requirements

- Within `evidence[]`, when `verification.status` is `checked`, supply `verification.checked_on`, `verification.checked_by`, `verification.scope`, `verification.result`. May be null: `verification.reason`.
- Within `evidence[]`, when `verification.status` is `unchecked`, supply `verification.reason`. May be null: `verification.checked_on`, `verification.checked_by`, `verification.scope`, `verification.result`.
- Within `evidence[]`, when `verification.status` is `unavailable`, supply `verification.reason`. May be null: `verification.checked_on`, `verification.checked_by`, `verification.scope`, `verification.result`.
- Within `evolution`, when `origin_state` is `diverged`, supply `deltas`, `locators`, `assessed_on`. 
- Within `evolution`, when `origin_state` is `aligned`, supply `locators`, `assessed_on`. 
- Supply at least one dated, citable account of successful real use.

## Discovery and integration

`standard.check_contribution(path)` returns standard_version, record, discovery, checks, presence_complete, review_required, limitations and read_error. Checks contain rule_id, field, state (present/missing/invalid/unknown) and a message. Malformed JSON leaves record and discovery null. Missing fields and unknown values are never invented.

`standard.discovery_record(record, pattern_text)` derives a screening projection from full context and the single authored explanation: title from its level-one heading, summary from the first required section and problem from the second. The checker adds presence_complete and has_unknowns. Retain the full record and bundle; discovery is lossy and cannot establish selection. Its context_ref is relative to the contribution. Store code owns hashes, supplying locations, admission state and comparisons.

Discovery bounds: `{"condition_chars": 96, "does_not_fit": 2, "fits": 2, "problem": 120, "summary": 180, "title": 96}`. Identifier and version strings are capped at 64 characters; asset kinds at four values of 32 characters. Fit conditions are truncated; limits and unknowns are flags. Serialized byte size also depends on character escaping.

## Review obligations

- **real_use**: Confirm real invention or material refinement and successful use; inspect dated supporting facts, failures and verification scope.
- **generic_kit**: Inspect each kit for project-specific identifiers; replace them with placeholders except in clearly marked origin evidence notes.
- **index**: Confirm a matching row in the parent index and no unmatched rows or directories; record useful compositions there.
- **layout**: Review the parent collection layout: its ordinary root files are its index, contribution instructions and optional checker; contributions use one directory each.
- **procedure**: Contributing project: verify evidence and generic assets before indexing; use one documentation-area commit according to its contribution procedure.
- **synchronization**: When originating advice changes, update the explanation and assets in the same work sitting or record the differences in the evidence section and evolution account.
- **counter_evidence**: Preserve adverse evidence in the evidence section; withdrawal retains the account and reason under the collection's retirement procedure. Admission and retirement are separate decisions.
- **consistency**: Review agreement between structured context, explanation and assets, including explicitly empty lists and unknowns. Never select solely from discovery text.

## Maintaining this standard

Edit standard/definition.py, then run `python -m standard.render` from the clone root. The field walker and conditional-rule interpreter consume that definition directly. `python -m standard.render --check` verifies generated artifacts. Tests use invented bundles.
