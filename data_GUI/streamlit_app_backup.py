import streamlit as st
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

DB_CONFIG = {
    'dbname': 'airflow',
    'user': 'airflow',
    'password': 'airflow',
    'host': 'postgres',
    'port': 5432
}

def db_connect():
    conn = psycopg2.connect(**DB_CONFIG)
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

def main():
    st.title("📈 자동 수집 티커 관리 대시보드")

    st.header("📄 현재 등록된 티커")
    tickers = fetch_tickers()

    for t in tickers:
        col1, col2, col3, col4 = st.columns([1, 2, 1, 1])
        col1.write(f"✅ {t['ticker']}")
        col2.write(f"{t['description'] or '-'}")

        # 파일 경로가 있을 때만 다운로드 버튼 활성화
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
