.PHONY: build-frontend build dev dev-frontend

build-frontend:
	cd frontend && npm install && npm run build

build: build-frontend

dev:
	PYTHONPATH=src uvicorn kitkat.main:app --reload

dev-frontend:
	cd frontend && npm run dev
