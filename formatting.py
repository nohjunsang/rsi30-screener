"""
formatting.py
알림 메시지 포맷팅 (일봉/4시간봉 공통). Telegram HTML 파스모드를 사용해서
종목명은 굵게, 신호 종류마다 구분되는 이모지를 붙여 가독성을 높임.

종목 수가 많을 때 가독성이 떨어지는 걸 막기 위해, 신호를 두 그룹으로 나눔:
  - ⭐ 주목할 신호: RSI 관련(과매도/과매수/다이버전스), 여러 신호 겹침,
    타임프레임 컨플루언스, 거래량 급증, 구름대 안 컨텍스트 등 - 이런 건
    종목별로 자세히(현재가/등락율/상세수치까지) 보여줌
  - 나머지(일반) 신호: 단순 SMA 터치 하나, 단순 일목 터치/돌파 하나처럼
    부가 정보 없이 그 신호 하나만 뜬 경우 - 신호 종류별로 묶어서
    종목명만 나열 (자세한 수치는 생략, 스크롤 부담을 크게 줄임)

같은 종목에서 여러 신호가 동시에 뜨면(⭐ 주목할 신호 섹션 안에서):
  1) RSI/SMA 신호가 하필 "구름대 안(inside)"에서 발생했으면, 따로따로
     나열하지 않고 "☁️ 구름대 안에서 OO 발생" 식으로 묶어서 표시
  2) 그 종목에 "지금 이 순간 동시에 활성 상태인" 신호가 2개 이상이면
     (오늘 새로 뜬 것 + 이미 지속중이던 것 다 포함해서) 어떤 신호끼리
     겹쳤는지 마지막 줄에 요약, 각각 (신규)/(기존) 표시
  3) 반대 타임프레임(일봉<->4H)에서도 같은 종목이 활성 신호 상태면
     "⭐ [OO에서도 동시 확인]"으로 고신뢰 신호임을 표시
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
# (일목구름대 상단/하단 터치 자체는 이미 구름 얘기라 여기 포함 안 함)
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
# (SMA 터치, 일목 터치/돌파는 단독일 땐 흔해서 압축 대상, RSI/다이버전스는
#  이 스크리너의 핵심 관심사라 단독이어도 항상 자세히 보여줌)
ALWAYS_NOTABLE_TYPES = {
    "RSI 과매도 진입",
    "RSI 과매도 회복",
    "RSI 과매도",  # premarket_digest.py 등 스냅샷 모드에서 쓰는 라벨
    "RSI 과매수 진입",
    "RSI 과매수 회복",
    "RSI 과매수",  # 스냅샷 모드
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


def _format_ticker_block(ticker: str, ticker_alerts: list) -> list:
    """한 종목에 대한 상세 블록(현재가/등락율/신호별 상세)을 줄 단위 리스트로 반환"""
    first = ticker_alerts[0]
    change_pct = first["change_pct"]
    change_str = f"{change_pct:+.2f}%" if change_pct is not None else "N/A"
    change_emoji = _change_emoji(change_pct)
    cap_str = f"${first['market_cap_B']}B" if first.get("market_cap_B") else "N/A"

    lines = [
        f"<b>{html.escape(ticker)}</b>  ${first['close']}  {change_emoji}{change_str}  ·  시총 {cap_str}"
    ]

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

    notable_tickers = [t for t in order if _is_notable(grouped[t])]
    plain_tickers = [t for t in order if t not in notable_tickers]

    lines = [f"<b>{html.escape(title)}</b>", ""]
    lines.append(
        f"총 {len(order)}종목 신호 · ⭐ 주목 {len(notable_tickers)} · 일반 {len(plain_tickers)}"
    )
    lines.append("")

    if notable_tickers:
        lines.append("<b>━━━ ⭐ 주목할 신호 ━━━</b>")
        lines.append("")
        for ticker in notable_tickers:
            lines.extend(_format_ticker_block(ticker, grouped[ticker]))
            lines.append("")

    if plain_tickers:
        lines.append("<b>━━━ 나머지 신호 (단순, 압축표시) ━━━</b>")
        lines.append("")
        by_type = {}
        for t in plain_tickers:
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
