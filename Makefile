.PHONY: up down db-shell venv test lint pipelines-venv pipeline-list pipeline step survey survey-import test-pipelines
PY_PIPE = pipelines/.venv/bin/python

up:
	docker compose up -d db
down:
	docker compose down
db-shell:
	docker compose exec db mysql -uplanner -pplanner planner

# ---- backend ----
venv:
	python3 -m venv backend/.venv && backend/.venv/bin/pip install -e "backend[dev]"
test:
	cd backend && .venv/bin/pytest -q
lint:
	cd backend && .venv/bin/ruff check .
	cd pipelines && .venv/bin/ruff check .

# ---- pipeline dữ liệu: mọi lệnh đi qua flow (pipelines/itinerary_pipelines/flow.py) ----
PIPE = pipelines/.venv/bin/python -m itinerary_pipelines
STEP ?=
pipelines-venv:
	python3 -m venv pipelines/.venv && pipelines/.venv/bin/pip install -e "pipelines[dev]"
pipeline-list:
	$(PIPE) list
pipeline:                 # toàn bộ luồng; make pipeline FROM=clean để chạy từ một bước
	$(PIPE) flow $(if $(FROM),--from $(FROM),)
step:                     # make step STEP=survey_export
	$(PIPE) $(STEP)
survey:                   # sinh/cập nhật CSV khảo sát (giữ phần đã điền)
	$(PIPE) survey_export
survey-import:            # nạp CSV đã điền vào MySQL
	$(PIPE) survey_import
test-pipelines:
	cd pipelines && TEST_DATABASE_URL=$${TEST_DATABASE_URL:-mysql+pymysql://planner:planner@localhost:3306/planner_test} .venv/bin/pytest -q
