"""Send a completion message after a new KOSPI PBR date has been saved."""

import argparse
from datetime import date
from http.client import HTTPException, HTTPSConnection
import json
import os
import re
import sys


def send_completion(updated_date, bot_token, chat_id):
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", bot_token):
        raise ValueError("TELEGRAM_BOT_TOKEN 형식이 올바르지 않습니다.")

    payload = json.dumps({
        "chat_id": chat_id,
        "text": f"KOSPI PBR 작업 완료\n기준일 {updated_date.isoformat()}",
    }).encode("utf-8")

    connection = HTTPSConnection("api.telegram.org", timeout=15)
    try:
        connection.request(
            "POST", f"/bot{bot_token}/sendMessage", body=payload,
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError(f"Telegram 전송 실패 (HTTP {response.status})")
        result = json.loads(response.read())
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise ValueError("Telegram에서 전송 성공을 확인하지 못했습니다.")
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description="새 PBR 반영 완료 알림")
    parser.add_argument("updated_date", type=date.fromisoformat)
    args = parser.parse_args()

    keys = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
    bot_token, chat_id = (os.environ.get(key, "").strip() for key in keys)
    if not bot_token or not chat_id:
        print("Telegram 알림에 필요한 GitHub Secrets를 확인하세요. " + ", ".join(keys), file=sys.stderr)
        return 1

    try:
        send_completion(args.updated_date, bot_token, chat_id)
    except (OSError, HTTPException, json.JSONDecodeError, UnicodeError) as exc:
        print(f"Telegram 전송 결과를 확인하지 못했습니다 ({type(exc).__name__}).", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"{args.updated_date} Telegram 알림 전송 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
