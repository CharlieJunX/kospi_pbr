# 코스피 PBR 일일 갱신

GitHub Actions가 한국시간 월~금요일 20시에 실행됩니다. pykrx로 코스피 지수(1001)의 당일 PBR을 읽어 [코스피 PBR 대시보드](https://kospi-pbr-observatory.postray.chatgpt.site)에 한 건만 추가합니다. GitHub 혼잡 시 시작 시간이 늦어질 수 있습니다.

## 설정

저장소의 **Settings → Secrets and variables → Actions → New repository secret**에서 아래 항목을 등록합니다.

| 이름 | 값 |
| --- | --- |
| `KRX_ID` | KRX 정보데이터시스템 회원 아이디 |
| `KRX_PW` | KRX 정보데이터시스템 회원 비밀번호 |
| `SITES_SERVICE_TOKEN` | 해당 대시보드의 Sites 서비스 액세스 토큰 |
| `TELEGRAM_BOT_TOKEN` | 완료 알림을 보낼 Telegram 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 완료 메시지를 받을 Telegram 채팅 ID |

## 첫 실행 확인

1. **Actions → KOSPI PBR daily → Run workflow**에서 `verify_date`에 `2026-11-19`를 입력하면 KRX 조회만 실행합니다. 이 날짜의 대시보드 저장값은 1.27배입니다.
2. `verify_date`를 비워 수동 실행하면 한국시간 당일 데이터만 Sites에 반영합니다. 주말이나 당일 값이 없으면 건너뜁니다. 같은 날짜와 값의 재실행은 중복을 만들지 않습니다.
3. 수동 실행 로그에 `added` 또는 `already_present`가 표시되면 대시보드의 기준일과 PBR을 확인합니다.

공식 조회 화면은 [KRX 지수 PER/PBR/배당수익률](https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201010107)입니다.

## Telegram 완료 알림

Sites에 새 거래일이 저장되면 `KOSPI PBR 작업 완료` 메시지와 기준일을 보냅니다.
알림 작업만 실패했으면 GitHub Actions의 **Re-run failed jobs**로 저장 단계를 다시 실행하지 않고 알림을 재시도합니다.
