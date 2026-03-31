"""
调度模块 — 定时抓取 RSS 源
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from database import list_feeds
from fetcher import fetch_all_feeds

scheduler = BackgroundScheduler()
_job_id = "rss_fetch_all"


def _run_fetch():
    """调度器回调：抓取所有 feed"""
    feeds = list_feeds()
    if not feeds:
        print("[调度] 没有订阅源，跳过")
        return
    print(f"[调度] 开始抓取 {len(feeds)} 个订阅源...")
    fetch_all_feeds(feeds)
    print("[调度] 抓取完成")


def start_scheduler(interval_minutes: int = 60):
    """启动定时抓取，默认每 60 分钟一次"""
    if scheduler.get_job(_job_id):
        scheduler.remove_job(_job_id)

    scheduler.add_job(
        _run_fetch,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id=_job_id,
        name="RSS 定时抓取",
        replace_existing=True,
    )

    if not scheduler.running:
        scheduler.start()

    print(f"[调度] 已启动，每 {interval_minutes} 分钟抓取一次")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("[调度] 已停止")


def update_interval(interval_minutes: int):
    """更新抓取间隔"""
    start_scheduler(interval_minutes)
