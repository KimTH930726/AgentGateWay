.PHONY: up down build logs test seed shell migrate

# 서버 기동 (빌드 포함)
up:
	docker compose up --build api db

# 백그라운드 기동
up-d:
	docker compose up --build -d api db

# 서버 종료 + 볼륨 제거
down:
	docker compose down -v

# 이미지만 빌드
build:
	docker compose build

# 로그 확인
logs:
	docker compose logs -f api

# 테스트 실행 (컨테이너 안, SQLite)
test:
	docker compose run --rm test

# 데모 데이터 삽입 (서버가 실행 중이어야 함)
seed:
	docker compose run --rm api python scripts/seed.py

# DB 마이그레이션만 실행
migrate:
	docker compose run --rm migrate

# api 컨테이너 셸 진입
shell:
	docker compose run --rm api bash
