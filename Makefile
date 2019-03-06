default: lint static test

test_requirements.freeze: test_requirements.txt
	pip install -r test_requirements.txt
	pip freeze > test_requirements.freeze

lint: test_requirements.freeze
	pycodestyle --ignore=E402 --max-line-length 159 .

static: test_requirements.freeze
	mypy --ignore-missing-imports .

test: test_requirements.freeze
	pytest tests

coverage: test_requirements.freeze
	coverage run --source errata_server `which pytest` tests
	coverage report

.PHONY: test coverage
