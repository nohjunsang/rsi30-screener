"""
universe.py
S&P500(대형) + S&P400(중형) + S&P600(소형) 종목 및 GICS 섹터 정보 수집.

위키피디아가 User-Agent 없는 요청을 403으로 막기 때문에
requests로 먼저 받아온 뒤 pandas에 넘겨줌.
"""

import io

import pandas as pd
import requests

WIKI_URLS = {
    "sp500": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
    "sp400": "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
    "sp600": "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _fetch_table(url: str) -> pd.DataFrame:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text))

    # 위키피디아 페이지마다 테이블 순서/구성이 달라서 'Symbol' 컬럼이
    # 있는 첫 번째 테이블을 종목 리스트로 간주함
    for t in tables:
        if "Symbol" in t.columns:
            return t
    raise ValueError(f"'Symbol' 컬럼을 가진 테이블을 찾지 못함: {url}")


def get_universe(indices=("sp500", "sp400", "sp600")) -> pd.DataFrame:
    """
    반환: DataFrame[Symbol, Sector] (인덱스 간 중복 종목은 제거됨)
    """
    frames = []
    for idx in indices:
        table = _fetch_table(WIKI_URLS[idx])

        sector_col = None
        for candidate in ["GICS Sector", "GICS  Sector"]:
            if candidate in table.columns:
                sector_col = candidate
                break

        df = pd.DataFrame(
            {
                "Symbol": table["Symbol"].astype(str).str.replace(".", "-", regex=False).str.strip(),
                "Sector": table[sector_col] if sector_col else "Unknown",
            }
        )
        frames.append(df)

    universe = pd.concat(frames, ignore_index=True)
    universe = universe.drop_duplicates(subset="Symbol").reset_index(drop=True)
    return universe
