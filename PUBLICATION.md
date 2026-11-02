# Publication formats, version 1

All JSON uses UTF-8; emitted JSON has sorted keys, ASCII escapes and compact separators, followed by LF. Hashes are lowercase SHA-256. Inventories use forward-slash relative portable paths, no traversal, absolute paths, links/reparse points, secret names, special files or case collisions. Duplicate JSON keys are rejected. No evidence references are fetched. Hashes establish integrity relative to the supplied index, not trusted identity or actor authority.

## Project index and input list

`published/INDEX.md` preserves other prose, adding exactly one block:

````markdown
<!-- knowhow:v1 -->
```json
{"format":1,"project_id":"00000000-0000-4000-8000-000000000001","offers":[]}
```
<!-- /knowhow:v1 -->
````

An offer reference is `{"path":"knowhow/offers/<hash>/OFFER.json","sha256":"<hash>"}`. Optional `catalogue` is one current reference with the same path/hash shape, naming `knowhow/catalogues/<edition>/EDITION.json`. All reference paths are relative to the public index's directory. The index can change; the editions it names stay fixed. The project UUID is created locally at initialization and preserved through moves/reassignment; it is not a proof of ownership.

Curator input is `{"format":1,"published_parts":["directory-locator"]}`. Directory locators resolve relative to the list file or may be absolute. This list is an input, not a projects-folder setting; only the explicitly listed public indexes are read. Missing input does nothing. An empty list is valid.

## Offers and manifests

An offer directory contains `OFFER.json` and `bundle/<slug>/PATTERN.md`, `bundle/<slug>/kit/...`. The contribution remains standard 1.0, with its full structured context inside PATTERN. A manifest object has `format:1`, `kind` (`offer`, `catalogue`, `capability`), `metadata`, and `files`, a path-keyed object of `{"sha256":"<hash>","size":123}`. Its own name is excluded from `files`. The index carries SHA-256 of the exact manifest bytes; the directory's name alone never proves identity.

Offer metadata contains `content_id`, `name` (contribution slug) and `standard_version`. Content identity is SHA-256 of sorted contribution-relative file names and exact bytes: for each UTF-8 path and then each body, feed its unsigned 8-byte big-endian length followed by its bytes. Supplier UUID, publication path and timestamps are excluded. Changed bytes are new content; changed envelope metadata is a new offer. Supplying origins are recorded separately, preserving the original project and evidence accounts inside PATTERN.

Offering preflights the working bundle before reading/checking, checks the source, stages the captured bytes and checks that copy before installing. Intake verifies manifest inventory, exact offer file set, every size/hash and recomputed content ID; then checks the retained copy. Existing editions are verified rather than overwritten. Content is never silently repaired under its old identity.

## Catalogue

Catalogue `EDITION.json` metadata contains `edition` and `curator_id`. Files include `CATALOGUE.json`, `contents/<content-id>/bundle/<slug>/...` and `contents/<content-id>/CHECK.json`. The catalogue JSON contains `format:1`, `items` and ordered `events`. Each item holds ID, name, bounded discovery, bundle prefix, check path and supplying origins. Events retain sequence, timestamp, operation, subject ID, scope (`*` or project UUID), actor, reason, merge target and reversal flag. Sources and past decisions are retained; they are not independent evidence of success.

Ask verifies the manifest and catalogue JSON, then uses discovery and effective policy without reading full bundles. Select rereads the current index through a new invocation, verifies selected bundle files and recomputes content identity, returning full context/checks and a kit locator inside the catalogue. The manifest inventory itself grows with the catalogue; the candidate list, not total disk reads or manifest size, has the 12000-byte bound. A current index is required even for an old content ID; no offline fallback can establish current exclusions.

## Local records and capability editions

Each project's `.knowhow/project.json` holds its UUID. JSONL records hold local declines/reversals, use reports, measured costs and catalogue hashes/locators. Curator SQLite holds content metadata, supplying origins, known UUIDs, decisions and its own costs; retained offers sit beside it. These local formats are private state, not communication channels. Publish selected learning as a complete offer to share it; the curator never reads taker journals.

Capability editions keep their source-relative layout with `EDITION.json` kind `capability`, edition identifier, Python floor and explicit file inventory. Pack uses an explicit allowlist, no recursive repository capture. The external index must carry its manifest hash. Preserve edition identity when relocating; a locator change requires verification of the same bytes, while adopting new content is an explicit new edition. Fixed editions run without writing themselves; personal state belongs in the invoking project.
