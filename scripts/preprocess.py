"""
원본 CSV 2개를 날짜별 한 줄짜리 데이터로 합치는 전처리 스크립트.

입력
  data/raw/air_2025.csv      서울 열린데이터광장 '일별 평균 대기오염도' (cp949)
  data/raw/weather_2025.csv  기상청 ASOS 서울(108) 일자료 (cp949)

출력
  data/seoul_air_2025.csv    date,value,pm10,temp_avg,temp_min,temp_max,rain,wind,humidity,memo (utf-8)

실행
  pip install pandas
  python scripts/preprocess.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "seoul_air_2025.csv"


def load_air(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="cp949")
    df = df.rename(columns={
        "측정일시": "date",
        "측정소명": "station",
        "미세먼지농도(㎍/㎥)": "pm10",
        "초미세먼지농도(㎍/㎥)": "pm25",
    })
    # 측정소 50곳 중 자치구 대표 측정소 25곳만 사용 (이름이 '구'로 끝남).
    # 도로변 측정소(강남대로 등)는 차량 배출 영향으로 값이 높게 나와 서울 평균을 왜곡함.
    df = df[df["station"].str.endswith("구")]
    assert df["station"].nunique() == 25, df["station"].unique()

    df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d").dt.strftime("%Y-%m-%d")
    # 결측치는 mean()에서 자동으로 제외됨
    daily = df.groupby("date")[["pm25", "pm10"]].mean().round(1).reset_index()
    return daily


def load_weather(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="cp949")
    df = df.rename(columns={
        "일시": "date",
        "평균기온(°C)": "temp_avg",
        "최저기온(°C)": "temp_min",
        "최고기온(°C)": "temp_max",
        "일강수량(mm)": "rain",
        "평균 풍속(m/s)": "wind",
        "평균 상대습도(%)": "humidity",
    })
    df = df[["date", "temp_avg", "temp_min", "temp_max", "rain", "wind", "humidity"]].copy()
    # 기상청 일강수량이 빈칸이면 '비가 오지 않은 날' -> 0
    df["rain"] = df["rain"].fillna(0)
    return df


def main() -> None:
    air = load_air(RAW / "air_2025.csv")
    weather = load_weather(RAW / "weather_2025.csv")

    merged = air.merge(weather, on="date", how="inner")
    merged = merged.rename(columns={"pm25": "value"})  # 주 지표 = 초미세먼지(PM2.5)
    merged["memo"] = ""
    merged = merged[["date", "value", "pm10", "temp_avg", "temp_min", "temp_max",
                     "rain", "wind", "humidity", "memo"]]

    missing = merged.isna().sum()
    if missing.any():
        print("결측치가 남아 있어요:\n", missing[missing > 0])

    merged.to_csv(OUT, index=False, encoding="utf-8")
    print(f"저장 완료: {OUT} ({len(merged)}행, {merged['date'].min()} ~ {merged['date'].max()})")


if __name__ == "__main__":
    main()
