.PHONY: validate validate-canonical-plan validate-contracts validate-semantic-zoom validate-visual-semantics validate-renderer-spike validate-maplibre-phase2-proof validate-public-shell test smoke-pages-live check-pages-dns-target

validate: validate-canonical-plan validate-contracts validate-semantic-zoom validate-visual-semantics validate-renderer-spike validate-maplibre-phase2-proof validate-public-shell test

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

validate-public-shell:
	python3 scripts/validate_public_shell.py

test:
	python3 -m unittest discover -s tests -p 'test_*.py'

smoke-pages-live:
	python3 scripts/smoke_pages_live.py

check-pages-dns-target:
	python3 scripts/check_pages_dns_target.py
