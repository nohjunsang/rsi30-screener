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

## 4) 정상 등록됐는지 확인

1. 저장소 페이지에서 **Actions** 탭 클릭
2. 왼쪽에 "EOD RSI Report", "Intraday RSI Monitor" 두 워크플로우가 보이면 정상
3. 아무거나 클릭 → 오른쪽 **Run workflow** 버튼 눌러서 수동 실행 테스트 가능
   (실행 후 초록 체크 표시 뜨면 성공, 빨간 X면 클릭해서 로그 확인)

## 5) 이제부터 자동으로 되는 것

- **Intraday RSI Monitor**: 평일 미국 장중에 15분마다 자동 실행, 조건 통과 종목 있으면 Telegram 알림
- **EOD RSI Report**: 평일 미국 장마감 후 자동 실행, 그날 확정 리포트 Telegram 전송
- 준상님 PC 상태(켜짐/꺼짐/잠자기)와 완전히 무관하게 작동

## 6) 기존 Windows 작업 스케줄러는 삭제 권장

GitHub Actions랑 Windows 작업 스케줄러가 동시에 돌면 **알림이 중복으로 두 번** 올 수 있으니, PowerShell에서 삭제:

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
