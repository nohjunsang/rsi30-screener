"""
healthcheck.py
로컬 코드 전체가 정상 상태인지 한 번에 점검하는 스크립트.
(이중폴더 문제, 파일 손상, import 불일치 등을 한 방에 잡아줌)

사용법:
  python healthcheck.py
"""

import ast
import importlib
import os
import sys

REQUIRED_FILES = [
    "config.py", "indicators.py", "universe.py", "data.py", "signals.py",
    "state.py", "history.py", "notifier.py", "engine.py", "alerts.py",
    "h4_alerts.py", "formatting.py", "main.py", "intraday_monitor.py",
    "refresh_cache.py", "backtest.py", "premarket_digest.py", "kr_open_digest.py",
]

REQUIRED_SYMBOLS = {
    "config.py": ["MARKET_CAP_THRESHOLD", "RSI_THRESHOLD", "RSI_OVERBOUGHT_THRESHOLD", "H4_LOOKBACK_PERIOD"],
    "data.py": ["get_scan_universe", "download_daily_data", "download_hourly_data", "extract_ticker_df"],
    "engine.py": ["scan", "scan_current_snapshot"],
    "formatting.py": ["format_alerts"],
}

ok = True


def fail(msg):
    global ok
    ok = False
    print(f"  ❌ {msg}")


def check_nested_folder():
    print("[1/4] 이중폴더 확인")
    if os.path.isdir("rsi30_screener"):
        fail("현재 폴더 안에 'rsi30_screener' 하위폴더가 또 있음! (이중폴더 문제)")
    else:
        print("  ✅ 이중폴더 없음")


def check_files_exist():
    print("[2/4] 필수 파일 존재 확인")
    missing = [f for f in REQUIRED_FILES if not os.path.exists(f)]
    if missing:
        fail(f"누락된 파일: {', '.join(missing)}")
    else:
        print(f"  ✅ {len(REQUIRED_FILES)}개 파일 전부 존재")


def check_syntax():
    print("[3/4] 문법 검사")
    errors = []
    for f in REQUIRED_FILES:
        if not os.path.exists(f):
            continue
        try:
            ast.parse(open(f, encoding="utf-8").read())
        except SyntaxError as e:
            errors.append(f"{f}: {e}")
    if errors:
        for e in errors:
            fail(e)
    else:
        print("  ✅ 문법 오류 없음")


def check_symbols():
    print("[4/4] 필수 함수/상수 존재 확인")
    problems = []
    for fname, symbols in REQUIRED_SYMBOLS.items():
        if not os.path.exists(fname):
            continue
        content = open(fname, encoding="utf-8").read()
        for sym in symbols:
            if sym not in content:
                problems.append(f"{fname}에 '{sym}' 없음")
    if problems:
        for p in problems:
            fail(p)
    else:
        print("  ✅ 필수 함수/상수 전부 있음")


def check_imports():
    print("[+] 실제 import 테스트")
    sys.path.insert(0, os.getcwd())
    mods = [f[:-3] for f in REQUIRED_FILES if os.path.exists(f)]
    problems = []
    for m in mods:
        try:
            importlib.import_module(m)
        except Exception as e:
            problems.append(f"{m}: {type(e).__name__}: {e}")
    if problems:
        for p in problems:
            fail(p)
    else:
        print(f"  ✅ {len(mods)}개 모듈 전부 정상 import")


if __name__ == "__main__":
    check_nested_folder()
    check_files_exist()
    check_syntax()
    check_symbols()
    check_imports()

    print()
    if ok:
        print("🎉 전체 점검 통과 - 코드 상태 정상")
    else:
        print("⚠️ 위에 나온 문제들을 해결해야 함")
        sys.exit(1)
