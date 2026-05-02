.PHONY: install backend test lint godot

install:
	cd backend && pip install -e ".[dev]"

backend:
	cd backend && uvicorn src.main:app --reload --host 127.0.0.1 --port 8000

test:
	cd backend && pytest -v

lint:
	cd backend && ruff check src tests && mypy src

godot:
	@echo "Open godot_client/project.godot in Godot 4 editor"
