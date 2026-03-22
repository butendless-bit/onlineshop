"""
HiMart Scheduler — APScheduler 기반 자동 크롤링
매일 오전 8시 실행, 실패 시 30분 후 최대 3회 재시도
"""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from config import CRAWL_HOUR, LOG_PATH
import os

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
log = logging.getLogger(__name__)

_scheduler = BackgroundScheduler(timezone="Asia/Seoul")
_retry_count = 0
MAX_RETRY = 3


def _crawl_job():
    global _retry_count
    _retry_count = 0
    _run_with_retry()


def _run_with_retry():
    global _retry_count
    from crawler import run_crawler
    try:
        log.info(f"[스케줄러] 크롤링 시작 (시도 {_retry_count + 1}/{MAX_RETRY})")
        count = run_crawler()
        log.info(f"[스케줄러] 크롤링 완료 — {count}개 수집")
        _retry_count = 0
    except Exception as e:
        _retry_count += 1
        log.error(f"[스케줄러] 크롤링 실패: {e}")
        if _retry_count < MAX_RETRY:
            retry_at = datetime.now() + timedelta(minutes=30)
            log.info(f"[스케줄러] 30분 후 재시도 예정: {retry_at.strftime('%H:%M')}")
            _scheduler.add_job(
                _run_with_retry,
                trigger="date",
                run_date=retry_at,
                id=f"retry_{_retry_count}",
                replace_existing=True,
            )
        else:
            log.error(f"[스케줄러] 최대 재시도 횟수 초과. 다음 정기 실행까지 대기.")


def _subscription_crawl_job():
    from crawler import run_subscription_crawler
    try:
        log.info("[스케줄러] 구독상품 크롤링 시작")
        count = run_subscription_crawler()
        log.info(f"[스케줄러] 구독상품 크롤링 완료 — {count}개 신규")
    except Exception as e:
        log.error(f"[스케줄러] 구독상품 크롤링 실패: {e}")


def start_scheduler():
    if _scheduler.running:
        return
    _scheduler.add_job(
        _crawl_job,
        trigger=CronTrigger(hour=CRAWL_HOUR, minute=0, timezone="Asia/Seoul"),
        id="daily_crawl",
        replace_existing=True,
    )
    _scheduler.add_job(
        _subscription_crawl_job,
        trigger=CronTrigger(hour=8, minute=30, timezone="Asia/Seoul"),
        id="daily_sub_crawl",
        replace_existing=True,
    )
    _scheduler.start()
    log.info(f"[스케줄러] 시작 — 매일 {CRAWL_HOUR:02d}:00 가격크롤 / 08:30 구독크롤")


def get_next_run_time() -> str | None:
    if not _scheduler.running:
        return None
    job = _scheduler.get_job("daily_crawl")
    if job and job.next_run_time:
        return job.next_run_time.strftime("%Y-%m-%d %H:%M")
    return None


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown()
