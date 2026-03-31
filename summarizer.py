"""
AI 摘要与翻译模块 — 使用 Kimi (Moonshot AI) API 对文章进行智能概括和翻译
Kimi API 与 OpenAI 格式完全兼容
支持并发处理，大幅提升批量摘要速度
"""

import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from config import KIMI_API_KEY, KIMI_MODEL, SUMMARY_MAX_LENGTH
from database import get_article, update_article_summary, update_article_content, list_articles_pending_summary

KIMI_BASE_URL = "https://api.moonshot.cn/v1"

# 并发线程数（Kimi 免费版限流较严格，3 个比较安全）
MAX_WORKERS = 3


def _get_client() -> OpenAI:
    """获取 Kimi 客户端（兼容 OpenAI SDK）"""
    if not KIMI_API_KEY:
        raise ValueError(
            "未设置 KIMI_API_KEY。\n"
            "请在项目根目录的 .env 文件中填入:\n"
            "KIMI_API_KEY=sk-your-key-here\n\n"
            "获取 Key: https://platform.moonshot.cn/console/api-keys"
        )
    return OpenAI(api_key=KIMI_API_KEY, base_url=KIMI_BASE_URL)


def _estimate_reading_time(text: str) -> int:
    """估算阅读时间（分钟）"""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    minutes = (chinese_chars / 400) + (english_words / 200)
    return max(1, round(minutes))


def _strip_html(text: str) -> str:
    """去除 HTML 标签"""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


# 摘要细致程度配置
LEVEL_CONFIG = {
    "concise": {
        "label": "简洁",
        "zh_instruction": "用1句话概括核心结论（25字以内）",
        "en_instruction": "1 sentence summary (under 20 words)",
        "max_tokens": 300,
        "text_limit": 2000,
    },
    "standard": {
        "label": "标准",
        "zh_instruction": "用2-3句话概括主要内容和关键信息",
        "en_instruction": "2-3 sentence summary covering main points",
        "max_tokens": 500,
        "text_limit": 3000,
    },
    "detailed": {
        "label": "详细",
        "zh_instruction": "用4-6句话详细概括：包括背景、主要论点、关键数据/事实、结论及影响",
        "en_instruction": "4-6 sentence detailed summary: include background, key arguments, data/facts, conclusions and implications",
        "max_tokens": 900,
        "text_limit": 6000,
    },
}


def _try_refetch_fulltext(article: dict) -> str:
    """
    若数据库中存储的正文偏短（< 500 字），在摘要前重新尝试抓取原文全文。
    成功则更新数据库并返回新全文，否则返回原文本。
    """
    from fetcher import fetch_full_text, _is_known_paywall_domain
    link = article.get("link", "")
    existing = _strip_html(article.get("content") or article.get("summary") or "")
    if not link or len(existing) >= 500:
        return existing  # 已经够长，不重复抓取

    print(f"  [摘要前补抓] {article['title'][:50]} ...")
    full_text = fetch_full_text(link)
    if full_text and len(full_text) > len(existing):
        is_paywalled = 1 if len(full_text) < 150 else 0
        update_article_content(article["id"], full_text, is_paywalled=is_paywalled)
        print(f"  ✓ 补抓成功 ({len(full_text)} 字)")
        return full_text
    else:
        print(f"  ✗ 补抓未获更多内容，使用已有文本 ({len(existing)} 字)")
        return existing


def summarize_article(article_id: int, level: str = "standard") -> dict:
    """
    对单篇文章进行 AI 摘要 + 翻译。
    若数据库中正文偏短，会先重新抓取原文全文再送给 AI。
    level: "concise" | "standard" | "detailed"
    返回 { ai_summary, ai_summary_zh, reading_time, keywords }
    """
    article = get_article(article_id)
    if not article:
        raise ValueError(f"文章 {article_id} 不存在")

    # 若内容偏短，在摘要前先尝试补抓原文
    text = _try_refetch_fulltext(article)

    if not text or len(text) < 20:
        result = {
            "ai_summary": text or article.get("title", ""),
            "ai_summary_zh": text or article.get("title", ""),
            "reading_time": 1,
            "keywords": "",
        }
        update_article_summary(article_id, **result)
        return result

    reading_time = _estimate_reading_time(text)

    # 根据细致程度调整截取长度和提示词
    cfg = LEVEL_CONFIG.get(level, LEVEL_CONFIG["standard"])
    if len(text) > cfg["text_limit"]:
        text = text[:cfg["text_limit"]]

    client = _get_client()
    title = article.get('title', '')

    prompt = (
        f"摘要以下文章，返回JSON。\n"
        f"标题：{title}\n"
        f"正文：{text}\n\n"
        f"要求：\n"
        f"- 中文摘要：{cfg['zh_instruction']}\n"
        f"- English summary: {cfg['en_instruction']}\n\n"
        f"JSON格式（只返回JSON，不要其他文字）：\n"
        f'{{"t":"标题中文翻译(若已是中文则原样返回)","s":"中文摘要","e":"English summary","k":"关键词1,关键词2,关键词3"}}'
    )

    response = client.chat.completions.create(
        model=KIMI_MODEL,
        messages=[
            {"role": "system", "content": "你是摘要助手。只返回JSON，不要markdown代码块。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=cfg["max_tokens"],
    )

    reply = response.choices[0].message.content.strip()

    # 尝试从 markdown 代码块中提取 JSON
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', reply, re.DOTALL)
    if json_match:
        reply = json_match.group(1)

    try:
        data = json.loads(reply)
    except json.JSONDecodeError:
        data = {"s": reply[:SUMMARY_MAX_LENGTH], "e": "", "k": ""}

    result = {
        "ai_summary": (data.get("e") or data.get("ai_summary") or "")[:500],
        "ai_summary_zh": (data.get("s") or data.get("ai_summary_zh") or "")[:500],
        "title_zh": (data.get("t") or "")[:200],
        "reading_time": reading_time,
        "keywords": (data.get("k") or data.get("keywords") or ""),
    }

    update_article_summary(article_id, **result)
    return result


def _summarize_one(article: dict, level: str = "standard") -> dict:
    """用于线程池的单篇处理函数"""
    try:
        r = summarize_article(article["id"], level=level)
        print(f"  ✓ [{article['id']}] {article['title'][:40]}")
        return {
            "article_id": article["id"],
            "title": article["title"],
            "status": "success",
            "ai_summary_zh": r["ai_summary_zh"][:80] + "...",
        }
    except Exception as e:
        print(f"  ✗ [{article['id']}] {article['title'][:40]}: {e}")
        return {
            "article_id": article["id"],
            "title": article["title"],
            "status": "error",
            "error": str(e),
        }


def summarize_batch(limit: int = 10, level: str = "standard") -> list[dict]:
    """
    批量摘要：并发处理，3 篇同时调用 AI，大幅提速。
    level: "concise" | "standard" | "detailed"
    """
    pending = list_articles_pending_summary(limit=limit)
    if not pending:
        return []

    print(f"  [批量摘要] 共 {len(pending)} 篇待处理，{MAX_WORKERS} 线程并发（细致度: {level}）...")
    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(_summarize_one, a, level): a for a in pending}
        for future in as_completed(futures):
            results.append(future.result())

    return results
