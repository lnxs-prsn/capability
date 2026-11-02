"""The authoritative definition: documentation and validation consume these data."""
SCHEMA_VERSION = 1
STANDARD_VERSION = "1.0"
NOTICE = "This check establishes recorded presence, not truth, fitness or admission."


def text(description):
    return {"type": "text", "description": description}


def choice(values, description):
    return {"type": "text", "choices": values, "description": description}


def obj(fields, description):
    return {"type": "object", "fields": fields, "description": description}


def listing(item, description, minimum=0):
    return {"type": "list", "item": item, "minimum": minimum, "description": description}


def date(description):
    return {"type": "date", "description": description}


SECTIONS = (
    ("What it is", "Explain the technique and its intended effect."),
    ("Problem it solves", "Describe the difficulty that makes the technique useful."),
    ("How to use it", "Give actionable steps and the expected result."),
    ("Fits projects like", "Explain how a receiver should judge applicability."),
    ("Proven in", "Explain real use, including failures and the basis for the claims."),
    ("Kit (deployable files in `kit/`)", "Explain the supplied assets and their connection to the advice."),
)
CONTEXT_HEADING = "Context record"
CONTEXT_FENCE = "```json"

RECORD = obj({
    "schema_version": {"type": "integer", "constant": SCHEMA_VERSION,
                       "description": "Record format version."},
    "standard_version": {"type": "text", "constant": STANDARD_VERSION,
                         "description": "Standard used for this contribution."},
    "id": {"type": "id", "description": "Lowercase kebab identifier matching the contribution directory."},
    "origin": obj({
        "project": text("Identify the developing project, separately from supplying copies."),
        "situation": text("Describe the circumstances that led to the technique."),
        "environment": text("Record relevant operating conditions."),
        "developed_on": date("Date of development; null explicitly records an unknown date."),
        "development_kind": choice(["invented", "materially_refined"], "Real project development, not merely imported advice."),
        "development_account": text("Explain the development and any uncertainty, including an unknown development date."),
    }, "Where and why the contribution developed."),
    "applicability": obj({
        "fits": listing(text("A positive fit condition."), "Conditions under which reuse makes sense.", 1),
        "does_not_fit": listing(text("A negative fit condition."), "Technical exclusions; empty means none identified, not universal fitness."),
        "prerequisites": listing(text("A required condition or dependency."), "Conditions needed before use; empty means none identified."),
        "adaptations": listing(text("A required adaptation."), "Changes the receiver must make; empty means none identified."),
    }, "Structured suitability conditions, available before selection."),
    "evidence": listing(obj({
        "claim": text("The specific assertion supported by this account."),
        "outcome": choice(["success", "failure", "mixed"], "Reported outcome of real use."),
        "project": text("Project where the reported use occurred, not the copy's host."),
        "situation": text("Circumstances and scope of that use."),
        "occurred_on": date("Date of use, separately from verification."),
        "locators": listing(text("Evidence locator, for example a file and revision or incident identifier."), "Citable supporting facts; this check does not fetch or verify them.", 1),
        "verification": obj({
            "status": choice(["unchecked", "checked", "unavailable"], "Contributor-reported verification status, never inferred from presence."),
            "checked_on": date("Verification date; null when no verification occurred."),
            "checked_by": text("Who performed the reported verification; null if not checked."),
            "scope": text("What was verified; null if not checked."),
            "result": text("What verification established; null if not checked."),
            "reason": text("Explain unavailable evidence or lack of checking; null after a reported check."),
        }, "Keep claims distinct from verification and access."),
    }, "An account of observed use."), "Retain positive and negative evidence. At least one successful real-use account is required.", 1),
    "limits": listing(text("A known limit, failure condition or unresolved uncertainty."), "Residual limits; empty means none identified and requires review."),
    "evolution": obj({
        "origin_state": choice(["aligned", "diverged", "unknown"], "Relationship to current originating practice."),
        "assessed_on": date("Date alignment was assessed; null if unknown."),
        "locators": listing(text("Source-state locator."), "Basis for the alignment account."),
        "deltas": listing(text("A difference from current originating practice."), "Known differences; required when diverged."),
        "reason": text("Explain alignment, divergence or unresolved knowledge."),
    }, "Make drift visible rather than silently claiming freshness."),
    "assets": listing(obj({
        "path": {"type": "asset_path", "description": "Portable relative path below kit/; identifies a supplied deployable file."},
        "kind": text("Asset type, such as template, script or checklist."),
        "purpose": text("What this asset supplies."),
        "adaptations": listing(text("A required edit."), "How to adapt this asset; empty means none identified."),
        "dependencies": listing(text("A dependency."), "What this asset needs; empty means none identified."),
        "context_ref": {"type": "context_ref", "description": "PATTERN.md#<section-slug> or PATTERN.md#/field/path, resolving to this explanation or record."},
    }, "Deployable material linked back to context."), "At least one supplied deployable file; list every kit file.", 1),
}, "Full contribution context. All named keys are required; unknown values use null and remain visibly incomplete.")

# Conditional paths use [] to range over evidence accounts.
CONDITIONS = (
    {"path": "evidence[]", "when": ["verification.status", "checked"],
     "require": ["verification.checked_on", "verification.checked_by", "verification.scope", "verification.result"],
     "nullable": ["verification.reason"]},
    {"path": "evidence[]", "when": ["verification.status", "unchecked"],
     "require": ["verification.reason"],
     "nullable": ["verification.checked_on", "verification.checked_by", "verification.scope", "verification.result"]},
    {"path": "evidence[]", "when": ["verification.status", "unavailable"],
     "require": ["verification.reason"],
     "nullable": ["verification.checked_on", "verification.checked_by", "verification.scope", "verification.result"]},
    {"path": "evolution", "when": ["origin_state", "diverged"], "require": ["deltas", "locators", "assessed_on"], "nullable": []},
    {"path": "evolution", "when": ["origin_state", "aligned"], "require": ["locators", "assessed_on"], "nullable": []},
)
PREDICATES = (
    {"kind": "some", "path": "evidence", "field": "outcome", "equals": "success",
     "message": "Supply at least one dated, citable account of successful real use."},
)
REVIEW_ITEMS = (
    ("real_use", "Confirm real invention or material refinement and successful use; inspect dated supporting facts, failures and verification scope."),
    ("generic_kit", "Inspect each kit for project-specific identifiers; replace them with placeholders except in clearly marked origin evidence notes."),
    ("index", "Confirm a matching row in the parent index and no unmatched rows or directories; record useful compositions there."),
    ("layout", "Review the parent collection layout: its ordinary root files are its index, contribution instructions and optional checker; contributions use one directory each."),
    ("procedure", "Contributing project: verify evidence and generic assets before indexing; use one documentation-area commit according to its contribution procedure."),
    ("synchronization", "When originating advice changes, update the explanation and assets in the same work sitting or record the differences in the evidence section and evolution account."),
    ("counter_evidence", "Preserve adverse evidence in the evidence section; withdrawal retains the account and reason under the collection's retirement procedure. Admission and retirement are separate decisions."),
    ("consistency", "Review agreement between structured context, explanation and assets, including explicitly empty lists and unknowns. Never select solely from discovery text."),
)
DISCOVERY_LIMITS = {"title": 96, "summary": 180, "problem": 120,
                    "fits": 2, "does_not_fit": 2, "condition_chars": 96}
