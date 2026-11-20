#!/usr/bin/env python3
"""Fetch one KRX KOSPI PBR observation using pykrx.

Install: python -m pip install "pykrx==1.2.9"
Set KRX_ID and KRX_PW in the execution environment.
Example: python kospi_pbr_daily.py --date 2026-11-19
Pass --publish to send today's verified result to the hosted dashboard.
"""

import argparse
from contextlib import redirect_stdout
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import os
import sys
from zoneinfo import ZoneInfo


KOSPI_TICKER = "1001"
SEOUL = ZoneInfo("Asia/Seoul")
SITES_ENDPOINT = "https://kospi-pbr-observatory.postray.chatgpt.site/api/pbr/observations"


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


def fetch_pbr(target_date):
    missing = [key for key in ("KRX_ID", "KRX_PW") if not os.environ.get(key)]
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
    import requests

    keys = ("SITES_SERVICE_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL", "ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    missing = [key for key in keys if not os.environ.get(key)]
    if missing:
        raise ValueError("게시 환경변수가 필요합니다. " + ", ".join(missing))

    oidc_response = requests.get(
        os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"],
        params={"audience": SITES_ENDPOINT},
        headers={"Authorization": "Bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]},
        timeout=15,
        allow_redirects=False,
    )
    if oidc_response.status_code != 200:
        raise ValueError(f"GitHub 실행 인증 실패 (HTTP {oidc_response.status_code})")
    oidc_token = oidc_response.json().get("value")
    if not isinstance(oidc_token, str) or not oidc_token:
        raise ValueError("GitHub 실행 인증 토큰이 응답에 없습니다.")

    response = requests.post(
        SITES_ENDPOINT,
        json=observation,
        headers={
            "OAI-Sites-Authorization": "Bearer " + os.environ["SITES_SERVICE_TOKEN"],
            "Authorization": "Bearer " + oidc_token,
        },
        timeout=30,
        allow_redirects=False,
    )
    if response.status_code not in (200, 201):
        raise ValueError(f"Sites 갱신 실패 (HTTP {response.status_code})")
    result = response.json()
    if result.get("status") not in ("added", "already_present") or result.get("date") != observation["date"]:
        raise ValueError("Sites 응답에서 갱신을 확인하지 못했습니다.")
    return result["status"]


def main():
    parser = argparse.ArgumentParser(description="한국시간 기준 코스피 PBR 하루치 조회")
    parser.add_argument("--date", type=date.fromisoformat, help="검증용 조회일 (YYYY-MM-DD)")
    parser.add_argument("--publish", action="store_true", help="당일 유효 PBR을 Sites에 반영")
    args = parser.parse_args()

    today = datetime.now(SEOUL).date()
    target = args.date or today
    if target > today:
        parser.error("미래 날짜는 조회할 수 없습니다.")
    if args.publish and target != today:
        parser.error("Sites에는 한국시간 기준 오늘 값만 게시할 수 있습니다.")
    if target.weekday() >= 5:
        print(f"{target} 주말 건너뜀", file=sys.stderr)
        return 0

    try:
        observation = fetch_pbr(target)
        if observation is None:
            print(f"{target} 당일 PBR 미확인. 갱신 건너뜀", file=sys.stderr)
            return 0
        if args.publish:
            status = publish_observation(observation)
            print(f"{target} Sites 갱신 결과 {status}")
        else:
            print(json.dumps(observation))
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
    except Exception as exc:
        print(f"조회 또는 데이터 처리 실패 ({type(exc).__name__})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
