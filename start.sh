#!/bin/bash
# .env 파일을 불러온다
set -a  # 자동 export 옵션 활성화
source .env
set +a  # 옵션 비활성화 (선택사항)


if [ ! -d "./mlflow_artifacts" ]; then
    mkdir "./mlflow_artifacts"
fi
if [ ! -d "./airflow/logs" ]; then
    mkdir "./airflow/logs"
fi
if [ ! -d "./airflow/dags" ]; then
    mkdir "./airflow/dags"
fi
if [ ! -d $POSTGRES_DATA_PATH ]; then
    mkdir $POSTGRES_DATA_PATH
fi
if [ ! -d $DATA_PATH ]; then
    mkdir $DATA_PATH
fi

sudo chown -R 50000:50000 ./airflow/logs
sudo chown -R 50000:50000 ./airflow/dags
sudo chown -R 50000:50000 $DATA_PATH
sudo chown -R 50000:50000 $POSTGRES_DATA_PATH  
sudo chmod -R 777 ./mlflow_artifacts
sudo chmod -R 777 ./airflow/logs
sudo chmod -R 777 ./airflow/dags
sudo chmod -R 777 $DATA_PATH
sudo chmod -R 777 $POSTGRES_DATA_PATH
docker-compose build
docker-compose up -d