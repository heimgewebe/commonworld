.PHONY: validate $(VALIDATE_TARGETS)

VALIDATE_TARGETS = \
	validate-contracts \
	validate-seed-manifest \
	validate-mixed-node-proof \
	validate-map-proof \
	validate-map-source-strategy \
	validate-aether-proof \
	validate-proof-hub \
	validate-mobile-atlas-shift \
	validate-mobile-atlas-shift-doctrine \
	validate-projection-contract \
	validate-source-curation-policy \
	test

validate: $(VALIDATE_TARGETS)

validate-contracts:
	python3 scripts/validate_contracts.py

validate-seed-manifest:
	python3 scripts/validate_seed_manifest.py

validate-mixed-node-proof:
	python3 scripts/validate_mixed_node_proof.py

validate-map-proof:
	python3 scripts/validate_map_proof.py

validate-map-source-strategy:
	python3 scripts/validate_map_source_strategy.py

validate-aether-proof:
	python3 scripts/validate_aether_proof.py

validate-proof-hub:
	python3 scripts/validate_proof_hub.py

validate-mobile-atlas-shift:
	python3 scripts/validate_mobile_atlas_shift.py

validate-mobile-atlas-shift-doctrine:
	python3 scripts/validate_mobile_atlas_shift_doctrine.py

validate-projection-contract:
	python3 scripts/validate_projection_contract.py

validate-source-curation-policy:
	python3 scripts/validate_source_curation_policy.py

test:
	python3 -m unittest discover -s tests -p 'test_*.py'
