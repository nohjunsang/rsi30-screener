"""
engine.py
일봉/4시간봉 공통 스캔 엔진.

종목별 OHLC 데이터로 신호(RSI 과매도/과매수 진입·회복, SMA120/200 터치,
일목구름대 상단/하단 터치, [옵션] 구름대 상방/하방 돌파, RSI 다이버전스)를
계산하고, 상태가 실제로 바뀐(전이) 것만 걸러서 알림 목록을 만듦.

추가 기능:
  - 거래량 급증: 독자 신호는 아니고, 다른 신호가 뜰 때 "거래량도 평소보다
    N배 터졌다"는 정보를 detail에 같이 붙여서 신호 신뢰도 판단에 참고하게 함.
  - 타임프레임 건너 컨플루언스: cross_state_filename을 넘기면, 그 반대
    타임프레임(일봉<->4H)에서도 지금 같은 종목이 활성 신호 상태인지 확인해서
    겹치면 "고신뢰" 태그를 붙임.

겹침(동시발생) 판정: 오늘 "새로" 뜬 신호끼리만 비교하지 않고, 그 종목이
"지금 이 순간 동시에 활성 상태인" 모든 신호(신규 + 기존 지속중인 것 포함)를
스냅샷으로 같이 붙여줌.
"""

from signals import compute_signals
from state import StateStore
from data import get_market_cap_from_cache


def _market_cap_b(ticker):
    cap = get_market_cap_from_cache(ticker)
    return round(cap / 1e9, 1) if cap else None


def _active_signal_labels(state: StateStore, ticker: str) -> list:
    """해당 상태저장소 기준, 이 종목이 '지금' 활성 상태인 신호 라벨 목록
    (컨플루언스/겹침 판정에 공용으로 씀)"""
    labels = []
    zone = state.get(ticker, "rsi_zone")
    if zone == "oversold":
        labels.append("RSI 과매도")
    elif zone == "overbought":
        labels.append("RSI 과매수")
    for period in (120, 200):
        if state.get(ticker, f"sma{period}") == "touching":
            labels.append(f"SMA{period} 터치")
    pos = state.get(ticker, "ichimoku_position")
    if pos == "top":
        labels.append("일목구름대 상단 터치")
    elif pos == "bottom":
        labels.append("일목구름대 하단 터치")
    div = state.get(ticker, "divergence")
    if div == "bullish":
        labels.append("RSI 강세 다이버전스")
    elif div == "bearish":
        labels.append("RSI 약세 다이버전스")
    return labels


def scan_current_snapshot(tickers: list, get_df, cross_state_filename: str = None, cross_label: str = "") -> list:
    """
    scan()과 달리 상태 전이(새로 생긴 것) 여부는 신경 안 쓰고,
    "지금 이 순간 조건을 만족하는 모든 종목"을 있는 그대로 전부 나열함.
    (장 시작 전 리마인더용 - 전날 밤 EOD 계산 결과를 기준으로 "지금 뭐가
    걸려있는지" 한 번 더 요약해서 보여주는 용도. 상태파일을 변경하거나
    저장하지 않음 - 읽기 전용)
    """
    cross_state = StateStore(cross_state_filename) if cross_state_filename else None
    results = []

    for ticker in tickers:
        df = get_df(ticker)
        if df is None or df.empty:
            continue

        sig = compute_signals(df)
        if sig is None:
            continue

        cap_b = _market_cap_b(ticker)
        cloud_position = sig["ichimoku"]["position"] if sig["ichimoku"] else None
        vol_tag = f" | 거래량 {sig['volume_ratio']}배" if sig.get("is_volume_spike") else ""

        ticker_signals = []

        def _add(signal_type, detail):
            ticker_signals.append(
                {
                    "ticker": ticker,
                    "signal_type": signal_type,
                    "detail": detail + vol_tag,
                    "close": sig["close"],
                    "change_pct": sig["change_pct"],
                    "market_cap_B": cap_b,
                    "cloud_position": cloud_position,
                    "volume_spike": sig.get("is_volume_spike", False),
                }
            )

        if sig["rsi_zone"] == "oversold":
            _add("RSI 과매도", f"RSI(14) {sig['rsi']}")
        elif sig["rsi_zone"] == "overbought":
            _add("RSI 과매수", f"RSI(14) {sig['rsi']}")

        for t in sig["sma_touches"]:
            if t["touching"]:
                _add(f"SMA{t['period']} 터치", f"SMA{t['period']}={t['value']} (거리 {t['distance_pct']}%)")

        if sig["ichimoku"]:
            pos = sig["ichimoku"]["position"]
            if pos in ("top", "bottom"):
                edge = "상단" if pos == "top" else "하단"
                cr = f"구름대 {sig['ichimoku']['cloud_bottom']}~{sig['ichimoku']['cloud_top']}"
                _add(f"일목구름대 {edge} 터치", cr)

        if sig.get("divergence_kind"):
            d = sig["divergence_detail"]
            if sig["divergence_kind"] == "bullish":
                _add(
                    "RSI 강세 다이버전스",
                    f"가격 {d['ref_price']}→{d['today_price']} (하락) / RSI {d['ref_rsi']}→{d['today_rsi']} (상승)",
                )
            else:
                _add(
                    "RSI 약세 다이버전스",
                    f"가격 {d['ref_price']}→{d['today_price']} (상승) / RSI {d['ref_rsi']}→{d['today_rsi']} (하락)",
                )

        if not ticker_signals:
            continue

        active_signals = [{"label": s["signal_type"], "is_new": True} for s in ticker_signals]
        cross_signals = _active_signal_labels(cross_state, ticker) if cross_state else []

        for s in ticker_signals:
            s["active_signals"] = active_signals
            s["cross_timeframe_signals"] = cross_signals
            s["cross_timeframe_label"] = cross_label

        results.extend(ticker_signals)

    return results


def scan(
    tickers: list,
    get_df,
    state_filename: str,
    label: str = "",
    enable_cloud_breakout: bool = False,
    cross_state_filename: str = None,
    cross_label: str = "",
) -> tuple:
    """
    tickers: 스캔 대상 티커 리스트
    get_df: 함수, ticker -> OHLC(+Volume) DataFrame (또는 None/빈 df)
    state_filename: 이 스캔 전용 상태파일 이름 (daily_state.json / h4_state.json)
    label: 로그 출력용 접두어 (예: "" 또는 "[4H] ")
    enable_cloud_breakout: True면 구름대 상방/하방 "돌파"(above/below 진입)도
        알림 대상에 포함
    cross_state_filename: 넘기면, 그 상태파일(반대 타임프레임) 기준으로도
        같은 종목이 활성 신호 상태인지 확인해서 컨플루언스 태그를 붙임
    cross_label: 컨플루언스 태그에 표시할 반대 타임프레임 이름 (예: "4H", "일봉")

    반환: (new_alerts: list[dict], state: StateStore)
    state는 호출한 쪽에서 save() 해줘야 파일/git에 반영됨.
    """
    state = StateStore(state_filename)
    cross_state = StateStore(cross_state_filename) if cross_state_filename else None

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
        vol_tag = f" | 거래량 {sig['volume_ratio']}배" if sig.get("is_volume_spike") else ""

        ticker_alerts = []

        def _add(signal_type, detail):
            ticker_alerts.append(
                {
                    "ticker": ticker,
                    "signal_type": signal_type,
                    "detail": detail + vol_tag,
                    "close": sig["close"],
                    "change_pct": sig["change_pct"],
                    "market_cap_B": cap_b,
                    "cloud_position": cloud_position,
                    "volume_spike": sig.get("is_volume_spike", False),
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
        ichimoku_new_kind = None
        if sig["ichimoku"]:
            position = sig["ichimoku"]["position"]
            cloud_top = sig["ichimoku"]["cloud_top"]
            cloud_bottom = sig["ichimoku"]["cloud_bottom"]
            cloud_range = f"구름대 {cloud_bottom}~{cloud_top}"
            changed = state.check_transition(ticker, "ichimoku_position", position)

            if changed:
                if position == "top":
                    ichimoku_new_kind = "일목구름대 상단 터치"
                    _add(ichimoku_new_kind, cloud_range)
                elif position == "bottom":
                    ichimoku_new_kind = "일목구름대 하단 터치"
                    _add(ichimoku_new_kind, cloud_range)
                elif position == "above" and enable_cloud_breakout:
                    ichimoku_new_kind = "일목구름대 상방 돌파"
                    _add(ichimoku_new_kind, cloud_range)
                elif position == "below" and enable_cloud_breakout:
                    ichimoku_new_kind = "일목구름대 하방 돌파"
                    _add(ichimoku_new_kind, cloud_range)

        # ---- RSI 다이버전스 (양방향 전이 감지: none <-> bullish/bearish) ----
        divergence_kind = sig.get("divergence_kind")
        divergence_status = divergence_kind if divergence_kind else "none"
        div_changed = state.check_transition(ticker, "divergence", divergence_status)
        if div_changed and divergence_kind:
            d = sig["divergence_detail"]
            if divergence_kind == "bullish":
                _add(
                    "RSI 강세 다이버전스",
                    f"가격 {d['ref_price']}→{d['today_price']} (하락) / RSI {d['ref_rsi']}→{d['today_rsi']} (상승)",
                )
            else:
                _add(
                    "RSI 약세 다이버전스",
                    f"가격 {d['ref_price']}→{d['today_price']} (상승) / RSI {d['ref_rsi']}→{d['today_rsi']} (하락)",
                )

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
        div_now = state.get(ticker, "divergence")
        if div_now == "bullish":
            active_signals.append({"label": "RSI 강세 다이버전스", "is_new": div_changed})
        elif div_now == "bearish":
            active_signals.append({"label": "RSI 약세 다이버전스", "is_new": div_changed})

        # ---- 타임프레임 건너 컨플루언스 ----
        cross_signals = _active_signal_labels(cross_state, ticker) if cross_state else []

        for a in ticker_alerts:
            a["active_signals"] = active_signals
            a["cross_timeframe_signals"] = cross_signals
            a["cross_timeframe_label"] = cross_label

        new_alerts.extend(ticker_alerts)

    return new_alerts, state
