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
