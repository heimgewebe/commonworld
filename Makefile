.PHONY: build validate validate-cache-coherence validate-security-policy validate-proposal-path validate-current-state validate-locale-release browser-smoke validate-canonical-plan validate-contracts validate-commons-admission validate-semantic-zoom validate-visual-semantics validate-renderer-spike validate-maplibre-phase2-proof validate-device-acceptance-pack validate-device-acceptance-rerun validate-digital-sphere validate-digital-ring-taxonomy validate-layered-digital-sphere-proof validate-digital-sphere-real-surface validate-device-acceptance-performance-v4 validate-physical-device-acceptance-v4-apple validate-public-catalog validate-public-seed-baseline validate-presence-axes validate-intent-search-discovery validate-renderer-selection validate-public-maplibre-vertical-slice validate-production-delivery-provider validate-public-shell validate-catalog-delivery-budget validate-catalog-browser-measurement-decision validate-catalog-scale-gates test-js test smoke-pages-live check-pages-dns-target

build:
	npm run build

validate-cache-coherence:
	python3 scripts/validate_cache_coherence.py

validate: validate-cache-coherence validate-security-policy validate-proposal-path validate-current-state validate-canonical-plan validate-contracts validate-locale-release validate-commons-admission validate-semantic-zoom validate-visual-semantics validate-renderer-spike validate-maplibre-phase2-proof validate-device-acceptance-pack validate-device-acceptance-rerun validate-digital-sphere validate-digital-ring-taxonomy validate-layered-digital-sphere-proof validate-digital-sphere-real-surface validate-device-acceptance-performance-v4 validate-physical-device-acceptance-v4-apple validate-public-catalog validate-public-seed-baseline validate-presence-axes validate-intent-search-discovery validate-renderer-selection validate-public-maplibre-vertical-slice validate-production-delivery-provider validate-public-shell validate-catalog-delivery-budget validate-catalog-browser-measurement-decision validate-catalog-scale-gates test-js test

validate-proposal-path:
	python3 scripts/validate_proposal_path.py

validate-current-state:
	python3 scripts/validate_current_state.py

validate-canonical-plan:
	python3 scripts/validate_canonical_plan.py

validate-contracts:
	python3 scripts/validate_contracts.py

validate-locale-release:
	python3 scripts/validate_locale_release.py

validate-commons-admission:
	python3 scripts/validate_commons_admission.py

validate-semantic-zoom:
	python3 scripts/validate_semantic_zoom.py

validate-visual-semantics:
	python3 scripts/validate_visual_semantics.py

validate-renderer-spike:
	python3 scripts/validate_renderer_spike.py

validate-maplibre-phase2-proof:
	python3 scripts/validate_maplibre_phase2_proof.py

validate-device-acceptance-pack:
	python3 scripts/validate_device_acceptance_pack.py

validate-device-acceptance-rerun:
	python3 scripts/validate_device_acceptance_rerun.py

validate-digital-sphere:
	python3 scripts/validate_digital_sphere.py

validate-digital-ring-taxonomy:
	python3 scripts/validate_digital_ring_taxonomy.py

validate-layered-digital-sphere-proof:
	python3 scripts/validate_layered_digital_sphere_proof.py

validate-digital-sphere-real-surface:
	python3 scripts/validate_digital_sphere_real_surface.py

validate-device-acceptance-performance-v4:
	python3 scripts/validate_device_acceptance_performance_v4.py

validate-physical-device-acceptance-v4-apple:
	python3 scripts/validate_physical_device_acceptance_v4_apple.py

validate-public-catalog:
	python3 scripts/validate_public_catalog.py

validate-public-seed-baseline:
	python3 scripts/validate_public_seed_baseline.py

validate-presence-axes:
	@echo "Validating derived presence dimensions..."
	python3 scripts/validate_presence_axes.py

validate-intent-search-discovery:
	python3 scripts/validate_intent_search_discovery.py

validate-renderer-selection:
	python3 scripts/validate_renderer_selection.py

validate-public-maplibre-vertical-slice:
	python3 scripts/validate_public_maplibre_vertical_slice.py

validate-production-delivery-provider:
	python3 scripts/validate_production_delivery_provider.py

validate-security-policy:
	python3 scripts/validate_security_policy.py

validate-public-shell:
	python3 scripts/validate_public_shell.py

validate-catalog-delivery-budget: build
	python3 scripts/validate_catalog_delivery_budget.py

validate-catalog-browser-measurement-decision:
	python3 scripts/validate_catalog_browser_measurement_decision.py

validate-catalog-scale-gates:
	python3 scripts/validate_catalog_scale_gates.py
	python3 scripts/validate_catalog_scale_masterplan.py

test-js:
	npm test

test:
	python3 -m unittest discover -s tests -p 'test_*.py'

smoke-pages-live:
	python3 scripts/smoke_pages_live.py

check-pages-dns-target:
	python3 scripts/check_pages_dns_target.py

browser-smoke:
	npm run smoke:browser
