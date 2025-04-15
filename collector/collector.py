import yfinance as yf
import pandas as pd
import os
from fastapi import FastAPI, Query
from enum import Enum
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import pytz
from time import sleep
from pathlib import Path
import subprocess


# UTC 타임존 객체 생성
UTC_TZ = pytz.UTC

# FastAPI 앱 설정
app = FastAPI()

DB_CONFIG = {
    'dbname': 'airflow',
    'user': 'airflow',
    'password': 'airflow',
    'host': 'postgres',  # Docker 내 Postgres라면 변경 필요
    'port': 5432
}
NAS_PATH = Path("./data")
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
    last_date = df.index[-1]
    try:
        convert_tz = pd.to_datetime(last_date).tz_convert('UTC').to_pydatetime()
    except:
        convert_tz = pd.to_datetime(last_date).tz_localize('UTC').to_pydatetime()
    return convert_tz

def fetch_new_data(ticker, start_date, end_date, interval="1d"):
    print(f"[{ticker}] Fetching from {start_date.date()} to today...")
    data = yf.download(ticker, start=start_date.date(),end=end_date, interval=interval,progress=False)
    
    if not data.empty:
        # Ticker 컬럼 제거 (만약 존재하면)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)
        
        data.index.name = 'Date'
    sleep(1)  # API 호출 간격을 두기 위해 1초 대기
    return data
def update_data_path_in_files(ticker_id, data_type, path):
    """
    Update or insert the data path for a specific ticker and data type in the ticker_data_files table.
    """
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ticker_data_files (ticker_id, data_type, data_path, created_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (ticker_id, data_type) DO UPDATE
        SET data_path = EXCLUDED.data_path, created_at = NOW()
    """, (ticker_id, data_type, path))
    conn.commit()
    conn.close()
    
#“1m”, “2m”, “5m”, “15m”, “30m”, “60m”, “90m”, “1h”, “1d”, “5d”, “1wk”, “1mo”, “3mo”
# 유효한 interval 값을 정의
class Interval(str, Enum):
    one_minute = "1m"
    two_minutes = "2m"
    five_minutes = "5m"
    fifteen_minutes = "15m"
    thirty_minutes = "30m"
    sixty_minutes = "60m"
    ninety_minutes = "90m"
    one_hour = "1h"
    one_day = "1d"
    five_days = "5d"
    one_week = "1wk"
    one_month = "1mo"
    three_months = "3mo"
    
@app.get("/collect_data/")
async def main(interval: Interval = Query("1d", description="데이터 수집 간격 (예: “1m”, “2m”, “5m”, “15m”, “30m”, “60m”, “90m”, “1h”, “1d”, “5d”, “1wk”, “1mo”, “3mo”)")):
    # 상위 폴더에 data 디렉토리 생성
    data_dir = "./data"
    try:
        os.makedirs(data_dir, exist_ok=True)
    except:
        pass

    tickers = get_ticker_list()
    print(f"Found {len(tickers)} tickers to process...")

    for ticker_entry in tickers:
        ticker_id = ticker_entry['id']
        ticker = ticker_entry['ticker']

        # 데이터 경로 설정
        data_path = f"./data/{ticker}_{interval.value}.csv"

        # 데이터 경로를 업데이트하거나 삽입
        update_data_path_in_files(ticker_id, interval.value, data_path)

        try:
            os.makedirs(os.path.dirname(data_path), exist_ok=True)
        except:
            pass

        existing_df = fetch_existing_data(data_path)
        last_date = get_last_date(existing_df)

        if last_date:
            start_date = last_date + timedelta(days=1)
        else:
            start_date = datetime(2000, 1, 1, tzinfo=UTC_TZ)
        # interval이 1d 미만인 경우, start_date를 현재 날짜로부터 60일 전으로 제한
        if interval.value in ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"]:
            if interval.value in ["2m", "5m", "15m", "30m", "60m", "90m", "1h"]:
                max_start_date = datetime.now(UTC_TZ) - timedelta(days=59)
            else:
                max_start_date = datetime.now(UTC_TZ) - timedelta(days=7)
            if start_date < max_start_date:
                start_date = max_start_date
                
        today = datetime.now(UTC_TZ).date() 

        if start_date.date() >= today:
            print(f"[{ticker} - {interval.value}] Already up-to-date.")
            continue

        new_data = fetch_new_data(ticker, start_date, today, interval=interval.value)
        # Fetch new data for the specified interval
        #new_data = yf.download(ticker, start=start_date, interval=interval, progress=False)

        if new_data.empty:
            print(f"[{ticker} - {interval.value}] No new data found.")
            continue
        else:
            print(f"[{ticker} New data found. Rows: {len(new_data)}] ")

        updated_df = pd.concat([existing_df, new_data])
        updated_df = updated_df[~updated_df.index.duplicated(keep='last')]

        save_data(data_path, updated_df)
        print(f"[{ticker} - {interval.value}] Data updated. Rows: {len(updated_df)}")

    return {"message": "Data collection triggered successfully"}

def is_nas_connected() -> bool:
    try:
        NAS_PATH.stat()
        return True
    except:
        return False

@app.get("/health/nas")
def health_check_nas():
    if is_nas_connected():
        return {"status": "ok", "message": "NAS is connected"}
    else:
        return {"status": "fail", "message": "NAS is not connected"}
# 티커 리스트를 받아서 데이터 수집을 트리거하는 API 엔드포인트
# @app.get("/collect_data/")
# async def main():
#     # 상위 폴더에 data 디렉토리 생성
#     data_dir = "./data"
#     try:
#         os.makedirs(data_dir, exist_ok=True)
#     except:
#         pass
#     tickers = get_ticker_list()
#     print(f"Found {len(tickers)} tickers to process...")

#     for ticker_entry in tickers:
#         ticker_id = ticker_entry['id']
#         ticker = ticker_entry['ticker']
#         data_path = ticker_entry['data_path']

#         if not data_path:
#             data_path = f"./data/{ticker}.csv"
#             update_data_path(ticker_id, data_path)

#         try:
#             os.makedirs(os.path.dirname(data_path), exist_ok=True)
#         except:
#             pass

#         existing_df = fetch_existing_data(data_path)
#         last_date = get_last_date(existing_df)

#         if last_date:
#             start_date = last_date + timedelta(days=1)
#         else:
#             start_date = datetime(2000, 1, 1)

#         today = datetime.now().date()

#         if start_date.date() > today:
#             print(f"[{ticker}] Already up-to-date.")
#             continue

#         new_data = fetch_new_data(ticker, start_date)

#         if new_data.empty:
#             print(f"[{ticker}] No new data found.")
#             continue

#         updated_df = pd.concat([existing_df, new_data])
#         updated_df = updated_df[~updated_df.index.duplicated(keep='last')]

#         save_data(data_path, updated_df)
#         print(f"[{ticker}] Data updated. Rows: {len(updated_df)}")
#     return {"message": "Data collection triggered successfully"}
# #if __name__ == "__main__":
# #    main()
