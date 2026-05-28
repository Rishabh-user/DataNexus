.PHONY: run worker beat migrate test lint

run:
	cd backend && uvicorn app.main:app --reload --port 8000

worker:
	cd backend && celery -A app.core.celery_app worker -l info -Q default,file_processing,onedrive_sync,reports,embeddings

beat:
	cd backend && celery -A app.core.celery_app beat -l info

migrate:
	cd backend && alembic upgrade head

migration:
	cd backend && alembic revision --autogenerate -m "$(msg)"

test:
	cd backend && python -m pytest -v

lint:
	ruff check backend/
	ruff format --check backend/

format:
	ruff format backend/

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f
