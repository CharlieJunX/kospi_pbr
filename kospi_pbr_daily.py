#!/usr/bin/env python3
"""Fetch one KRX KOSPI PBR observation using pykrx.

Install: python -m pip install -r requirements.txt
Set KRX_ID and KRX_PW in .env beside this script or in the execution environment.
Example: python kospi_pbr_daily.py --date 2026-11-19
Pass --publish to save the result to the KOSPI PBR Observatory.
Pass --notify to send the PBR result to Telegram using TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.
"""

import argparse
from contextlib import redirect_stdout
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from http.client import HTTPException, HTTPSConnection
import json
import os
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

from dotenv import dotenv_values


KOSPI_TICKER = "1001"
SEOUL = ZoneInfo("Asia/Seoul")
SITES_HOST = "kospi-pbr-observatory.postray.chatgpt.site"
SITES_PATH = "/api/pbr/observations"


def extract_observation(frame, target_date):
    import pandas as pd

    if frame.empty:
        return None
    if list(frame.columns).count("PBR") != 1:
        raise ValueError("조회 결과의 PBR 열을 확인할 수 없습니다.")

    dates = pd.to_datetime(frame.index, errors="coerce").strftime("%Y-%m-%d")
    values = frame.loc[dates == target_date.isoformat(), "PBR"]
    if values.empty:
        return None
    if len(values) != 1:
        raise ValueError("같은 날짜의 PBR이 여러 건입니다.")

    try:
        pbr = Decimal(str(values.iloc[0]))
        if not pbr.is_finite() or pbr <= 0:
            return None
        pbr = pbr.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    if pbr <= 0:
        return None
    return {"date": target_date.isoformat(), "pbr": float(pbr)}


def load_dotenv_environment(keys):
    missing = [key for key in keys if not os.environ.get(key)]
    if not missing:
        return

    values = dotenv_values(
        Path(__file__).resolve().with_name(".env"),
        encoding="utf-8-sig",
        interpolate=False,
    )
    for key in missing:
        value = values.get(key)
        if value:
            os.environ[key] = value


def fetch_pbr(target_date):
    credential_keys = ("KRX_ID", "KRX_PW")
    load_dotenv_environment(credential_keys)
    missing = [key for key in credential_keys if not os.environ.get(key)]
    if missing:
        raise ValueError("환경변수가 필요합니다. " + ", ".join(missing))

    day = target_date.strftime("%Y%m%d")
    try:
        with redirect_stdout(sys.stderr):
            from pykrx import stock

            frame = stock.get_index_fundamental(day, day, KOSPI_TICKER)
    except ModuleNotFoundError as exc:
        if exc.name == "pykrx":
            raise ValueError('pykrx가 필요합니다. python -m pip install "pykrx==1.2.9"') from None
        raise
    return extract_observation(frame, target_date)


def publish_observation(observation):
    keys = ("SITES_SERVICE_TOKEN", "SITES_PUBLISH_TOKEN")
    load_dotenv_environment(keys)
    tokens = {key: os.environ.get(key, "").strip() for key in keys}
    missing = [key for key in keys if not tokens[key]]
    if missing:
        raise ValueError("Sites 게시에 필요한 .env 설정을 확인하세요. " + ", ".join(missing))
    if any(not re.fullmatch(r"[A-Za-z0-9._~-]+", token) for token in tokens.values()):
        raise ValueError("Sites 게시 토큰 형식이 올바르지 않습니다.")

    connection = HTTPSConnection(SITES_HOST, timeout=30)
    try:
        connection.request(
            "POST", SITES_PATH, body=json.dumps(observation).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "OAI-Sites-Authorization": "Bearer " + tokens["SITES_SERVICE_TOKEN"],
                "Authorization": "Bearer " + tokens["SITES_PUBLISH_TOKEN"],
            },
        )
        response = connection.getresponse()
        if response.status not in (200, 201):
            raise ValueError(f"Sites 게시 실패 (HTTP {response.status})")
        try:
            result = json.loads(response.read(8192))
        except (ValueError, UnicodeError):
            raise ValueError("Sites 응답에서 게시 결과를 확인하지 못했습니다.") from None
    except (OSError, HTTPException) as exc:
        raise ValueError(f"Sites 게시 결과를 확인하지 못했습니다 ({type(exc).__name__}).") from None
    finally:
        connection.close()

    if not isinstance(result, dict) or result.get("date") != observation["date"]:
        raise ValueError("Sites 응답에서 게시 결과를 확인하지 못했습니다.")
    status = result.get("status")
    if status not in ("added", "already_present"):
        raise ValueError("Sites 응답에서 게시 결과를 확인하지 못했습니다.")
    return status


def send_completion(observation, bot_token, chat_id):
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", bot_token):
        raise ValueError("TELEGRAM_BOT_TOKEN 형식이 올바르지 않습니다.")

    payload = json.dumps({
        "chat_id": chat_id,
        "text": (
            f"KOSPI PBR 조회 결과\n기준일 {observation['date']}\n"
            f"PBR {observation['pbr']:.2f}배"
        ),
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


def notify_completion(observation):
    try:
        keys = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
        load_dotenv_environment(keys)
        bot_token, chat_id = (os.environ.get(key, "").strip() for key in keys)
        if not bot_token or not chat_id:
            raise ValueError(
                "Telegram 알림에 필요한 .env 설정을 확인하세요. "
                + ", ".join(keys)
            )
        send_completion(observation, bot_token, chat_id)
    except (OSError, HTTPException, json.JSONDecodeError, UnicodeError) as exc:
        print(f"Telegram 전송 결과를 확인하지 못했습니다 ({type(exc).__name__}).", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"{observation['date']} Telegram 알림 전송 완료", file=sys.stderr)
    return 0


def main():
    parser = argparse.ArgumentParser(description="한국시간 기준 코스피 PBR 하루치 조회")
    parser.add_argument("--date", type=date.fromisoformat, help="조회일 (YYYY-MM-DD)")
    parser.add_argument("--publish", action="store_true", help="조회 결과를 Sites에 게시")
    parser.add_argument("--notify", action="store_true", help="조회 결과를 Telegram으로 전송")
    args = parser.parse_args()

    today = datetime.now(SEOUL).date()
    target = args.date or today
    if target > today:
        parser.error("미래 날짜는 조회할 수 없습니다.")
    if target.weekday() >= 5:
        print(f"{target} 주말 건너뜀", file=sys.stderr)
        return 0

    try:
        observation = fetch_pbr(target)
        if observation is None:
            print(f"{target} 유효한 PBR을 확인하지 못했습니다.", file=sys.stderr)
            return 0
        print(json.dumps(observation))
        if args.publish:
            status = publish_observation(observation)
            print(f"{target} Sites 게시 결과 {status}", file=sys.stderr)
        if args.notify:
            return notify_completion(observation)
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
    except Exception as exc:
        print(f"조회 또는 알림 처리 실패 ({type(exc).__name__})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
