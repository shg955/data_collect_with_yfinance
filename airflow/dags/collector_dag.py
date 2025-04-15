# airflow_dag.py

import requests
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.dummy_operator import DummyOperator
from datetime import datetime, timedelta
import psycopg2
import pandas as pd
import requests
import json
import os

# FastAPI 서버 주소
FASTAPI_URL = "http://collector:8000/"

GPU_SERVER = 'http://gpu-server:8000/infer'  # 도커 네트워크 이름에 맞게 수정 필요
DATA_BASE_DIR = '/data/tickers'  # CSV들이 있는 베이스 경로

# interval 리스트
INTERVALS = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"]

DB_CONFIG = {
    'dbname': 'airflow',
    'user': 'airflow',
    'password': 'airflow',
    'host': 'postgres',
    'port': 5432
}
def create_tables():
    with psycopg2.connect(**DB_CONFIG) as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS models (
                id SERIAL PRIMARY KEY,
                tag VARCHAR(100) UNIQUE NOT NULL,
                description TEXT,
                input_patch_len INT NOT NULL,
                interval VARCHAR(500),
                input_column_names TEXT,
                uploaded_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id SERIAL PRIMARY KEY,
                model_id INT REFERENCES models(id) ON DELETE CASCADE,
                ticker_id INT REFERENCES tickers(id) ON DELETE CASCADE,
                interval VARCHAR(20) NOT NULL,
                patch_end_date DATE NOT NULL,
                result JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (model_id, ticker_id, interval, patch_end_date)
            )
        """)
        conn.commit()

def load_and_infer():
    with psycopg2.connect(**DB_CONFIG) as conn:
        cur = conn.cursor()

        # 모든 모델 정보 조회
        cur.execute("SELECT id, tag, input_patch_len, interval, input_column_names FROM models")
        models = cur.fetchall()

        # ticker + interval 별 데이터 파일 정보
        cur.execute("""
            SELECT t.id, t.ticker, d.data_type, d.data_path 
            FROM ticker_data_files d 
            JOIN tickers t ON d.ticker_id = t.id
        """)
        data_files = cur.fetchall()

        for model_id, tag, patch_len, model_interval, input_column_names in models:
            input_cols = [col.strip().lower() for col in input_column_names.split(',') if col.strip()]
            model_intervals = [v.strip() for v in model_interval.split(',')] if model_interval else []

            for ticker_id, ticker, interval, data_path in data_files:
                if model_intervals and interval not in model_intervals:
                    continue

                df = pd.read_csv(os.path.join(DATA_BASE_DIR, data_path), parse_dates=['date'])
                df.columns = df.columns.str.lower()
                if not all(col in df.columns for col in input_cols):
                    print(f"[SKIP] Missing input columns for model {tag} on {ticker}: {input_cols}")
                    continue

                df = df.sort_values('date')

                for i in range(len(df) - patch_len + 1):
                    # 예측 중복 확인
                    cur.execute("""
                        SELECT 1 FROM predictions 
                        WHERE model_id=%s AND ticker_id=%s AND interval=%s AND patch_end_date=%s
                    """, (model_id, ticker_id, interval, patch_end_date))
                    if cur.fetchone():
                        continue  # 이미 있음
                      
                    patch = df.iloc[i:i+patch_len]
                    patch_end_date = patch.iloc[-1]['date'].date()


                    x_values = patch[input_cols].values.tolist()
                    input_dim = len(input_cols)

                    x_enc = [x_values]
                    x_mark_enc = [[[0] * input_dim for _ in range(patch_len)]]
                    x_dec = [[[0] * input_dim for _ in range(patch_len)]]
                    x_mark_dec = [[[0] * input_dim for _ in range(patch_len)]]

                    payload = {
                        "tag": tag,
                        "x_enc": x_enc,
                        "x_mark_enc": x_mark_enc,
                        "x_dec": x_dec,
                        "x_mark_dec": x_mark_dec,
                    }

                    response = requests.post(GPU_SERVER, json=payload)
                    if response.status_code == 200:
                        result = response.json()
                        cur.execute("""
                            INSERT INTO predictions (model_id, ticker_id, interval, patch_end_date, result)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (model_id, ticker_id, interval, patch_end_date, json.dumps(result)))
                        conn.commit()
                    else:
                        print(f"[ERROR] Inference failed: {response.text}")
                        
# 데이터 수집을 트리거하는 함수
def trigger_data_collection(interval):
    response = requests.get(f"{FASTAPI_URL}collect_data/?interval={interval}")
    
    if response.status_code == 200:
        print(f"Data collection triggered successfully for interval: {interval}")
    else:
        print(f"Failed to trigger data collection for interval: {interval}, Status Code: {response.status_code}")

# 데이터 수집을 트리거하는 함수
def nas_health_check(interval):
    
    response = requests.get(f"{FASTAPI_URL}health/nas")
    if response.status_code == 200:
        data = response.json()

        status = data.get('status')
        message = data.get('message')
        if status == 'ok':
            print(f"NAS health check passed: {message}")
        else:
            print(f"NAS health check failed: {message}")
            raise Exception(f"NAS health check failed: {message}")
    else:
        print(f"Failed to trigger data collection for interval: {interval}, Status Code: {response.status_code}")

# 기본 DAG 설정
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 3, 30, 3, 0),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'ticker_data_collection',
    default_args=default_args,
    description='수집된 티커 데이터 자동화',
    schedule_interval=timedelta(days=1),  # 매일 1번 실행
)

# 더미 시작 태스크
# start_task = DummyOperator(
#     task_id='start',
#     dag=dag,
# )
start_task = PythonOperator(
        task_id=f'NAS_health_check',
        python_callable=nas_health_check,
        #op_args=[interval],  # interval 값을 함수에 전달
        dag=dag,
    )





# interval별로 병렬 요청 태스크 생성
interval_tasks = []
before_task = start_task
for interval in INTERVALS:
    task = PythonOperator(
        task_id=f'collect_data_{interval}',
        python_callable=trigger_data_collection,
        op_args=[interval],  # interval 값을 함수에 전달
        dag=dag,
    )
    interval_tasks.append(task)
    before_task >> task  # 이전 태스크가 현재 태스크의 부모가 됨
    before_task = task  # 이전 태스크 업데이트
    #start_task >> task  # start_task가 모든 interval 태스크의 부모가 됨