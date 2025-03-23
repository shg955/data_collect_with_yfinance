#!/bin/bash

# .env 파일을 불러온다
set -a  # 자동 export 옵션 활성화
source .env
set +a  # 옵션 비활성화 (선택사항)

sudo chown -R 50000:50000 ./airflow/logs
sudo chown -R 50000:50000 ./airflow/dags
sudo chown -R 50000:50000 $DATA_PATH
sudo chown -R 50000:50000 $POSTGRES_DATA_PATH
docker-compose build
docker-compose up -d