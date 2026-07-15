"""
formatting.py
알림 메시지 포맷팅 (일봉/4시간봉 공통). Telegram HTML 파스모드를 사용해서
종목명은 굵게, 신호 종류마다 구분되는 이모지를 붙여 가독성을 높임.

메시지는 4개 섹션으로 구성됨 (위에서부터 우선순위 순):
  1) 🌟 고품질 자리: 추세(골든/데드크로스)와 신호 방향이 같고, 겹침/
     컨플루언스/거래량 같은 확인이 많이 붙은 종목 - 점수로 자동 판정
  2) ⚠️ 주의 필요: 추세를 거스르는 역방향 신호(예: 데드크로스 중 RSI
     과매도 - "떨어지는 칼날" 위험) - 마찬가지로 점수로 자동 판정
  3) ⭐ 주목할 신호: 위 둘로 분류 안 된 것 중, RSI/다이버전스/겹침/
     컨플루언스/거래량급증 등 부가정보 있는 신호 - 자세히 표시
  4) 나머지(일반) 신호: 단순 SMA/일목 터치 하나만 뜬 흔한 경우 -
     신호 종류별로 종목명만 압축해서 나열

품질 점수 계산 방식 (_compute_quality 참고):
  - 신호 방향(상승기대/하락기대)이 있는 신호가 하나라도 새로 떴을 때만 계산
  - 그 방향이 지금 추세(골든/데드크로스 상태)와 같은 방향이면 +2,
    반대(역행) 방향이면 -2
  - 같이 활성 상태인 신호가 많을수록(겹침) 최대 +3
  - 타임프레임 컨플루언스(일봉+4H 동시) +2
  - 거래량 급증 동반 +1
  - 점수 >= GOOD_THRESHOLD 면 고품질, <= BAD_THRESHOLD 면 주의
"""

import html

# 신호 종류별로 한눈에 구분되는 이모지 (없는 신호는 기본값 "•" 사용)
SIGNAL_EMOJI = {
    "RSI 과매도 진입": "🔵",
    "RSI 과매도 회복": "🔄",
    "RSI 과매도": "🔵",
    "RSI 과매수 진입": "🔴",
    "RSI 과매수 회복": "🔄",
    "RSI 과매수": "🔴",
    "SMA120 터치": "📏",
    "SMA200 터치": "📏",
    "일목구름대 상단 터치": "☁️⬆️",
    "일목구름대 하단 터치": "☁️⬇️",
    "일목구름대 상방 돌파": "🚀",
    "일목구름대 하방 돌파": "💥",
    "RSI 강세 다이버전스": "💎",
    "RSI 약세 다이버전스": "⚠️",
    "골든크로스 발생": "✨",
    "골든크로스 상태": "✨",
    "데드크로스 발생": "💀",
    "데드크로스 상태": "💀",
    "볼린저밴드 스퀴즈 진입": "🤏",
    "볼린저밴드 스퀴즈": "🤏",
    "볼린저밴드 스퀴즈 해제(상방)": "🎯",
    "볼린저밴드 스퀴즈 해제(하방)": "🎯",
}

# 이 신호들은 "구름대 안에서 발생"으로 묶일 수 있는 대상
CLOUD_CONTEXT_TYPES = {
    "RSI 과매도 진입",
    "RSI 과매도 회복",
    "RSI 과매도",
    "RSI 과매수 진입",
    "RSI 과매수 회복",
    "RSI 과매수",
    "SMA120 터치",
    "SMA200 터치",
}

# 이 신호들은 단독으로 떠도 항상 "주목할 신호"로 자세히 보여줌
ALWAYS_NOTABLE_TYPES = {
    "RSI 과매도 진입",
    "RSI 과매도 회복",
    "RSI 과매도",
    "RSI 과매수 진입",
    "RSI 과매수 회복",
    "RSI 과매수",
    "RSI 강세 다이버전스",
    "RSI 약세 다이버전스",
    "골든크로스 발생",
    "골든크로스 상태",
    "데드크로스 발생",
    "데드크로스 상태",
    "볼린저밴드 스퀴즈 진입",
    "볼린저밴드 스퀴즈",
    "볼린저밴드 스퀴즈 해제(상방)",
    "볼린저밴드 스퀴즈 해제(하방)",
}

# 신호별 방향성 (상승 기대 신호 / 하락 기대 신호). 여기 없는 신호(SMA/일목
# 터치, 스퀴즈 진입)는 그 자체로는 방향성이 없어서(중립) 점수 계산 대상에서
# 자동 제외됨.
SIGNAL_DIRECTION = {
    "RSI 과매도 진입": "bullish",
    "RSI 과매도 회복": "bullish",
    "RSI 강세 다이버전스": "bullish",
    "골든크로스 발생": "bullish",
    "볼린저밴드 스퀴즈 해제(상방)": "bullish",
    "RSI 과매수 진입": "bearish",
    "RSI 과매수 회복": "bearish",
    "RSI 약세 다이버전스": "bearish",
    "데드크로스 발생": "bearish",
    "볼린저밴드 스퀴즈 해제(하방)": "bearish",
}

GOOD_THRESHOLD = 3
BAD_THRESHOLD = -2


def _emoji(signal_type: str) -> str:
    return SIGNAL_EMOJI.get(signal_type, "•")


def _change_emoji(change_pct) -> str:
    if change_pct is None:
        return ""
    if change_pct > 0:
        return "🔺"
    if change_pct < 0:
        return "🔻"
    return "➖"


def _is_notable(ticker_alerts: list) -> bool:
    """이 종목의 신호들을 '자세히' 보여줄지, '압축된 목록'으로만 보여줄지 판단"""
    if len(ticker_alerts) > 1:
        return True
    a = ticker_alerts[0]
    if a["signal_type"] in ALWAYS_NOTABLE_TYPES:
        return True
    if a.get("cross_timeframe_signals"):
        return True
    if a.get("volume_spike"):
        return True
    if a.get("cloud_position") == "inside":
        return True
    return False


def _compute_quality(ticker_alerts: list):
    """
    이 종목에 '새로' 뜬 신호들을 보고 자리 품질 점수를 계산.
    방향성 있는 신호(SIGNAL_DIRECTION에 있는 것)가 하나도 없으면 채점 대상이
    아니라고 보고 (None, None, []) 반환함 (단순 터치만 뜬 경우는 채점 안 함).

    반환: (score:int|None, direction:"bullish"|"bearish"|None, reasons:list[str])
    """
    directions = [SIGNAL_DIRECTION.get(a["signal_type"]) for a in ticker_alerts]
    directions = [d for d in directions if d]
    if not directions:
        return None, None, []

    direction = "bullish" if directions.count("bullish") >= directions.count("bearish") else "bearish"

    active = ticker_alerts[0].get("active_signals") or []
    active_labels = {a["label"] for a in active}

    score = 0
    reasons = []

    trend_state = None
    if "골든크로스 상태" in active_labels:
        trend_state = "bullish"
    elif "데드크로스 상태" in active_labels:
        trend_state = "bearish"

    if trend_state == direction:
        trend_kr = "상승" if direction == "bullish" else "하락"
        score += 2
        reasons.append(f"{trend_kr}추세(골든/데드크로스)와 같은 방향")
    elif trend_state is not None and trend_state != direction:
        counter_kr = "하락" if direction == "bullish" else "상승"
        score -= 2
        reasons.append(f"{counter_kr}추세 중 역행 신호 (추세 거스름 - 주의)")

    overlap_count = len([a for a in active if a["label"] not in ("골든크로스 상태", "데드크로스 상태")])
    overlap_bonus = min(max(overlap_count - 1, 0), 3)
    if overlap_bonus > 0:
        score += overlap_bonus
        reasons.append(f"신호 {overlap_count}개 동시 겹침")

    if ticker_alerts[0].get("cross_timeframe_signals"):
        score += 2
        reasons.append("일봉+4H 동시 확인(컨플루언스)")

    if any(a.get("volume_spike") for a in ticker_alerts):
        score += 1
        reasons.append("거래량 급증 동반")

    return score, direction, reasons


def _format_ticker_block(ticker: str, ticker_alerts: list, quality=None) -> list:
    """한 종목에 대한 상세 블록을 줄 단위 리스트로 반환.
    quality를 넘기면 (score, direction, reasons) 요약 줄을 맨 위에 붙임."""
    first = ticker_alerts[0]
    change_pct = first["change_pct"]
    change_str = f"{change_pct:+.2f}%" if change_pct is not None else "N/A"
    change_emoji = _change_emoji(change_pct)
    cap_str = f"${first['market_cap_B']}B" if first.get("market_cap_B") else "N/A"

    lines = [
        f"<b>{html.escape(ticker)}</b>  ${first['close']}  {change_emoji}{change_str}  ·  시총 {cap_str}"
    ]

    if quality:
        score, direction, reasons = quality
        dir_kr = "매수 관점" if direction == "bullish" else "매도/청산 관점"
        sign = f"{score:+d}"
        lines.append(f"  <b>점수 {sign} · {dir_kr}</b> — {' / '.join(reasons)}")

    inside_cloud = any(a.get("cloud_position") == "inside" for a in ticker_alerts)
    combinable = [a for a in ticker_alerts if a["signal_type"] in CLOUD_CONTEXT_TYPES]
    others = [a for a in ticker_alerts if a["signal_type"] not in CLOUD_CONTEXT_TYPES]

    if inside_cloud and combinable:
        names = " + ".join(a["signal_type"] for a in combinable)
        details = " / ".join(a["detail"] for a in combinable)
        lines.append(f"  ☁️ 구름대 안에서 {html.escape(names)} 발생 ({html.escape(details)})")
    else:
        for a in combinable:
            lines.append(f"  {_emoji(a['signal_type'])} {a['signal_type']} — {html.escape(a['detail'])}")

    for a in others:
        lines.append(f"  {_emoji(a['signal_type'])} {a['signal_type']} — {html.escape(a['detail'])}")

    active = first.get("active_signals") or []
    if len(active) > 1:
        parts = [f"{s['label']}({'신규' if s['is_new'] else '기존'})" for s in active]
        lines.append(f"  ⚡ <b>동시 발생(겹침)</b>: {' + '.join(parts)}")

    cross_signals = first.get("cross_timeframe_signals") or []
    cross_label = first.get("cross_timeframe_label") or ""
    if cross_signals:
        lines.append(
            f"  ⭐ <b>[{cross_label}에서도 동시 확인]</b> {', '.join(cross_signals)} - 고신뢰 신호"
        )

    return lines


def format_alerts(alerts: list, title: str, footer: str = "") -> str:
    if not alerts:
        return title

    grouped = {}
    order = []
    for a in alerts:
        if a["ticker"] not in grouped:
            grouped[a["ticker"]] = []
            order.append(a["ticker"])
        grouped[a["ticker"]].append(a)

    good, bad, notable, plain = [], [], [], []
    quality_map = {}

    for t in order:
        ticker_alerts = grouped[t]
        score, direction, reasons = _compute_quality(ticker_alerts)
        if score is not None and score >= GOOD_THRESHOLD:
            good.append(t)
            quality_map[t] = (score, direction, reasons)
        elif score is not None and score <= BAD_THRESHOLD:
            bad.append(t)
            quality_map[t] = (score, direction, reasons)
        elif _is_notable(ticker_alerts):
            notable.append(t)
        else:
            plain.append(t)

    lines = [f"<b>{html.escape(title)}</b>", ""]
    lines.append(
        f"총 {len(order)}종목 · 🌟 고품질 {len(good)} · ⚠️ 주의 {len(bad)} · ⭐ 주목 {len(notable)} · 일반 {len(plain)}"
    )
    lines.append("")

    if good:
        lines.append("<b>━━━ 🌟 고품질 자리 (추세 정합 + 다중 확인) ━━━</b>")
        lines.append("")
        for ticker in sorted(good, key=lambda t: quality_map[t][0], reverse=True):
            lines.extend(_format_ticker_block(ticker, grouped[ticker], quality=quality_map[ticker]))
            lines.append("")

    if bad:
        lines.append("<b>━━━ ⚠️ 주의 필요 (추세 역행 신호) ━━━</b>")
        lines.append("")
        for ticker in sorted(bad, key=lambda t: quality_map[t][0]):
            lines.extend(_format_ticker_block(ticker, grouped[ticker], quality=quality_map[ticker]))
            lines.append("")

    if notable:
        lines.append("<b>━━━ ⭐ 주목할 신호 ━━━</b>")
        lines.append("")
        for ticker in notable:
            lines.extend(_format_ticker_block(ticker, grouped[ticker]))
            lines.append("")

    if plain:
        lines.append("<b>━━━ 나머지 신호 (단순, 압축표시) ━━━</b>")
        lines.append("")
        by_type = {}
        for t in plain:
            signal_type = grouped[t][0]["signal_type"]
            by_type.setdefault(signal_type, []).append(t)

        for signal_type, tickers in by_type.items():
            emoji = _emoji(signal_type)
            lines.append(f"{emoji} <b>{html.escape(signal_type)}</b> ({len(tickers)}개)")
            lines.append(", ".join(html.escape(t) for t in tickers))
            lines.append("")

    if footer:
        lines.append(html.escape(footer))

    return "\n".join(lines).rstrip()
