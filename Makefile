.PHONY: validate generate-catalog-export generate-catalog-api-route-fixtures generate-search-index-input $(VALIDATE_TARGETS)

VALIDATE_TARGETS = \
	validate-contracts \
	validate-seed-manifest \
	validate-shared-aspects \
	validate-mixed-node-proof \
	validate-map-proof \
	validate-map-proof-offline-smoke \
	validate-map-source-strategy \
	validate-aether-proof \
	validate-search-proof \
	validate-search-query-fixtures \
	validate-proof-surfaces \
	validate-proof-hub \
	validate-proof-hub-offline-smoke \
	validate-mobile-atlas-shift \
	validate-mobile-atlas-shift-doctrine \
	validate-projection-contract \
	validate-source-curation-policy \
	validate-weltgewebe-handoff-contract \
	validate-runtime-scale-boundary \
	validate-catalog-export-contract \
	validate-catalog-api-contract \
	validate-catalog-api-route-fixtures \
	validate-search-index-input-contract \
	validate-search-index-input \
	test

validate: $(VALIDATE_TARGETS)

validate-contracts:
	python3 scripts/validate_contracts.py

validate-seed-manifest:
	python3 scripts/validate_seed_manifest.py

validate-shared-aspects:
	python3 scripts/validate_shared_aspects.py

validate-mixed-node-proof:
	python3 scripts/validate_mixed_node_proof.py

validate-map-proof:
	python3 scripts/validate_map_proof.py

validate-map-proof-offline-smoke:
	python3 scripts/smoke_map_proof_offline.py >/dev/null

validate-map-source-strategy:
	python3 scripts/validate_map_source_strategy.py

validate-aether-proof:
	python3 scripts/validate_aether_proof.py

validate-search-proof:
	python3 scripts/validate_search_proof.py

validate-search-query-fixtures:
	python3 scripts/validate_search_query_fixtures.py

validate-proof-surfaces:
	python3 scripts/validate_proof_surfaces.py

validate-proof-hub:
	python3 scripts/validate_proof_hub.py

validate-proof-hub-offline-smoke:
	python3 scripts/smoke_proof_hub_offline.py >/dev/null

validate-mobile-atlas-shift:
	python3 scripts/validate_mobile_atlas_shift.py

validate-mobile-atlas-shift-doctrine:
	python3 scripts/validate_mobile_atlas_shift_doctrine.py

validate-projection-contract:
	python3 scripts/validate_projection_contract.py

validate-source-curation-policy:
	python3 scripts/validate_source_curation_policy.py

validate-weltgewebe-handoff-contract:
	python3 scripts/validate_weltgewebe_handoff_contract.py

validate-runtime-scale-boundary:
	python3 scripts/validate_runtime_scale_boundary.py

validate-catalog-export-contract:
	python3 scripts/generate_catalog_export.py --check
	python3 scripts/validate_catalog_export_contract.py

validate-catalog-api-contract:
	python3 scripts/validate_catalog_api_contract.py

validate-catalog-api-route-fixtures:
	python3 scripts/generate_catalog_api_route_fixtures.py --check
	python3 scripts/validate_catalog_api_route_fixtures.py

validate-search-index-input-contract:
	python3 scripts/validate_search_index_input_contract.py

validate-search-index-input:
	python3 scripts/generate_search_index_input.py --check
	python3 scripts/validate_search_index_input.py

generate-catalog-export:
	python3 scripts/generate_catalog_export.py

generate-catalog-api-route-fixtures:
	python3 scripts/generate_catalog_api_route_fixtures.py

generate-search-index-input:
	python3 scripts/generate_search_index_input.py

test:
	python3 -m unittest discover -s tests -p 'test_*.py'

.PHONY: smoke-map-browser
smoke-map-browser:
	python3 scripts/smoke_map_proof_browser.py

.PHONY: capture-proof-hub-browser-smoke
capture-proof-hub-browser-smoke:
	python3 scripts/smoke_proof_hub_browser.py

.PHONY: smoke-pages-live
smoke-pages-live:
	python3 scripts/smoke_pages_live.py

.PHONY: check-pages-dns-target
check-pages-dns-target:
	python3 scripts/check_pages_dns_target.py
