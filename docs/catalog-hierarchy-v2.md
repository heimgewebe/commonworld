# Guarded catalogue hierarchy v2

## Purpose

The v2 catalogue runtime keeps static delivery while removing the flat-directory scaling limit. It is a migration candidate, not a production cutover.

## Request path

The active default remains `catalog/runtime/manifest.v1.json` with two-hex shards. The candidate loads `manifest.v2.json` plus `aggregate.v2.json`, then only the selected aggregate segment, followed by one one-hex shard index and one three-hex leaf shard. Details remain content-addressed v1 documents.

Descriptors bind URL, byte length and SHA-256. URLs remain same-origin and inside the document root. Corrupt bytes fail closed.

## Budgets and rollback

The 1,000, 10,000 and 100,000-entry fixtures cap every root, index, segment and leaf at 32,768 gzip bytes. Chromium evidence proves bounded request topology and corruption rejection. `cutover_authorized` remains `false`; rollback is `catalog/runtime/manifest.v1.json`. Physical iPad and mobile-network acceptance remains required for any later cutover decision.
