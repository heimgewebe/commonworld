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

## HTML cache coherence boundary

The live GitHub Pages delivery was re-read on 2026-07-28. Canonical HTML and catalog responses exposed `Cache-Control: max-age=600`. Different query strings reused the same shared Varnish cache entry: they returned the same ETag with increasing `Age` and changed from `MISS` to `HIT`. Commonworld therefore does not claim that `?v=`, `cw_probe` or `cw_release` values bypass the provider cache. Query tags remain only content diagnostics inside one immutable release path.

Every public build now creates exactly one content-derived snapshot under `/releases/<release-id>/`. The rendered pages contain a release-bound `<base>` element, so relative scripts, styles, catalog files, contracts and navigation remain inside that coherent snapshot. Interactive entry pages check freshness through a unique unknown path under `/__cw_probe/<nonce>/manifest`. A first request to each distinct path was observed as a separate CDN `MISS`; GitHub Pages serves the current custom `404.html`, which contains the strict release manifest. A stale interactive page replaces itself with the matching release-snapshot path and then presents the canonical URL through `history.replaceState`.

The probe is limited to three seconds. A late response cannot trigger navigation. Before a necessary proposal-page navigation, a dirty form is stored once in that tab's `sessionStorage`; the next page load deletes the draft immediately and restores it only when schema, locale and the five-minute age bound match. No server receives the draft.

Two limits remain explicit:

- HTML cached before the first deployment of this path-probe checker cannot execute code it does not yet contain; one manual reload or expiry of the observed provider TTL is required once.
- `method.html` and `method.de.html` remain script-free. Navigation from an interactive current release resolves to the release-bound method copy, but a direct canonical method URL can remain stale for the provider TTL.

True zero-staleness for every direct URL would require delivery where Commonworld controls HTML response headers, for example `no-cache, must-revalidate` for documents and immutable caching for content-addressed release assets. That migration is not authorized by this record.

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
