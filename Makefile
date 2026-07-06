.PHONY: validate validate-contracts validate-mixed-node-proof validate-map-proof test

validate: validate-contracts validate-mixed-node-proof validate-map-proof test

validate-contracts:
	python3 scripts/validate_contracts.py

validate-mixed-node-proof:
	python3 scripts/validate_mixed_node_proof.py

validate-map-proof:
	python3 scripts/validate_map_proof.py

test:
	python3 -m unittest discover -s tests -p 'test_*.py'
