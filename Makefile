.PHONY: up down db-shell venv test lint
up:
	docker compose up -d db
down:
	docker compose down
db-shell:
	docker compose exec db mysql -uplanner -pplanner planner
venv:
	python3 -m venv backend/.venv && backend/.venv/bin/pip install -e "backend[dev]"
test:
	cd backend && .venv/bin/pytest -q
lint:
	cd backend && .venv/bin/ruff check .
