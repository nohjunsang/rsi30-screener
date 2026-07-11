# GitHub Actions로 자동화하기

PC가 꺼져있거나 잠자기 상태여도 알림이 오도록, GitHub 서버에서 대신 실행해주는 방식.

## 0) 준비물

- GitHub 계정 (없으면 https://github.com 에서 가입, 무료)
- Git 설치 여부 확인:
  ```powershell
  git --version
  ```
  버전이 안 나오면 https://git-scm.com/download/win 에서 설치 (설치 중 옵션은 기본값 그대로 다음 눌러도 됨)

## 1) GitHub에 새 저장소(repository) 만들기

1. https://github.com/new 접속
2. Repository name: 원하는 이름 (예: `rsi30-screener`)
3. **Public**으로 설정 (Actions 실행 시간이 완전 무료로 무제한. Private으로 하면 월 사용량 제한 있음)
4. README, .gitignore, license 체크박스는 전부 **체크 해제**한 상태로 "Create repository" 클릭
5. 생성되면 나오는 저장소 주소 복사해두기 (예: `https://github.com/내계정/rsi30-screener.git`)

## 2) 로컬 코드를 GitHub에 올리기

이 폴더(`rsi30_screener`)에서 PowerShell 열고 순서대로 한 줄씩:

```powershell
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/내계정/rsi30-screener.git
git push -u origin main
```

(`내계정/rsi30-screener.git` 부분은 1)번에서 복사한 실제 주소로 바꿔서 입력)

처음 push할 때 GitHub 로그인 창이 뜨면 로그인해서 인증 완료.

> **주의**: `config.py`의 토큰 값은 빈 문자열(`""`)로 되어있는 상태 그대로 올리는 게 맞음.
> 실제 토큰은 아래 3)번처럼 GitHub의 "Secrets" 기능으로 별도 등록하고, 코드에는 절대 직접 안 적음.

## 3) Telegram 토큰/chat_id를 GitHub Secrets로 등록

1. 방금 만든 저장소 페이지에서 **Settings** 탭 클릭
2. 왼쪽 메뉴에서 **Secrets and variables → Actions** 클릭
3. **New repository secret** 클릭해서 아래 2개 각각 등록:
   - Name: `TELEGRAM_BOT_TOKEN` / Value: (BotFather한테 받은 토큰)
   - Name: `TELEGRAM_CHAT_ID` / Value: (아까 확인한 chat_id 숫자)

## 4) 정상 등록됐는지 확인 + 최초 캐시 생성 (★ 중요, 처음 한 번은 꼭)

1. 저장소 페이지에서 **Actions** 탭 클릭
2. 왼쪽에 아래 3개 워크플로우가 보이면 정상:
   - **Refresh Universe Cache**
   - **EOD Signal Report**
   - **Intraday 4H RSI Monitor**
3. **먼저 "Refresh Universe Cache"부터 수동 실행**해야 함 (오른쪽 "Run workflow" 버튼)
   - 이 단계가 S&P500+400+600 전체 종목의 시총/섹터 정보를 모아서
     `universe_cache.json`을 만드는 과정이라, 다른 두 워크플로우가 이
     캐시 없이는 스캔할 종목이 하나도 없어서 사실상 아무 일도 안 함
   - 몇 분 정도 걸릴 수 있음 (수백~1500개 가까운 종목 조회)
4. 캐시 생성이 초록 체크(성공)로 끝나면, 나머지 두 워크플로우도 각각
   "Run workflow"로 수동 테스트 (실행 후 초록 체크면 성공, 빨간 X면 클릭해서 로그 확인)

## 5) 이제부터 자동으로 되는 것

- **Refresh Universe Cache**: 하루 1회, 장 열리기 전에 유니버스/시총/섹터 캐시 갱신
- **EOD Signal Report**: 평일 미국 장마감 후, 일봉 기준 확정 신호(RSI 과매도/회복,
  SMA120/200 터치, 일목구름대 터치) 종합 리포트 Telegram 전송
- **Intraday 4H RSI Monitor**: 평일 장중 30분 간격, 4시간봉 RSI 과매도/회복 조기경보
- 준상님 PC 상태(켜짐/꺼짐/잠자기)와 완전히 무관하게 작동

## 6) 기존 Windows 작업 스케줄러

이미 삭제하셨다면 이 단계는 넘어가도 됨. 혹시 다시 등록해서 쓰고 계셨다면,
GitHub Actions랑 중복으로 알림이 두 번 오는 걸 방지하기 위해 삭제 권장:

```powershell
schtasks /delete /tn RSI30Screener /f
schtasks /delete /tn RSI30IntradayMonitor /f
```


## 참고: 알아두면 좋은 점

- GitHub는 저장소에 **60일 동안 커밋(변경사항)이 없으면 스케줄 워크플로우를 자동으로 비활성화**함.
  장중 모니터링은 매번 상태파일을 커밋하니 이 문제는 자연히 해결되지만, 혹시 오랫동안 알림이
  안 오면 Actions 탭에서 워크플로우가 "비활성화"로 표시되어있는지 한 번씩 확인해볼 것.
- 예약된 시각(cron)에 GitHub 서버가 바쁘면 실제 실행이 몇 분 정도 늦어질 수 있음 (정상적인 현상).
- 코드/설정을 수정하고 싶으면, 로컬에서 파일 고친 뒤 아래처럼 다시 올리면 반영됨:
  ```powershell
  git add .
  git commit -m "설정 변경"
  git push
  ```
