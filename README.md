# RSI30 Market Cap Screener

시가총액 3,000억 달러 이상 미국 주식 중 일봉 RSI(14, Wilder's smoothing)가
30 이하로 마감한 종목을 스크리닝하는 도구.

> **자동화는 GitHub Actions를 기본으로 씁니다.** PC가 꺼져있거나 잠자기
> 상태여도 알림이 오도록 하려면 `GITHUB_SETUP.md`부터 진행하세요.
> Windows 작업 스케줄러(`register_task.ps1` 등)는 로컬 테스트/보조용으로만
> 남겨뒀습니다.

## 폴더 구조

```
rsi30_screener/
├── main.py                    # 장마감 후 확정 리포트 실행 진입점
├── intraday_monitor.py         # 장중 조기경보 모니터링 (15분 간격)
├── config.py                    # 임계값, Telegram 설정
├── data.py                      # 티커 목록 / 가격·시총 데이터 수집
├── indicators.py                 # RSI 계산 로직
├── screener.py                   # 스크리닝 핵심 로직
├── notifier.py                   # Telegram 알림 전송
├── state.py                      # 장중 중복 알림 방지 상태 저장
├── requirements.txt              # 필요 패키지
├── run_screener.bat              # (장마감용) 작업 스케줄러 실행 배치
├── run_intraday.bat               # (장중용) 작업 스케줄러 실행 배치
├── register_task.ps1              # 장마감 후 자동 실행 등록
├── register_intraday_task.ps1     # 장중 15분 간격 모니터링 등록
└── TELEGRAM_SETUP.md              # Telegram 봇 설정 가이드
```

## 두 가지 자동 실행 모드

| 모드 | 스크립트 | 실행 시점 | 성격 |
|---|---|---|---|
| 장마감 확정 리포트 | `main.py` | 미국 장마감 후 하루 1회 | RSI 확정치 (신뢰도 높음) |
| 장중 조기경보 | `intraday_monitor.py` | 장중 15분마다 | RSI 잠정치 (마감 전까지 변동 가능) |

둘 다 등록해서 같이 써도 되고, 하나만 써도 됨.

## 장중 모니터링 등록

```powershell
powershell -ExecutionPolicy Bypass -File .\register_intraday_task.ps1
```

- 스크립트가 `zoneinfo`로 뉴욕 시간을 직접 확인해서 장중 여부를 스스로 판단하기 때문에,
  서머타임(EDT/EST) 전환에도 별도 조정 없이 자동으로 맞음.
- 장중이 아니면 바로 종료되므로 24시간 등록해놔도 부담 없음.
- 같은 종목이 하루에 여러 번 알림 오지 않도록 `alerted_today.json`에 기록해서 중복 방지함
  (다음날 되면 자동 초기화).
- 체크 주기는 `register_intraday_task.ps1`의 `$intervalMinutes` 값으로 조절 (기본 15분).

## 장중 알림 관련 주의

장중 RSI는 "지금 이 순간 가격 기준 잠정치"라서, 장 마감 때까지 가격이 움직이면
RSI도 바뀔 수 있음. 실제로 "일봉이 RSI 30 이하로 마감했다"고 확정하려면
`main.py`(장마감 후 자동 실행)의 결과가 최종 기준.

## 사용법

```powershell
python -m pip install -r requirements.txt
python main.py
```

조건을 그때그때 바꿔서 1회성으로 실행하고 싶으면:
```powershell
python main.py --market-cap 200 --rsi 35
```
(시총 200B달러 이상, RSI 35 이하로 조건 변경. `config.py`는 안 건드림)

## 설정 변경 (기본값)

`config.py`에서 기본 조건 조절 가능:

- `MARKET_CAP_THRESHOLD` : 시가총액 하한선 (기본 3000억 달러)
- `RSI_THRESHOLD` : RSI 상한선 (기본 30)
- `RSI_PERIOD` : RSI 계산 기간 (기본 14일)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` : 채우면 결과 자동 전송

## Telegram 알림 설정

`TELEGRAM_SETUP.md` 참고 (봇 생성 → 토큰 발급 → chat_id 확인 → config.py 입력).

## 매일 자동 실행 (Windows 작업 스케줄러)

이 폴더에서 PowerShell 열고:
```powershell
.\register_task.ps1
```

미국 정규장 마감(16:00 ET) 후 한국시간 기준 새벽에 자동 실행되도록
매주 화~토요일 06:30(KST)에 등록됨 (서머타임 여부와 무관하게 안전 마진 포함).
자세한 시간대 계산은 `register_task.ps1` 상단 주석 참고.

수동으로 테스트하려면:
```powershell
schtasks /run /tn RSI30Screener
```

등록 취소:
```powershell
schtasks /delete /tn RSI30Screener /f
```

## 참고

- 유니버스는 S&P500 기준. 시총 3000억 달러 이상 기업은 거의 전부
  S&P500에 포함되어 있어 커버리지는 충분함.
- RSI는 Wilder's smoothing (EMA, alpha=1/14) 방식으로, 대부분 증권사
  차트와 동일한 계산법.
