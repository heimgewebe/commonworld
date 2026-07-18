# Commonworld Pages DNS Contract

## Status

- Domain: `commonworld.net`
- Repository: `heimgewebe/commonworld`
- Pages source: `main` / `/`
- Custom-domain file: `CNAME` contains `commonworld.net`
- DNS target: GitHub Pages
- Purpose: preserve the public delivery path while Commonworld is rebuilt around the canonical globe plan

## Required DNS records

The authoritative INWX zone must expose the following records.

### Apex

| Name | Type | Value | TTL |
|---|---|---|---:|
| `@` | `A` | `185.199.108.153` | `3600` |
| `@` | `A` | `185.199.109.153` | `3600` |
| `@` | `A` | `185.199.110.153` | `3600` |
| `@` | `A` | `185.199.111.153` | `3600` |
| `@` | `AAAA` | `2606:50c0:8000::153` | `3600` |
| `@` | `AAAA` | `2606:50c0:8001::153` | `3600` |
| `@` | `AAAA` | `2606:50c0:8002::153` | `3600` |
| `@` | `AAAA` | `2606:50c0:8003::153` | `3600` |

### `www`

| Name | Type | Value | TTL |
|---|---|---|---:|
| `www` | `CNAME` | `heimgewebe.github.io.` | `3600` |

## Forbidden zone shapes

- no INWX parking target `185.181.104.242`;
- no direct `A` or `AAAA` record for `www` while the CNAME exists;
- no apex CNAME;
- no wildcard record;
- no registrar forwarding or framed redirect;
- no unrelated mail or service records as part of this Pages contract.

## Verification

Authoritative and recursive DNS:

```bash
make check-pages-dns-target
```

Expected result:

```text
commonworld Pages DNS target validation ok
```

Public delivery after a merged Pages build:

```bash
make smoke-pages-live
```

Expected receipt id:

```text
commonworld.pages-live.globe-first-and-proposal.v7
```

The delivery smoke is read-only. It verifies that the canonical Commonworld shell is served and rejects parking, login, backend and removed-development content.

## Automated exact-commit production readback

Every push to `main` also starts `.github/workflows/production-readback.yml`. The workflow does not treat a green Pages build as sufficient proof. It waits at most 600 seconds for a `github-pages` deployment whose SHA is the exact commit checked out by the workflow. Older successful deployments are ignored.

After that exact deployment reports success, the workflow reuses `scripts/smoke_pages_live.py`. The existing smoke compares the public shell, proposal page, catalog and runtime assets with the checked-out commit. Each automated file request is bounded to five seconds. The existing smoke checks the shell, proposal page, catalog and six runtime assets; the orchestrator additionally binds `index.html`, `propose.html` and `catalog/catalog.json` byte-for-byte to the checked-out commit. CDN propagation is retried only as three complete cycles with the fixed delays `0, 30, 90` seconds. Together with the inner one-retry-per-URL limit, even twelve public files consuming their full request windows remain inside the 20-minute workflow boundary. There is no unbounded retry.

The machine-readable artifact is retained for 30 days under the receipt id:

```text
commonworld.pages-production-readback.v1
```

The JSON receipt records the expected commit, selected deployment id and state, deployment observations, live attempts and the complete nested live-smoke receipt. It is uploaded even when the workflow fails.

A red readback does not authorize DNS mutation, provider migration or automatic recovery. There is no automatic rollback. Operators must distinguish a deployment failure, CDN propagation, DNS failure and a client-network problem before applying the separately reviewed rollback contract.

The same workflow can be started manually with `workflow_dispatch`; it still binds itself to the exact commit selected by GitHub Actions.

## Change boundary

This document does not authorize DNS mutation. Any future DNS or Pages change must preserve the canonical domain, HTTPS delivery and the one public Commonworld surface.

## Bounded production authorization

GitHub Pages is authorized as the production delivery path for the current static, account-free Commonworld catalog. The authorization excludes backends, accounts, sensitive transactions and any claimed service-level agreement.

Operational limits from the official GitHub Pages contract remain visible: the published site must stay within 1 GiB, deployments must finish within 10 minutes, the 100 GiB monthly bandwidth value is a soft limit, and rate limiting can occur. Approaching any of these boundaries reopens the delivery decision.

The basemap is a separate noncritical dependency. `tiles.openfreemap.org` is authorized only as best effort without an SLA or continuity guarantee. If it is unavailable, the complete linear catalog, project selection and focus content must remain usable and the map must report a degraded state.

The machine-readable decision and its failure/rollback boundary are in `contracts/commonworld/production-delivery-provider.contract.json`. Provider migration, self-hosting, backend introduction or automatic failover require a separate reviewed task.
