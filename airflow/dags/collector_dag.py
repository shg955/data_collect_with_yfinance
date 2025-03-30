# airflow_dag.py

import requests
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime, timedelta

# FastAPI 서버 주소
FASTAPI_URL = "http://collector:8000/collect_data/"

# 데이터 수집을 트리거하는 함수
def trigger_data_collection():
    #tickers = ["TSLA", "AAPL", "GOOG"]  # 예시로 사용될 티커 리스트
    response = requests.get(FASTAPI_URL)
    
    if response.status_code == 200:
        print("Data collection triggered successfully")
    else:
        print("Failed to trigger data collection:", response.status_code)

# 기본 DAG 설정
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 3, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'ticker_data_collection',
    default_args=default_args,
    description='수집된 티커 데이터 자동화',
    schedule_interval=timedelta(days=1),  # 매일 1번 실행
)

# DAG 작업 정의
collect_data_task = PythonOperator(
    task_id='collect_data',
    python_callable=trigger_data_collection,  # FastAPI로 요청을 보내는 함수 호출
    dag=dag,
)

collect_data_task
