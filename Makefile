.PHONY: validate validate-canonical-plan validate-contracts validate-semantic-zoom validate-visual-semantics validate-renderer-spike validate-maplibre-phase2-proof validate-device-acceptance-pack validate-device-acceptance-rerun validate-digital-sphere validate-layered-digital-sphere-proof validate-digital-sphere-real-surface validate-device-acceptance-performance-v4 validate-physical-device-acceptance-v4-apple validate-public-catalog validate-renderer-selection validate-public-shell test smoke-pages-live check-pages-dns-target

validate: validate-canonical-plan validate-contracts validate-semantic-zoom validate-visual-semantics validate-renderer-spike validate-maplibre-phase2-proof validate-device-acceptance-pack validate-device-acceptance-rerun validate-digital-sphere validate-layered-digital-sphere-proof validate-digital-sphere-real-surface validate-device-acceptance-performance-v4 validate-physical-device-acceptance-v4-apple validate-public-catalog validate-renderer-selection validate-public-shell test

validate-canonical-plan:
	python3 scripts/validate_canonical_plan.py

validate-contracts:
	python3 scripts/validate_contracts.py

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

validate-renderer-selection:
	python3 scripts/validate_renderer_selection.py

validate-public-shell:
	python3 scripts/validate_public_shell.py

test:
	python3 -m unittest discover -s tests -p 'test_*.py'

smoke-pages-live:
	python3 scripts/smoke_pages_live.py

check-pages-dns-target:
	python3 scripts/check_pages_dns_target.py
