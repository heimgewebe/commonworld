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
commonworld.pages-live.canonical-shell.v2
```

The delivery smoke is read-only. It verifies that the canonical Commonworld shell is served and rejects parking, login, backend and removed-development content.

## Change boundary

This document does not authorize DNS mutation. Any future DNS or Pages change must preserve the canonical domain, HTTPS delivery and the one public Commonworld surface.

## Bounded production authorization

GitHub Pages is authorized as the production delivery path for the current static, account-free Commonworld catalog. The authorization excludes backends, accounts, sensitive transactions and any claimed service-level agreement.

Operational limits from the official GitHub Pages contract remain visible: the published site must stay within 1 GiB, deployments must finish within 10 minutes, the 100 GiB monthly bandwidth value is a soft limit, and rate limiting can occur. Approaching any of these boundaries reopens the delivery decision.

The basemap is a separate noncritical dependency. `tiles.openfreemap.org` is authorized only as best effort without an SLA or continuity guarantee. If it is unavailable, the complete linear catalog, project selection and focus content must remain usable and the map must report a degraded state.

The machine-readable decision and its failure/rollback boundary are in `contracts/commonworld/production-delivery-provider.contract.json`. Provider migration, self-hosting, backend introduction or automatic failover require a separate reviewed task.
