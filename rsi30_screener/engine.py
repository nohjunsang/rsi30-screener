"""
engine.py
일봉/4시간봉 공통 스캔 엔진.

종목별 OHLC 데이터로 신호(RSI 과매도/과매수 진입·회복, SMA120/200 터치,
일목구름대 상단/하단 터치, [옵션] 구름대 상방/하방 돌파)를 계산하고,
상태가 실제로 바뀐(전이) 것만 걸러서 알림 목록을 만듦.

겹침(동시발생) 판정: 오늘 "새로" 뜬 신호끼리만 비교하지 않고, 그 종목이
"지금 이 순간 동시에 활성 상태인" 모든 신호(신규 + 기존 지속중인 것 포함)를
스냅샷으로 같이 붙여줌 - 그래야 "RSI는 3일 전부터 과매도였고 오늘 SMA만
새로 터치"한 경우에도 겹침으로 표시할 수 있음.
"""

from signals import compute_signals
from state import StateStore
from data import get_market_cap_from_cache


def _market_cap_b(ticker):
    cap = get_market_cap_from_cache(ticker)
    return round(cap / 1e9, 1) if cap else None


def scan(
    tickers: list,
    get_df,
    state_filename: str,
    label: str = "",
    enable_cloud_breakout: bool = False,
) -> tuple:
    """
    tickers: 스캔 대상 티커 리스트
    get_df: 함수, ticker -> OHLC DataFrame (또는 None/빈 df)
    state_filename: 이 스캔 전용 상태파일 이름 (daily_state.json / h4_state.json)
    label: 로그 출력용 접두어 (예: "" 또는 "[4H] ")
    enable_cloud_breakout: True면 구름대 상방/하방 "돌파"(above/below 진입)도
        알림 대상에 포함. False면 터치(top/bottom)만 알림, above/below는
        컨텍스트로만 씀 (일봉은 기본 False, 4시간봉은 True로 사용)

    반환: (new_alerts: list[dict], state: StateStore)
    state는 호출한 쪽에서 save() 해줘야 파일/git에 반영됨.
    """
    state = StateStore(state_filename)

    if not tickers:
        print(f"{label}스캔 대상이 없습니다. refresh_cache.py를 먼저 실행했는지 확인하세요.")
        return [], state

    new_alerts = []

    for ticker in tickers:
        df = get_df(ticker)
        if df is None or df.empty:
            continue

        sig = compute_signals(df)
        if sig is None:
            continue

        cap_b = _market_cap_b(ticker)
        cloud_position = sig["ichimoku"]["position"] if sig["ichimoku"] else None

        ticker_alerts = []

        def _add(signal_type, detail):
            ticker_alerts.append(
                {
                    "ticker": ticker,
                    "signal_type": signal_type,
                    "detail": detail,
                    "close": sig["close"],
                    "change_pct": sig["change_pct"],
                    "market_cap_B": cap_b,
                    "cloud_position": cloud_position,
                }
            )

        # ---- RSI 과매도/과매수 진입 / 회복 (3-state 전이: normal/oversold/overbought) ----
        rsi_zone = sig["rsi_zone"]
        old_rsi_zone = state.get(ticker, "rsi_zone")
        rsi_new = state.check_transition(ticker, "rsi_zone", rsi_zone)
        rsi_alert_label = None
        if rsi_new:
            if rsi_zone == "oversold":
                rsi_alert_label = "RSI 과매도 진입"
            elif rsi_zone == "overbought":
                rsi_alert_label = "RSI 과매수 진입"
            elif rsi_zone == "normal":
                if old_rsi_zone == "oversold":
                    rsi_alert_label = "RSI 과매도 회복"
                elif old_rsi_zone == "overbought":
                    rsi_alert_label = "RSI 과매수 회복"
            if rsi_alert_label:
                _add(rsi_alert_label, f"RSI(14) {sig['rsi']}")

        # ---- SMA 터치 (진입 시에만 알림) ----
        sma_new_flags = {}
        for t in sig["sma_touches"]:
            if t["value"] is None:
                continue
            status = "touching" if t["touching"] else "normal"
            key = f"sma{t['period']}"
            changed = state.check_transition(ticker, key, status)
            sma_new_flags[t["period"]] = bool(changed and status == "touching")
            if changed and status == "touching":
                _add(
                    f"SMA{t['period']} 터치",
                    f"SMA{t['period']}={t['value']} (거리 {t['distance_pct']}%)",
                )

        # ---- 일목균형표: 터치(top/bottom) + [옵션] 돌파(above/below) ----
        # position 5단계(top/bottom/inside/above/below)를 하나의 state 키로
        # 추적해서, 상태가 바뀔 때마다 무엇으로 바뀌었는지에 따라 다르게 처리.
        ichimoku_new_kind = None
        if sig["ichimoku"]:
            position = sig["ichimoku"]["position"]
            cloud_top = sig["ichimoku"]["cloud_top"]
            cloud_bottom = sig["ichimoku"]["cloud_bottom"]
            changed = state.check_transition(ticker, "ichimoku_position", position)

            if changed:
                if position == "top":
                    ichimoku_new_kind = "일목구름대 상단 터치"
                    _add(ichimoku_new_kind, f"구름 상단={cloud_top} 하단={cloud_bottom}")
                elif position == "bottom":
                    ichimoku_new_kind = "일목구름대 하단 터치"
                    _add(ichimoku_new_kind, f"구름 상단={cloud_top} 하단={cloud_bottom}")
                elif position == "above" and enable_cloud_breakout:
                    ichimoku_new_kind = "일목구름대 상방 돌파"
                    _add(ichimoku_new_kind, f"구름 상단={cloud_top} 하단={cloud_bottom}")
                elif position == "below" and enable_cloud_breakout:
                    ichimoku_new_kind = "일목구름대 하방 돌파"
                    _add(ichimoku_new_kind, f"구름 상단={cloud_top} 하단={cloud_bottom}")

        if not ticker_alerts:
            continue

        # ---- 겹침(동시발생) 스냅샷: 신규+기존 다 포함해서 "지금 동시에 활성인" 신호 목록 ----
        active_signals = []
        zone_now = state.get(ticker, "rsi_zone")
        if zone_now == "oversold":
            active_signals.append(
                {"label": "RSI 과매도", "is_new": rsi_alert_label == "RSI 과매도 진입"}
            )
        elif zone_now == "overbought":
            active_signals.append(
                {"label": "RSI 과매수", "is_new": rsi_alert_label == "RSI 과매수 진입"}
            )
        for period in (120, 200):
            if state.get(ticker, f"sma{period}") == "touching":
                active_signals.append(
                    {"label": f"SMA{period} 터치", "is_new": sma_new_flags.get(period, False)}
                )
        pos_now = state.get(ticker, "ichimoku_position")
        if pos_now == "top":
            active_signals.append(
                {"label": "일목구름대 상단 터치", "is_new": ichimoku_new_kind == "일목구름대 상단 터치"}
            )
        elif pos_now == "bottom":
            active_signals.append(
                {"label": "일목구름대 하단 터치", "is_new": ichimoku_new_kind == "일목구름대 하단 터치"}
            )

        for a in ticker_alerts:
            a["active_signals"] = active_signals

        new_alerts.extend(ticker_alerts)

    return new_alerts, state
