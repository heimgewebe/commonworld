# Commonworld production delivery and basemap provider decision v1

## Decision

The current public architecture is authorized for bounded production use:

- `commonworld.net` remains a static GitHub Pages site built from `main` and `/`;
- the public OpenFreeMap instance remains the basemap source;
- OpenFreeMap is a noncritical best-effort dependency without a claimed SLA, warranty, continuity guarantee or personalized support;
- no backend, account system, sensitive transaction, automatic provider failover or provider migration is authorized.

The map is an enhancement to discovery, not the only path to the catalog. If map resources fail, the complete linear catalog, project selection and focus information must remain usable and the interface must state that the map is degraded.

## Why this is the proportionate choice

The present Commonworld release is a small static catalog. GitHub Pages provides the required HTTPS and custom-domain delivery without introducing a server. OpenFreeMap supplies keyless public tiles with low operational burden. Self-hosting now would add storage, update pipelines, bandwidth, monitoring and incident responsibility before traffic or availability requirements justify them.

This decision does not treat free service as guaranteed service. It makes the lack of an SLA visible and keeps the provider outside the critical information path.

## Current-state readback

- public URL: `https://commonworld.net/`;
- delivery: GitHub Pages, `main` / `/`, custom domain through `CNAME`;
- renderer assets: local and lockfile-bound;
- basemap runtime origin: `https://tiles.openfreemap.org`;
- style, sprites, glyphs, raster and vector resources use that origin;
- attribution: OpenFreeMap, OpenMapTiles and OpenStreetMap;
- CSP permits the basemap origin only for the required map resources;
- no Commonworld telemetry, proxy, backend, account or API key is used.

## Compared options

| Option | SLA | Privacy/control | Cost | Operations | Decision |
| --- | --- | --- | --- | --- | --- |
| OpenFreeMap public instance | None | No accounts/cookies; bounded incident logging and Cloudflare processing can occur | No usage fee claimed | Low | Selected as noncritical best effort |
| OpenFreeMap self-hosted | Operator-owned | Highest direct control | Infrastructure and bandwidth | High: imports, storage, updates, monitoring | Revisit only when control is needed |
| MapTiler Custom cloud | 99.9% on the cited Custom plan | Requires contract and data-processing review | Paid contract | Medium | Procurement option if an SLA becomes necessary |
| Protomaps/PMTiles on owned storage/CDN | Operator/CDN-owned | High, dependent on CDN | Storage, CDN and pipeline | Medium to high | Revisit for static controlled tile delivery |

## Failure and rollback

- **OpenFreeMap outage or rate limit:** show a degraded-map state; preserve the linear catalog, selection and focus; avoid retry storms.
- **Stale or unknown tiles:** do not claim freshness that Commonworld has not measured.
- **GitHub Pages failure:** inspect the Pages deployment and service status. If a release caused the failure, return to the previous known-good commit.
- **DNS failure:** compare authoritative and recursive DNS with `docs/ops/pages-dns.md` before any mutation.
- **Provider migration:** create a separate reviewed implementation task. This decision alone changes no tile delivery.

## Revisit conditions

Reopen the decision when traffic approaches GitHub Pages' published soft limits, the site approaches 1 GiB, a contractual uptime target or data-processing agreement becomes necessary, repeated map outages materially impair discovery, provider terms change, tile freshness becomes product-critical, or Commonworld introduces backend/account responsibilities.

## Official sources checked on 2026-07-13

- GitHub Pages limits: `https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits`
- OpenFreeMap service description: `https://openfreemap.org/`
- OpenFreeMap privacy: `https://openfreemap.org/privacy/`
- OpenFreeMap terms: `https://openfreemap.org/terms/`
- OpenFreeMap self-hosting quick start: `https://openfreemap.org/quick_start/`
- MapTiler pricing and SLA boundary: `https://www.maptiler.com/cloud/pricing/`
- Protomaps PMTiles documentation: `https://docs.protomaps.com/pmtiles/`

## Boundary

This record authorizes a deliberately limited production responsibility. It does not claim a provider SLA, automatic failover, backend readiness, self-hosted tile competence or capacity for future unmeasured traffic.
