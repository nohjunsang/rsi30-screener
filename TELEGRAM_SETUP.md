# Telegram 알림 설정하기

스크리닝 결과를 Telegram으로 자동 전송받기 위한 설정 방법.

## 1) 봇 만들기 (토큰 발급)

1. Telegram 앱에서 `@BotFather` 검색 후 대화 시작
2. `/newbot` 입력
3. 봇 이름 입력 (아무거나, 예: `내RSI스크리너`)
4. 봇 username 입력 (끝에 `bot`으로 끝나야 함, 예: `junsang_rsi_bot`)
5. 완료되면 아래처럼 토큰이 나옴 — 이 값을 복사해둘 것

```
123456789:AAExampleTokenStringHere1234567
```

## 2) 채팅 ID(chat_id) 확인하기

1. 방금 만든 봇을 Telegram에서 검색해서 대화 시작 (아무 메시지나 하나 보내기, 예: `hi`)
2. 브라우저에서 아래 주소 접속 (`<TOKEN>`을 1)에서 받은 토큰으로 교체)

```
https://api.telegram.org/bot<TOKEN>/getUpdates
```

3. 응답 JSON에서 아래 형태로 `chat_id` 확인

```json
"chat": { "id": 987654321, "first_name": "준상", ... }
```

이 `id` 값 (예: `987654321`)이 chat_id.

> 만약 응답이 비어있으면(`"result":[]`), 봇한테 메시지를 아직 안 보낸 것. 1번부터 다시 확인.

## 3) config.py에 값 채우기

`config.py` 열어서 아래 두 줄 수정:

```python
TELEGRAM_BOT_TOKEN = "123456789:AAExampleTokenStringHere1234567"
TELEGRAM_CHAT_ID = "987654321"
```

## 4) 테스트

```powershell
python main.py
```

실행 끝나고 Telegram으로 결과 메시지가 오면 정상 설정된 것. (조건 충족 종목이 없어도 "종목 없음" 메시지가 오도록 되어 있어서, 스케줄러가 제대로 돌았는지 확인하는 용도로도 쓸 수 있음.)
