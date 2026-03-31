#!/usr/bin/env python3
"""
快速演示脚本 — 不需要启动 API 服务器，直接在命令行体验核心功能
用法:  python demo.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from database import init_db, add_feed, list_feeds, list_articles
from fetcher import fetch_and_store

# 一些优质的中英文 RSS 源示例
SAMPLE_FEEDS = [
    ("https://hnrss.org/frontpage", "Hacker News", "科技"),
    ("https://feeds.arstechnica.com/arstechnica/index", "Ars Technica", "科技"),
    ("https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "NYT Technology", "科技"),
    ("http://www.36kr.com/feed", "36氪", "创业"),
]


def main():
    print("=" * 60)
    print("  📰 Information Digest MVP — 快速演示")
    print("=" * 60)

    # 1. 初始化数据库
    print("\n[1/3] 初始化数据库...")
    init_db()
    print("  ✓ 数据库就绪\n")

    # 2. 添加示例 RSS 源
    print("[2/3] 添加示例订阅源...")
    for url, title, cat in SAMPLE_FEEDS:
        try:
            result = add_feed(url=url, title=title, category=cat)
            print(f"  ✓ 已添加: {title} ({url})")
        except Exception as e:
            print(f"  - 跳过（可能已存在）: {title}")

    feeds = list_feeds()
    print(f"\n  当前共 {len(feeds)} 个订阅源\n")

    # 3. 抓取内容
    print("[3/3] 开始抓取 RSS 内容...")
    for feed in feeds:
        try:
            result = fetch_and_store(feed["id"], feed["url"])
            print(f"  ✓ {result['feed_title']}: 发现 {result['total_entries']} 篇，新增 {result['new_articles']} 篇")
        except Exception as e:
            print(f"  ✗ {feed['url']}: {e}")

    # 4. 展示结果
    print("\n" + "=" * 60)
    print("  抓取结果预览（最新 10 篇文章）")
    print("=" * 60)

    articles = list_articles(limit=10)
    for i, a in enumerate(articles, 1):
        print(f"\n  [{i}] {a['title']}")
        print(f"      来源: Feed#{a['feed_id']} | 发布时间: {a['published']}")
        if a["summary"]:
            summary = a["summary"][:100].replace("\n", " ")
            print(f"      摘要: {summary}...")
        if a["link"]:
            print(f"      链接: {a['link']}")

    print("\n" + "=" * 60)
    print("  ✅ 演示完成！")
    print()
    print("  接下来你可以:")
    print("  • 启动 API 服务器:  python main.py")
    print("  • 访问 API 文档:    http://localhost:8000/docs")
    print("  • 查看所有接口:     http://localhost:8000/redoc")
    print("=" * 60)


if __name__ == "__main__":
    main()
