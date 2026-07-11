# 다중신호 미국주식 스크리너

시가총액 1000억 달러 이상 S&P500 종목 + 섹터별 시총 상위 10 + 레버리지 ETF
관심종목을 대상으로 아래 신호들을 **일봉과 4시간봉 둘 다** 종합 감시하는 도구.

- **RSI(14) 과매도 진입 / 회복**
- **SMA(120), SMA(200) 터치**
- **일목균형표 구름대 상단/하단 터치**

세 가지 신호는 각각 독립적으로 조건 충족 시 알림이 오고, 같은 종목에서
여러 신호가 동시에 뜨면:
- RSI/SMA 신호가 마침 **구름대 안(inside)**에서 발생했으면 "☁️ 구름대 안에서
  OO 발생" 식으로 묶어서 표시
- 그 외에도 2개 이상 신호가 겹치면 마지막 줄에 **"⚡ 동시 발생(겹침)"** 으로
  어떤 신호끼리 겹쳤는지 요약

> **자동화는 GitHub Actions를 기본으로 씁니다.** PC가 꺼져있거나 잠자기
> 상태여도 알림이 오도록 하려면 `GITHUB_SETUP.md`부터 진행하세요.
> Windows 작업 스케줄러(`register_task.ps1` 등)는 로컬 테스트/보조용으로만
> 남겨뒀습니다.

## 폴더 구조

```
rsi30_screener/
├── main.py                     # 장마감 후 확정 리포트 (일봉 기준 전체 신호)
├── intraday_monitor.py          # 장중 4시간봉 전체신호 조기경보 (30분 간격)
├── refresh_cache.py              # 유니버스+시총+섹터top10 캐시 갱신 (하루 1회)
├── universe.py                    # S&P500 + GICS 섹터 수집
├── engine.py                       # 일봉/4시간봉 공용 스캔 엔진 (신호계산+전이감지)
├── alerts.py                        # 일봉 스캔 (engine.py 얇은 래퍼)
├── h4_alerts.py                      # 4시간봉 스캔 (engine.py 얇은 래퍼)
├── signals.py                         # RSI/SMA터치/일목균형표 원시값 계산 (타임프레임 공용)
├── formatting.py                       # 알림 메시지 포맷 (겹침/구름대안 컨텍스트)
├── indicators.py                        # 지표 계산 (RSI, SMA터치, 일목균형표, 4h 리샘플)
├── state.py                              # 신호별 상태추적(중복방지+회복감지) 저장소
├── history.py                             # 알림 히스토리 기록
├── data.py                                 # 캐시 로딩, 가격 데이터 다운로드
├── config.py                                # 전체 설정값
├── notifier.py                                # Telegram 알림 전송
├── requirements.txt                            # 필요 패키지
├── .github/workflows/                          # GitHub Actions 자동화
│   ├── refresh_cache.yml                        # 캐시 갱신 (하루 1회)
│   ├── eod_report.yml                            # 장마감 확정 리포트 (하루 1회)
│   └── intraday_monitor.yml                       # 장중 조기경보 (30분 간격)
├── run_screener.bat / register_task.ps1            # (로컬/Windows 보조용)
├── run_intraday.bat / register_intraday_task.ps1      # (로컬/Windows 보조용)
├── GITHUB_SETUP.md                                    # GitHub Actions 설정 가이드
└── TELEGRAM_SETUP.md                                   # Telegram 봇 설정 가이드
```

## 최초 1회 필수: 캐시 생성

`alerts.py`/`h4_alerts.py`는 `universe_cache.json`(시총/섹터 정보)이 있어야
동작함. 로컬 테스트든 GitHub Actions든 **가장 먼저 한 번은 꼭 실행**:

```powershell
python refresh_cache.py
```

(S&P500 전체 종목의 시총을 조회하기 때문에 몇 분 정도 걸림)

GitHub Actions에서는 `refresh_cache.yml`이 매일 자동으로 갱신해주지만,
저장소를 처음 만든 직후에는 **Actions 탭에서 "Refresh Universe Cache"를
수동으로 한 번 실행(Run workflow)** 해서 `universe_cache.json`을 먼저
만들어둬야 EOD/장중 스크리너가 정상 동작함.

## 신호 종류 및 조건

| 신호 | 조건 | 실행 주기 |
|---|---|---|
| RSI 과매도 진입/회복 | RSI(14) ≤ 30 진입 / 30 초과 회복 | 일봉(장마감 후 1일 1회, 확정치) + 4시간봉(장중 30분 간격, 잠정치) |
| RSI 과매수 진입/회복 | RSI(14) ≥ 70 진입 / 70 미만 회복 | 일봉 + 4시간봉 둘 다 |
| SMA120/200 터치 | 종가가 이동평균선 ±1% 이내 근접 | 일봉 + 4시간봉 둘 다 (4h는 "120/200개의 4시간봉" 기준) |
| 일목균형표 구름대 터치 | 종가가 구름 상단/하단 ±1% 이내 근접 | 일봉 + 4시간봉 둘 다 |
| 일목균형표 구름대 상방/하방 돌파 | 가격이 구름 위(above)/아래(below)로 새로 진입 (방향 명시) | 일봉 + 4시간봉 둘 다 |

같은 신호가 계속 유지되는 동안은 알림이 반복되지 않고, **상태가 실제로
바뀌는 순간(전이)에만** 알림이 옴 (예: RSI가 30 밑에 열흘 머물러도
알림은 진입 시점 1번만, 다시 30 위로 올라올 때 회복 알림 1번).

> **최초 실행 시 주의**: 상태 기록이 없는 첫 실행에서는, 현재 조건을
> 이미 만족하고 있는 모든 종목이 "신규 신호"로 한꺼번에 잡혀서 알림이
> 평소보다 많이 올 수 있음 (정상적인 초기화 동작).

## 겹침 / 구름대 안 컨텍스트 표시

- RSI 또는 SMA 신호가 하필 **일목구름대 "안(inside)"**에서 발생했으면
  `☁️ 구름대 안에서 RSI 과매도 진입 + SMA120 터치 발생` 처럼 한 줄로 묶어서 표시
  (구름 상단/하단 자체 터치/돌파 알림과는 별개 개념 - "터치"가 아니라 "구름
  안에 들어와 있는 상태에서 다른 신호가 났다"는 뜻)
- **겹침(동시 발생) 판정은 "오늘 새로 뜬 신호"끼리만 비교하지 않음.** 그
  종목이 지금 이 순간 동시에 활성 상태인 모든 신호(오늘 새로 뜬 것 +
  이미 며칠 전부터 지속되던 것 다 포함)를 맨 아래 한 줄로 요약하고, 각각
  `(신규)` / `(기존)` 로 구분해서 표시함. 예:
  `⚡ 동시 발생(겹침): RSI 과매도(기존) + SMA120 터치(신규)`
  → RSI는 며칠 전부터 과매도 상태였고, SMA120은 오늘 새로 터치했다는 뜻

## 유니버스 / 항상 포함 종목

- 기본 유니버스: **S&P500**
- `config.py`의 `MARKET_CAP_THRESHOLD`(기본 1000억$) 이상만 스캔 대상
- 아래는 시총 기준과 무관하게 **항상** 스캔 대상에 포함:
  - `EXTRA_WATCHLIST` (기본: SOXL, NAIL, TSLQ — 직접 추가/삭제 가능)
  - GICS 11개 섹터별 시가총액 상위 `SECTOR_TOP_N`(기본 10)개
    (S&P500 안에서의 섹터별 순위이며, 토스증권 앱의 "산업별 시총 순위"와
    완전히 같은 분류는 아니고 표준 GICS 섹터 분류를 대신 사용한 근사치임)

## 설정 변경 (`config.py`)

```python
MARKET_CAP_THRESHOLD = 100_000_000_000  # 시총 하한선
RSI_OVERBOUGHT_THRESHOLD = 70            # RSI 과매수 기준
EXTRA_WATCHLIST = ["SOXL", "NAIL", "TSLQ"]  # 항상 감시할 개별 종목
SECTOR_TOP_N = 10                        # 섹터별 상위 몇개까지 항상 포함할지
RSI_THRESHOLD = 30
SMA_TOUCH_PERIODS = [120, 200]
SMA_TOUCH_TOLERANCE_PCT = 1.0            # 터치 판정 허용 오차(%)
ICHIMOKU_TOUCH_TOLERANCE_PCT = 1.0
```

## 테스트 모드 (휴장일 등 실제 신호 없이도 강제로 알림 확인하고 싶을 때)

GitHub Actions Actions 탭에서 "EOD Signal Report" 또는 "Intraday 4H Signal
Monitor" 워크플로우 선택 → "Run workflow" 버튼 → **"테스트 모드"
체크박스 켜고 실행**하면 됨.

- 상태(중복방지) 완전히 무시하고, 지금 이 순간 조건을 충족하는 신호를
  전부 새 알림처럼 강제 전송함 (제목에 🧪 [테스트] 표시)
- 임시 상태로만 동작해서 **진짜 daily_state.json / h4_state.json에는
  전혀 영향 없음** (다음 정식 실행에 지장 없음), 히스토리에도 기록 안 됨
- 4H 쪽은 장 시간 체크도 건너뛰어서 휴장일에도 테스트 가능
- 로컬에서 직접 돌릴 땐 `python main.py --test` / `python intraday_monitor.py --test`

단, 이 모드도 "지금 실제로 조건을 만족하는 종목이 하나도 없으면" 빈
결과가 나올 수 있음 (신호 자체를 지어내는 게 아니라, 중복방지 필터만
꺼주는 거라서). 그럴 땐 그것대로 "지금은 조건 만족 종목이 없다"는
정상적인 결과임.

## 4시간봉 관련 참고

미국 주식 정규장은 하루 6.5시간(09:30~16:00 ET)이라 24시간 연속인
해외선물/코인처럼 딱 떨어지는 4시간봉이 나오지 않음. 이 도구는 장 시작
(09:30 ET)을 기준으로 4시간 단위로 끊어서(보통 하루 2개 봉: 09:30-13:30,
13:30-16:00) 계산함. SMA120/200, 일목균형표(9/26/52)도 일봉과 똑같은
"기간 숫자"를 4시간봉에 그대로 적용함 - 즉 4h의 SMA120은 "120개의
4시간봉"(약 20 거래일) 기준이라, 일봉 SMA120("120 거래일", 약 6개월)과
룩백 기간 자체가 다름 (더 짧은 호흡의 신호). 일봉보다 신호가 훨씬 자주
나오는 대신, 노이즈(가짜 신호)도 늘어난다는 점 감안 필요.

## 알림 히스토리 (`alert_history.json`)

모든 알림이 시간순으로 계속 쌓임 (티커, 신호종류, 당시 가격/RSI 등 기록).
나중에 "이 신호 이후 실제로 얼마나 움직였는지" 성과를 리뷰하고 싶으면
이 파일을 기반으로 분석 스크립트를 추가로 만들 수 있음 (필요하면 요청).

## Telegram 알림 설정

`TELEGRAM_SETUP.md` 참고.

## GitHub Actions 자동화

`GITHUB_SETUP.md` 참고. 요약:
1. `refresh_cache.yml` — 하루 1회, 캐시 갱신
2. `eod_report.yml` — 장마감 후, 일봉 기준 확정 신호 리포트 (RSI+SMA+일목 종합)
3. `intraday_monitor.yml` — 장중 30분 간격, 4시간봉 기준 조기경보 (RSI+SMA+일목 종합)

## 로컬(Windows)에서 수동 실행/테스트

```powershell
python -m pip install -r requirements.txt
python refresh_cache.py      # 최초 1회 필수
python main.py                # 일봉 기준 확정 리포트
python intraday_monitor.py     # 장중일 때만 4시간봉 조기경보
```
