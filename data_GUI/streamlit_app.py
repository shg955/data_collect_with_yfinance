import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import os
import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf
from datetime import datetime, timedelta, timezone

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
    # tickers 테이블 정의
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tickers (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(10) UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # ticker_data_files 테이블 정의
    #“1m”, “2m”, “5m”, “15m”, “30m”, “60m”, “90m”, “1h”, “1d”, “5d”, “1wk”, “1mo”, “3mo”
    # -- 동일 티커에 대해 중복 데이터 타입 방지
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ticker_data_files (
            id SERIAL PRIMARY KEY,
            ticker_id INT NOT NULL REFERENCES tickers(id) ON DELETE CASCADE,
            data_type VARCHAR(20) NOT NULL,
            data_path TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (ticker_id, data_type)
        )
    """)    
    # cur.execute("""
    #     CREATE TABLE IF NOT EXISTS tickers (
    #         id SERIAL PRIMARY KEY,
    #         ticker VARCHAR(10) UNIQUE NOT NULL,
    #         description TEXT,
    #         data_path TEXT,
    #         created_at TIMESTAMP DEFAULT NOW()
    #     )
    # """)
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
    st.write("데이터 확인 [시작일]:", data.head())
    st.write("데이터 확인 [종료일]:", data.tail())
    #st.write("데이터 인덱스 타입:", type(data.index))
    # 현재 날짜 기준으로 5일 전 계산
    # five_days_ago = pd.Timestamp.now(tz='UTC') - timedelta(days=5)
    # # 인덱스가 5일 전 이후인 데이터만 필터링
    # filtered_data = data[data.index >= five_days_ago]
    fig2, ax1 = plt.subplots(figsize=(10, 6))
    mpf.plot(data[-30:], type='candle', style='charles', ylabel='Price', 
         #volume=True,  # 거래량 추가
         #ylabel_lower='Volume',  # 거래량 축 레이블
         ax=ax1)
    st.write("데이터 확인 마지막 30개")
    st.pyplot(fig2)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    mpf.plot(data, type='candle', style='charles', ylabel='Price', ax=ax)
    st.write("데이터 확인 전체")
    st.pyplot(fig)
    # mpf.plot(data[-5:], type='candle', style='charles', ylabel='Price', ax=ax1)
     
def fetch_ticker_data_files(ticker_id):
    conn = db_connect()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT data_type, data_path FROM ticker_data_files
        WHERE ticker_id = %s
        ORDER BY data_type
    """, (ticker_id,))
    rows = cur.fetchall()
    conn.close()
    return rows
def initialize_tickers_from_file():
    """
    ticker_list.txt 파일에서 티커 목록을 읽어와 DB에 삽입
    """
    # ticker_list.txt 파일 경로
    ticker_file_path = "./ticker_list.txt"

    # 파일이 존재하지 않으면 경고 메시지 출력
    if not os.path.exists(ticker_file_path):
        st.warning("⚠️ ticker_list.txt 파일이 존재하지 않습니다. 초기화 작업을 건너뜁니다.")
        return

    # 파일에서 티커 목록 읽기
    with open(ticker_file_path, "r") as file:
        tickers = [line.strip() for line in file.readlines() if line.strip()]

    # DB에 티커 목록 삽입
    for ticker in tickers:
        add_ticker(ticker, description=None)  # description은 None으로 설정

    st.success("✅ ticker_list.txt 파일에서 티커 목록이 초기화되었습니다.")
def main():
    st.title("📈 자동 수집 티커 관리 대시보드")

    # 테이블이 비어 있는지 확인
    tickers = fetch_tickers()
    if not tickers:  # 테이블이 비어 있으면 초기화
        st.info("📄 티커 테이블이 비어 있습니다. ticker_list.txt 파일에서 초기화 중...")
        initialize_tickers_from_file()
        tickers = fetch_tickers()  # 초기화 후 다시 가져오기
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
    st.header("📄 현재 등록된 티커")
    tickers = fetch_tickers()

    for t in tickers:
        col1, col2, col3, col4 = st.columns([1, 2, 1, 1])
        col1.write(f"✅ {t['ticker']}")
        col2.write(f"{t['description'] or '-'}")

        # 삭제 버튼
        if col4.button("❌ 삭제", key=f"delete_{t['id']}"):
            delete_ticker(t['id'])
            st.rerun()

        # 티커 클릭하면 상세 정보 표시
        if st.button(f"🔍 {t['ticker']} 상세 보기", key=f"details_{t['id']}"):
            # 데이터 파일 정보 가져오기
            data_files = fetch_ticker_data_files(t['id'])

            if data_files:
                tabs = st.tabs([f"{df['data_type']}" for df in data_files])
                for i, df in enumerate(data_files):
                    with tabs[i]:
                        st.subheader(f"📂 {df['data_type']} 데이터")
                        if df.get("data_path"):#os.path.exists(df['data_path']):
                            # 데이터 읽기
                            data=None
                            try:
                                data = pd.read_csv(df['data_path'], index_col=0, parse_dates=True)
                            except FileNotFoundError as e:
                                if "No such file or directory" in str(e):
                                    st.warning("❌ NAS 연결이 끊겼거나, 파일이 없음")
                                else:
                                    st.warning("📛 다른 이유로 파일을 못 읽음")
                                continue
                                

                            # 통계 정보 출력
                            show_ticker_stats(data[['Open', 'Close', 'High', 'Low', 'Volume']])

                            # 캔들스틱 차트
                            plot_candlestick(data)

                            # 다운로드 버튼
                            with open(df['data_path'], 'rb') as file:
                                file_bytes = file.read()

                            st.download_button(
                                label="⬇️ 데이터 다운로드",
                                data=file_bytes,
                                file_name=os.path.basename(df['data_path']),
                                mime='text/csv'
                            )
                        else:
                            st.warning("데이터 파일이 존재하지 않습니다.")
            else:
                st.info("등록된 데이터 파일이 없습니다.")

# def main():
#     st.title("📈 자동 수집 티커 관리 대시보드")

#     st.header("📄 현재 등록된 티커")
#     tickers = fetch_tickers()

#     for t in tickers:
#         col1, col2, col3, col4 = st.columns([1, 2, 1, 1])
#         col1.write(f"✅ {t['ticker']}")
#         col2.write(f"{t['description'] or '-'}")

#         # 파일 경로가 있을 때만 다운로드 버튼 활성화
#         #data_path = f"data/{t['data_path']}" if t['data_path'] else None
#         if t['data_path'] and os.path.exists(t['data_path']):
#             with open(t['data_path'], 'rb') as file:
#                 file_bytes = file.read()

#             col3.download_button(
#                 label="⬇️ 다운로드",
#                 data=file_bytes,
#                 file_name=os.path.basename(t['data_path']),
#                 mime='text/csv'
#             )
#         else:
#             col3.write("파일 없음")

#         # 삭제 버튼
#         if col4.button("❌ 삭제", key=f"delete_{t['id']}"):
#             delete_ticker(t['id'])
#             st.rerun()

#         # 티커 클릭하면 상세 정보 표시
#         if st.button(f"🔍 {t['ticker']} 상세 보기", key=f"details_{t['id']}"):
#             # 파일 경로에서 CSV 파일을 읽어오기
#             if t['data_path'] and os.path.exists(t['data_path']):
#                 data = pd.read_csv(t['data_path'], index_col=0, parse_dates=True)
#                 # 통계 정보 출력
#                 show_ticker_stats(data[['Open', 'Close', 'High', 'Low', 'Volume']])

#                 # 캔들스틱 차트
#                 plot_candlestick(data)

#     st.header("➕ 티커 추가하기")
#     new_ticker = st.text_input("티커 입력 (예: AAPL)")
#     new_desc = st.text_input("설명 입력 (옵션)")

#     if st.button("추가하기"):
#         if new_ticker:
#             add_ticker(new_ticker.upper(), new_desc)
#             st.success(f"{new_ticker.upper()} 추가됨!")
#             st.rerun()
#         else:
#             st.warning("티커를 입력하세요!")

if __name__ == "__main__":
    main()
