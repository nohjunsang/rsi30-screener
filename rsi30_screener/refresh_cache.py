"""
refresh_cache.py
하루 1회 실행: 유니버스(S&P500+400+600) + 개별 종목 시가총액 + 섹터별
시총 상위 N개 목록을 캐시 파일(universe_cache.json)에 저장.

이 캐시가 있어야 EOD/장중 스크리너가 매번 1000개 넘는 종목의
시가총액을 야후파이낸스에 새로 조회하지 않고 빠르게 필터링할 수 있음.
"""

import json
import time
from pathlib import Path

import yfinance as yf

from universe import get_universe
from config import UNIVERSE_INDICES, EXTRA_WATCHLIST, SECTOR_TOP_N

CACHE_FILE = Path(__file__).parent / "universe_cache.json"


def fetch_market_cap(ticker: str):
    try:
        info = yf.Ticker(ticker).fast_info
        return info.get("market_cap") or info.get("marketCap")
    except Exception:
        return None


def build_cache():
    universe = get_universe(UNIVERSE_INDICES)
    print(f"유니버스 크기: {len(universe)}개 종목 (섹터 정보 포함)")

    records = {}
    total = len(universe)
    for i, row in universe.iterrows():
        ticker = row["Symbol"]
        cap = fetch_market_cap(ticker)
        records[ticker] = {"sector": row["Sector"], "market_cap": cap}
        if i % 100 == 0:
            print(f"  진행: {i}/{total}")
        time.sleep(0.05)  # 레이트리밋 방지

    # 관심종목(레버리지 ETF 등)도 캐시에 포함
    # ETF는 일반적 의미의 "시가총액"이 없거나 fast_info로 못 가져올 수 있어서
    # None이어도 무방함 (always_include 목록에는 무조건 들어감)
    for ticker in EXTRA_WATCHLIST:
        if ticker not in records:
            records[ticker] = {"sector": "Watchlist", "market_cap": fetch_market_cap(ticker)}

    # 섹터별 시총 상위 N개 계산
    by_sector = {}
    for ticker, info in records.items():
        if info["market_cap"] is None:
            continue
        by_sector.setdefault(info["sector"], []).append((ticker, info["market_cap"]))

    sector_top = []
    for sector, lst in by_sector.items():
        lst.sort(key=lambda x: x[1], reverse=True)
        sector_top.extend([t for t, _ in lst[:SECTOR_TOP_N]])

    always_include = sorted(set(sector_top) | set(EXTRA_WATCHLIST))

    cache = {
        "universe": records,
        "always_include": always_include,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    }

    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"캐시 저장 완료: {CACHE_FILE.name} "
        f"(전체 {len(records)}종목, 섹터top{SECTOR_TOP_N}+관심종목 = {len(always_include)}개 항상포함)"
    )


if __name__ == "__main__":
    build_cache()
