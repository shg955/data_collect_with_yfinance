import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import os
import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf

DB_CONFIG = {
    'dbname': 'airflow',
    'user': 'airflow',
    'password': 'airflow',
    'host': 'postgres',
    'port': 5432
}

def db_connect():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tickers (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(10) UNIQUE NOT NULL,
            description TEXT,
            data_path TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    return conn

def fetch_tickers():
    conn = db_connect()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM tickers ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return rows

def add_ticker(ticker, description):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO tickers (ticker, description, created_at)
        VALUES (%s, %s, %s)
        ON CONFLICT (ticker) DO NOTHING
    """, (ticker, description, datetime.now()))
    conn.commit()
    conn.close()

def delete_ticker(ticker_id):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM tickers WHERE id=%s", (ticker_id,))
    conn.commit()
    conn.close()

def show_ticker_stats(data):
    st.subheader("📊 통계 (기본 통계량)")
    stats = data.describe()
    st.dataframe(stats)

def plot_candlestick(data):
    st.subheader("📈 캔들스틱 차트")
    st.write("데이터 확인:", data.head())
    #st.write("데이터 인덱스 타입:", type(data.index))
    fig, ax = plt.subplots(figsize=(10, 6))
    mpf.plot(data, type='candle', style='charles', ylabel='Price', ax=ax)
    st.pyplot(fig)

def main():
    st.title("📈 자동 수집 티커 관리 대시보드")

    st.header("📄 현재 등록된 티커")
    tickers = fetch_tickers()

    for t in tickers:
        col1, col2, col3, col4 = st.columns([1, 2, 1, 1])
        col1.write(f"✅ {t['ticker']}")
        col2.write(f"{t['description'] or '-'}")

        # 파일 경로가 있을 때만 다운로드 버튼 활성화
        #data_path = f"data/{t['data_path']}" if t['data_path'] else None
        if t['data_path'] and os.path.exists(t['data_path']):
            with open(t['data_path'], 'rb') as file:
                file_bytes = file.read()

            col3.download_button(
                label="⬇️ 다운로드",
                data=file_bytes,
                file_name=os.path.basename(t['data_path']),
                mime='text/csv'
            )
        else:
            col3.write("파일 없음")

        # 삭제 버튼
        if col4.button("❌ 삭제", key=f"delete_{t['id']}"):
            delete_ticker(t['id'])
            st.rerun()

        # 티커 클릭하면 상세 정보 표시
        if st.button(f"🔍 {t['ticker']} 상세 보기", key=f"details_{t['id']}"):
            # 파일 경로에서 CSV 파일을 읽어오기
            if t['data_path'] and os.path.exists(t['data_path']):
                data = pd.read_csv(t['data_path'], index_col=0, parse_dates=True)
                # 통계 정보 출력
                show_ticker_stats(data[['Open', 'Close', 'High', 'Low', 'Volume']])

                # 캔들스틱 차트
                plot_candlestick(data)

    st.header("➕ 티커 추가하기")
    new_ticker = st.text_input("티커 입력 (예: AAPL)")
    new_desc = st.text_input("설명 입력 (옵션)")

    if st.button("추가하기"):
        if new_ticker:
            add_ticker(new_ticker.upper(), new_desc)
            st.success(f"{new_ticker.upper()} 추가됨!")
            st.rerun()
        else:
            st.warning("티커를 입력하세요!")

if __name__ == "__main__":
    main()
