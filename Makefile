.PHONY: check format test

check:
	uv run ruff check

format:
	uv run ruff format
	uv run docformatter -i -r .

test:
	uv run coverage run -m pytest -rpPfE
	uv run coverage report -m -i
