.PHONY: validate validate-contracts test

validate: validate-contracts test

validate-contracts:
	python3 scripts/validate_contracts.py

test:
	python3 -m unittest discover -s tests -p 'test_*.py'
