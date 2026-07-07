.PHONY: validate validate-contracts validate-mixed-node-proof validate-map-proof validate-map-source-strategy validate-aether-proof validate-proof-hub validate-mobile-atlas-shift validate-mobile-atlas-shift-doctrine test

validate: validate-contracts validate-mixed-node-proof validate-map-proof validate-map-source-strategy validate-aether-proof validate-proof-hub validate-mobile-atlas-shift validate-mobile-atlas-shift-doctrine test

validate-contracts:
	python3 scripts/validate_contracts.py

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

test:
	python3 -m unittest discover -s tests -p 'test_*.py'
