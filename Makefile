.PHONY: validate validate-contracts validate-mixed-node-proof test

validate: validate-contracts validate-mixed-node-proof test

validate-contracts:
	python3 scripts/validate_contracts.py

validate-mixed-node-proof:
	python3 scripts/validate_mixed_node_proof.py

test:
	python3 -m unittest discover -s tests -p 'test_*.py'
