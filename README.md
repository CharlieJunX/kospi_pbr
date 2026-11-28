# 코스피 PBR 조회, 게시 및 Telegram 알림

로컬 PC에서 pykrx로 코스피 지수(1001)의 PBR을 조회합니다. `--publish`로 [코스피 PBR 관측소](https://kospi-pbr-observatory.postray.chatgpt.site/)에 게시할 수 있습니다. `--notify`를 사용하면 기준일과 PBR을 Telegram으로 보냅니다.

## 설정

```powershell
python -m pip install -r requirements.txt
```

`kospi_pbr_daily.py`와 같은 폴더의 `.env`에 다음 값을 설정합니다.

```dotenv
KRX_ID=your_krx_id
KRX_PW=your_krx_password
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
SITES_SERVICE_TOKEN=your_sites_service_token
SITES_PUBLISH_TOKEN=your_sites_publish_token
```

조회만 할 때는 KRX 값 두 개만 있으면 됩니다. 게시에는 Sites 서비스 토큰과 관측소의 게시 전용 토큰이 필요합니다. 실행 환경에 설정된 값은 `.env`보다 우선합니다.

## 실행

`--date`를 생략하면 한국시간 기준 전날의 PBR을 조회합니다.

```powershell
# 전날 PBR 조회 및 게시
python kospi_pbr_daily.py --publish

# 특정 거래일의 PBR 조회 및 게시
python kospi_pbr_daily.py --date 2026-11-24 --publish

# 전날 PBR 조회, 게시 및 알림
python kospi_pbr_daily.py --publish --notify

# 전날 PBR 조회 및 알림
python kospi_pbr_daily.py --notify

# 특정 거래일의 PBR 조회 및 알림
python kospi_pbr_daily.py --date 2026-11-23 --notify

# 특정 거래일의 PBR 조회만 실행
python kospi_pbr_daily.py --date 2026-11-23
```

주말이거나 해당 날짜에 유효한 PBR이 없으면 건너뜁니다. 같은 날짜에 `--notify`를 다시 실행하면 알림을 다시 보냅니다. 게시할 거래일과 값이 이미 저장되어 있으면 `already_present`가 표시됩니다.

조회 값은 [KRX 지수 PER/PBR/배당수익률](https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201010107)에서 확인할 수 있습니다.

## GitHub Actions

저장소에 푸시할 때와 한국시간 매시 00분, 15분, 30분, 45분에 `python kospi_pbr_daily.py --publish --notify`를 실행합니다. 대상은 한국시간 기준 전날이며, 유효한 PBR이 있으면 실행할 때마다 Telegram 알림을 보냅니다. 예약 실행은 GitHub 기본 브랜치에서 이루어집니다. 수동으로 실행하려면 **Actions → KOSPI PBR daily → Run workflow**를 엽니다.

저장소의 **Settings → Secrets and variables → Actions**에 `KRX_ID`, `KRX_PW`, `SITES_SERVICE_TOKEN`, `SITES_PUBLISH_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`를 Repository secrets로 등록합니다.
