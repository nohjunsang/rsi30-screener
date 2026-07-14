"""
formatting.py
알림 메시지 포맷팅 (일봉/4시간봉 공통). Telegram HTML 파스모드를 사용해서
종목명은 굵게, 신호 종류마다 구분되는 이모지를 붙여 가독성을 높임.

같은 스캔에서 한 종목에 여러 신호가 동시에 뜨면:
  1) RSI/SMA 신호가 하필 "구름대 안(inside)"에서 발생했으면, 따로따로
     나열하지 않고 "☁️ 구름대 안에서 OO 발생" 식으로 묶어서 표시
     (가독성을 위해 - 일목구름대 자체 터치/돌파 알림과는 별개)
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
    "RSI 과매수 진입": "🔴",
    "RSI 과매수 회복": "🔄",
    "SMA120 터치": "📏",
    "SMA200 터치": "📏",
    "일목구름대 상단 터치": "☁️⬆️",
    "일목구름대 하단 터치": "☁️⬇️",
    "일목구름대 상방 돌파": "🚀",
    "일목구름대 하방 돌파": "💥",
    "RSI 강세 다이버전스": "💎",
    "RSI 약세 다이버전스": "⚠️",
}

# 이 신호들은 "구름대 안에서 발생"으로 묶일 수 있는 대상
# (일목구름대 상단/하단 터치 자체는 이미 구름 얘기라 여기 포함 안 함)
CLOUD_CONTEXT_TYPES = {
    "RSI 과매도 진입",
    "RSI 과매도 회복",
    "RSI 과매수 진입",
    "RSI 과매수 회복",
    "SMA120 터치",
    "SMA200 터치",
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

    lines = [f"<b>{html.escape(title)}</b>", ""]

    for ticker in order:
        ticker_alerts = grouped[ticker]
        first = ticker_alerts[0]
        change_pct = first["change_pct"]
        change_str = f"{change_pct:+.2f}%" if change_pct is not None else "N/A"
        change_emoji = _change_emoji(change_pct)
        cap_str = f"${first['market_cap_B']}B" if first.get("market_cap_B") else "N/A"

        lines.append(
            f"<b>{html.escape(ticker)}</b>  ${first['close']}  {change_emoji}{change_str}  ·  시총 {cap_str}"
        )

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

        if len(ticker_alerts) > 0:
            active = ticker_alerts[0].get("active_signals") or []
            if len(active) > 1:
                parts = [f"{s['label']}({'신규' if s['is_new'] else '기존'})" for s in active]
                lines.append(f"  ⚡ <b>동시 발생(겹침)</b>: {' + '.join(parts)}")

            cross_signals = ticker_alerts[0].get("cross_timeframe_signals") or []
            cross_label = ticker_alerts[0].get("cross_timeframe_label") or ""
            if cross_signals:
                lines.append(
                    f"  ⭐ <b>[{cross_label}에서도 동시 확인]</b> {', '.join(cross_signals)} - 고신뢰 신호"
                )

        lines.append("")

    if footer:
        lines.append(html.escape(footer))

    return "\n".join(lines).rstrip()
