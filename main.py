"""
Information Digest MVP — FastAPI 主入口
提供 RSS 源管理和文章查看的 REST API
"""

import sys
import os

# 确保模块路径正确
sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, HttpUrl
from database import (
    init_db, migrate_db, add_feed, remove_feed, update_feed, list_feeds, get_feed,
    list_articles, get_article, mark_article_read, delete_article,
    get_user_profile, save_user_profile,
)
from fetcher import fetch_and_store, fetch_all_feeds
from summarizer import summarize_article, summarize_batch
from scheduler import start_scheduler, stop_scheduler, update_interval


# ────────────────────── Pydantic Models ──────────────────────

class FeedCreate(BaseModel):
    url: str
    title: str = ""
    category: str = ""
    group_name: str = ""

class FeedUpdate(BaseModel):
    url: str | None = None
    title: str | None = None
    category: str | None = None
    group_name: str | None = None

class FeedResponse(BaseModel):
    id: int
    title: str | None
    url: str
    category: str
    group_name: str
    created_at: str | None
    last_fetched_at: str | None

class SchedulerUpdate(BaseModel):
    interval_minutes: int = 60


# ────────────────────── App Lifespan ──────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
    init_db()
    migrate_db()  # 兼容旧数据库：自动添加新字段
    start_scheduler(interval_minutes=60)
    print("🚀 Information Digest MVP 已启动")
    yield
    # 关闭时清理
    stop_scheduler()


app = FastAPI(
    title="Information Digest MVP",
    description="RSS 抓取与管理 — 你的个人信息摘要助手",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ────────────────────── Feed 管理接口 ──────────────────────

@app.post("/feeds", summary="添加订阅源")
def api_add_feed(body: FeedCreate):
    """添加一个新的 RSS/Atom 订阅源"""
    try:
        result = add_feed(url=body.url, title=body.title, category=body.category, group_name=body.group_name)
        return {"message": "订阅源已添加", "feed": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"添加失败: {e}")


@app.get("/feeds", summary="列出所有订阅源")
def api_list_feeds():
    """获取当前所有 RSS 订阅源"""
    return list_feeds()


@app.put("/feeds/{feed_id}", summary="修改订阅源")
def api_update_feed(feed_id: int, body: FeedUpdate):
    """修改订阅源的名称、URL、分类等信息"""
    ok = update_feed(feed_id, url=body.url, title=body.title,
                     category=body.category, group_name=body.group_name)
    if not ok:
        raise HTTPException(status_code=404, detail="订阅源不存在")
    return {"message": "订阅源已更新", "feed": get_feed(feed_id)}


@app.delete("/feeds/{feed_id}", summary="删除订阅源")
def api_remove_feed(feed_id: int):
    """删除指定订阅源及其所有文章"""
    if remove_feed(feed_id):
        return {"message": f"订阅源 {feed_id} 已删除"}
    raise HTTPException(status_code=404, detail="订阅源不存在")


# ────────────────────── 抓取接口 ──────────────────────

@app.post("/feeds/{feed_id}/fetch", summary="立即抓取某个订阅源")
def api_fetch_feed(
    feed_id: int,
    auto_summarize: bool = Query(True, description="抓取后自动生成摘要"),
    level: str = Query("standard", description="摘要细致度: concise | standard | detailed"),
):
    """立即触发对指定订阅源的抓取，默认抓取后自动摘要"""
    feed = get_feed(feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="订阅源不存在")
    try:
        fetch_result = fetch_and_store(feed_id, feed["url"])
        summary_result = None
        if auto_summarize and fetch_result.get("new_articles", 0) > 0:
            summary_result = summarize_batch(limit=fetch_result["new_articles"], level=level)
        return {"message": "抓取完成", "result": fetch_result, "summary": summary_result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"抓取失败: {e}")


@app.post("/feeds/fetch-all-bg", summary="后台抓取所有订阅源（立即返回）")
async def api_fetch_all_bg(background_tasks: BackgroundTasks):
    """立即返回，在后台触发抓取，不阻塞请求"""
    feeds = list_feeds()
    if not feeds:
        return {"message": "没有订阅源"}
    background_tasks.add_task(fetch_all_feeds, feeds)
    return {"message": f"已在后台触发抓取 {len(feeds)} 个订阅源"}


@app.post("/feeds/fetch-all", summary="立即抓取所有订阅源")
def api_fetch_all(
    auto_summarize: bool = Query(True, description="抓取后自动生成摘要"),
    level: str = Query("standard", description="摘要细致度: concise | standard | detailed"),
):
    """立即触发对所有订阅源的批量抓取，默认抓取后自动摘要"""
    feeds = list_feeds()
    if not feeds:
        return {"message": "没有订阅源", "results": [], "errors": []}
    results = fetch_all_feeds(feeds)
    total_new = sum(r.get("new_articles", 0) for r in results if "new_articles" in r)
    errors = [r for r in results if "error" in r]
    summary_result = None
    if auto_summarize and total_new > 0:
        print(f"  [自动摘要] 共 {total_new} 篇新文章，开始摘要（细致度: {level}）...")
        summary_result = summarize_batch(limit=total_new, level=level)
    return {
        "message": f"完成抓取 {len(feeds)} 个订阅源，新增 {total_new} 篇",
        "results": results,
        "errors": errors,
        "summary": summary_result,
    }


# ────────────────────── 文章接口 ──────────────────────

@app.get("/articles", summary="获取文章列表")
def api_list_articles(
    feed_id: int | None = Query(None, description="按订阅源筛选"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取文章列表，支持按订阅源筛选和分页"""
    return list_articles(feed_id=feed_id, limit=limit, offset=offset)


@app.get("/articles/summary-stats", summary="查询摘要进度")
def api_summary_stats():
    """返回已摘要和未摘要的文章数量"""
    from database import list_articles_pending_summary
    all_articles = list_articles()
    pending = list_articles_pending_summary(limit=9999)
    total = len(all_articles)
    done = total - len(pending)
    return {"total": total, "done": done, "pending": len(pending)}


@app.post("/articles/summarize-batch", summary="批量生成 AI 摘要")
def api_summarize_batch(
    limit: int = Query(10, ge=1, le=50, description="本次最多处理几篇"),
    level: str = Query("standard", description="摘要细致度: concise | standard | detailed"),
):
    """找出尚未摘要的文章，批量生成 AI 摘要"""
    if level not in ("concise", "standard", "detailed"):
        level = "standard"
    try:
        results = summarize_batch(limit=limit, level=level)
        success = sum(1 for r in results if r["status"] == "success")
        return {
            "message": f"批量摘要完成：{success}/{len(results)} 篇成功",
            "results": results,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量摘要失败: {e}")


@app.get("/articles/{article_id}", summary="获取文章详情")
def api_get_article(article_id: int):
    """获取单篇文章的详细内容"""
    article = get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    mark_article_read(article_id)
    return article


@app.delete("/articles/{article_id}", summary="删除文章")
def api_delete_article(article_id: int):
    """软删除文章（标记为已删除，不再展示）"""
    delete_article(article_id)
    return {"message": f"文章 {article_id} 已删除"}


# ────────────────────── AI 摘要接口 ──────────────────────

@app.post("/articles/{article_id}/summarize", summary="对单篇文章生成 AI 摘要")
def api_summarize_article(
    article_id: int,
    level: str = Query("standard", description="摘要细致度: concise | standard | detailed"),
):
    """调用 OpenAI 对指定文章生成摘要和中文翻译"""
    if level not in ("concise", "standard", "detailed"):
        level = "standard"
    article = get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    try:
        result = summarize_article(article_id, level=level)
        return {"message": "摘要生成成功", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"摘要生成失败: {e}")


# ────────────────────── 每日整合报告 ──────────────────────

@app.get("/digest/html", summary="生成每日信息整合 HTML 报告")
def api_generate_digest_html(date: str = Query(None, description="日期，默认今天")):
    """AI 深度阅读所有文章，生成 HTML 整合报告（在浏览器中可打印为 PDF）"""
    try:
        from digest import generate_digest
        html, stats = generate_digest(date_str=date)
        return Response(content=html, media_type="text/html; charset=utf-8")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成报告失败: {e}")


@app.get("/digest/stats", summary="获取整合报告统计")
def api_digest_stats():
    """返回可用于整合报告的文章统计"""
    articles = list_articles(limit=200)
    summarized = [a for a in articles if a.get("ai_summary_zh") and a["ai_summary_zh"].strip()]
    total_reading_time = sum(a.get("reading_time", 0) for a in summarized)
    import math
    digest_time = max(2, math.ceil(len(summarized) * 0.4))
    return {
        "total_articles": len(summarized),
        "total_reading_time": total_reading_time,
        "digest_reading_time": digest_time,
        "time_saved": max(0, total_reading_time - digest_time),
    }


# ────────────────────── RSSHub 路由发现 ──────────────────────

@app.get("/rsshub/search", summary="搜索 RSSHub 路由")
def api_rsshub_search(q: str = Query("", description="搜索关键词（中英文均可）"), limit: int = Query(8)):
    """根据网站名称或关键词，返回匹配的 RSSHub RSS 路由"""
    from rsshub import search_routes, get_all_categories, ROUTES
    if not q:
        return {"routes": ROUTES[:12], "categories": get_all_categories()}
    results = search_routes(q, limit=limit)
    return {"routes": results, "query": q}


@app.get("/rsshub/categories", summary="获取 RSSHub 路由分类")
def api_rsshub_categories():
    """获取所有可用的 RSSHub 路由分类和对应路由"""
    from rsshub import get_all_categories, get_routes_by_category
    cats = get_all_categories()
    return {cat: get_routes_by_category(cat) for cat in cats}


@app.post("/rsshub/build-url", summary="生成 RSSHub URL")
def api_rsshub_build(body: dict):
    """根据路径模板和参数生成完整的 RSSHub URL"""
    from rsshub import build_url
    path = body.get("path", "")
    params = body.get("params", {})
    if not path:
        raise HTTPException(status_code=400, detail="缺少 path 参数")
    url = build_url(path, params)
    return {"url": url}


# ────────────────────── 用户画像 & Bundle 推荐 ──────────────────────

class UserProfileBody(BaseModel):
    name: str = ""
    profession: str = ""
    interests: list[str] = []
    goals: list[str] = []
    custom_note: str = ""


@app.get("/profile", summary="获取用户画像")
def api_get_profile():
    """返回用户画像，不存在时返回 null"""
    profile = get_user_profile()
    return {"profile": profile}


@app.post("/profile", summary="保存用户画像")
def api_save_profile(body: UserProfileBody):
    """保存或更新用户画像"""
    import json as _json
    profile = save_user_profile(
        name=body.name,
        profession=body.profession,
        interests=_json.dumps(body.interests, ensure_ascii=False),
        goals=_json.dumps(body.goals, ensure_ascii=False),
        custom_note=body.custom_note,
    )
    return {"message": "用户画像已保存", "profile": profile}


@app.post("/profile/recommend", summary="AI 生成 RSS Bundle 推荐")
def api_recommend_bundle(body: UserProfileBody):
    """根据用户画像调用 AI，从订阅源库中挑选最合适的 RSS bundle"""
    try:
        from recommender import recommend_bundle
        result = recommend_bundle(
            name=body.name,
            profession=body.profession,
            interests=body.interests,
            goals=body.goals,
            custom_note=body.custom_note,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推荐生成失败: {e}")


# ────────────────────── 调度器接口 ──────────────────────

@app.put("/scheduler", summary="更新抓取频率")
def api_update_scheduler(body: SchedulerUpdate):
    """更新定时抓取的间隔时间（分钟）"""
    update_interval(body.interval_minutes)
    return {"message": f"抓取间隔已更新为 {body.interval_minutes} 分钟"}


# ────────────────────── 前端页面 ──────────────────────

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", summary="前端主页", include_in_schema=False)
def serve_frontend():
    """返回前端卡片式界面"""
    return FileResponse(str(STATIC_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
