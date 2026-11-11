.PHONY: setup ingest transforms test eval run-api run-ui docker-up docker-down

setup:
	pip install -r requirements.txt

seed:
	python src/ingestion/seed_generator.py

ingest:
	python -m src.ingestion.structured_loader
	python -m src.ingestion.unstructured_loader

transforms:
	python -m src.lakehouse.silver_transforms
	python -m src.lakehouse.quality_gate
	python -m src.lakehouse.gold_transforms

index:
	python -c "from src.retrieval.hybrid_retriever import HybridRetriever; hr = HybridRetriever(); hr.index_gold_chunks()"

pipeline: seed ingest transforms index

test:
	python -m pytest tests/test_platform.py -v

eval:
	python -m evaluation.evaluator

run-api:
	uvicorn src.orchestrator.main:app --host 0.0.0.0 --port 8000 --reload

run-ui:
	streamlit run src/ui/app.py --server.port 8501

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
