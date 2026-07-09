# Commonworld Pages DNS Fix

Status: prepared
Live DNS mutation: not performed by this document
Domain: `commonworld.net`
Repository: `heimgewebe/commonworld`
Pages source: `main` / `/`
Custom domain file: `CNAME` contains `commonworld.net`

## Why this exists

The repository is built by GitHub Pages, but the public domain currently does not
serve the Commonworld proof hub. The live smoke added in T029 detects the drift:

- `https://commonworld.net/` fails with connection refused.
- `https://heimgewebe.github.io/commonworld/` redirects to `http://commonworld.net/`.
- `http://commonworld.net/` serves an INWX parking page, not the committed proof hub.

Current public DNS points both apex and `www` to the INWX parking target:

```text
commonworld.net A        185.181.104.242
www.commonworld.net A    185.181.104.242
```

## Target DNS records

Use the INWX zone for `commonworld.net`.

### Delete

| Name | Type | Value |
|---|---|---|
| `@` | `A` | `185.181.104.242` |
| `www` | `A` | `185.181.104.242` |

### Create apex records

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

### Create `www` record

| Name | Type | Value | TTL |
|---|---|---|---:|
| `www` | `CNAME` | `heimgewebe.github.io.` | `3600` |

## Do not create

- No wildcard record such as `*.commonworld.net`.
- No `A` record for `www` after the CNAME exists.
- No registrar redirect, URL forwarding, parking target, frame redirect, or INWX webspace target.
- No mail records as part of this Pages-only fix.
- No repository deploy, no GitHub Pages source change, no CNAME change unless GitHub explicitly rejects the current value.

## Why these values

GitHub Pages documents these apex `A` and `AAAA` values for custom domains and
says `www` should be a CNAME to the user or organization Pages domain, excluding
the repository name:

- https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site

For this repository owner, the organization Pages domain is:

```text
heimgewebe.github.io
```

## Verification

After applying the INWX zone change, run:

```bash
make check-pages-dns-target
```

Expected outcome:

```text
commonworld Pages DNS target validation ok
```

Then run the delivery smoke:

```bash
make smoke-pages-live
```

Expected outcome: JSON receipt with `commonworld.pages-live.delivery-smoke.v1`.

## HTTPS enforcement follow-up

GitHub Pages currently reports `https_enforced: false`. Do not force this until
DNS resolves to GitHub Pages and GitHub has issued the certificate. GitHub notes
that DNS propagation and HTTPS availability can take up to 24 hours.

After DNS is correct and Pages reports HTTPS as available, enable HTTPS in GitHub
Pages settings or via an audited GitHub API call.
