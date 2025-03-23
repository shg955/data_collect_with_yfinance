import yfinance as yf
import pandas as pd
import os
from fastapi import FastAPI
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

# FastAPI 앱 설정
app = FastAPI()

DB_CONFIG = {
    'dbname': 'airflow',
    'user': 'airflow',
    'password': 'airflow',
    'host': 'postgres',  # Docker 내 Postgres라면 변경 필요
    'port': 5432
}

def db_connect():
    conn = psycopg2.connect(**DB_CONFIG)
    return conn

def get_ticker_list():
    conn = db_connect()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM tickers")
    tickers = cur.fetchall()
    conn.close()
    return tickers

def update_data_path(ticker_id, path):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("UPDATE tickers SET data_path=%s WHERE id=%s", (path, ticker_id))
    conn.commit()
    conn.close()

def fetch_existing_data(path):
    if os.path.exists(path):
        df = pd.read_csv(path, index_col='Date', parse_dates=True)
        return df
    else:
        return pd.DataFrame()

def save_data(path, df):
    df.to_csv(path)

def get_last_date(df):
    if df.empty:
        return None
    return df.index[-1]

def fetch_new_data(ticker, start_date):
    print(f"[{ticker}] Fetching from {start_date.date()} to today...")
    data = yf.download(ticker, start=start_date, progress=False)
    
    if not data.empty:
        # Ticker 컬럼 제거 (만약 존재하면)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)
        
        data.index.name = 'Date'
    
    return data
# 티커 리스트를 받아서 데이터 수집을 트리거하는 API 엔드포인트
@app.get("/collect_data/")
async def main():
    # 상위 폴더에 data 디렉토리 생성
    data_dir = "./data"
    os.makedirs(data_dir, exist_ok=True)
    tickers = get_ticker_list()
    print(f"Found {len(tickers)} tickers to process...")

    for ticker_entry in tickers:
        ticker_id = ticker_entry['id']
        ticker = ticker_entry['ticker']
        data_path = ticker_entry['data_path']

        if not data_path:
            data_path = f"./data/{ticker}.csv"
            update_data_path(ticker_id, data_path)

        os.makedirs(os.path.dirname(data_path), exist_ok=True)

        existing_df = fetch_existing_data(data_path)
        last_date = get_last_date(existing_df)

        if last_date:
            start_date = last_date + timedelta(days=1)
        else:
            start_date = datetime(2000, 1, 1)

        today = datetime.now().date()

        if start_date.date() > today:
            print(f"[{ticker}] Already up-to-date.")
            continue

        new_data = fetch_new_data(ticker, start_date)

        if new_data.empty:
            print(f"[{ticker}] No new data found.")
            continue

        updated_df = pd.concat([existing_df, new_data])
        updated_df = updated_df[~updated_df.index.duplicated(keep='last')]

        save_data(data_path, updated_df)
        print(f"[{ticker}] Data updated. Rows: {len(updated_df)}")
    return {"message": "Data collection triggered successfully"}
#if __name__ == "__main__":
#    main()
