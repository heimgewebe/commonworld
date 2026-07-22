# Commonworld catalogue data licence

SPDX-License-Identifier: CC0-1.0

Commonworld dedicates its own catalogue metadata, summaries, classifications and derived presentation data to the public domain under Creative Commons CC0 1.0 Universal.

This dedication applies only to material authored by Commonworld contributors and published in `catalog/`. Linked project names, trademarks, external websites, source documents, map data and third-party assets remain subject to their own rights and licences.

Source attribution and retrieval dates remain part of each CommonProject record even where attribution is not legally required. They document provenance and should be preserved when the data is reused.

Canonical licence text: https://creativecommons.org/publicdomain/zero/1.0/legalcode

## Third-party public-registry geometry

`catalog/projects/cltb-le-nid.json` contains a public address point and named building polygon derived from OpenStreetMap node 13966522352 and way 260066697. Those coordinate data are © OpenStreetMap contributors and are available under the Open Data Commons Open Database License 1.0 (ODbL). They are not covered by Commonworld's CC0 dedication. Their source identifiers and retrieval date are preserved in the CommonProject provenance.

OpenStreetMap copyright and licence information: https://www.openstreetmap.org/copyright
## Natural Earth country boundaries

`data/vendor/natural-earth/ne_110m_admin_0_countries.geojson` is the Natural Earth **Admin 0 – Countries** dataset at 1:110m scale, pinned to upstream repository commit `ca96624a56bd078437bca8184e78163e5039ad19`. Natural Earth data is in the public domain. The vendored file is used only as a build input. `assets/map/commonworld-country-boundaries.geojson` is deterministically generated from it and contains only countries needed by the current published CommonProject geometry, reducing the runtime transfer. Its boundary representation is not an endorsement by Commonworld and is not treated as authoritative jurisdictional truth. Reproducibility metadata is stored in `data/vendor/natural-earth/ne_110m_admin_0_countries.source.json`.
