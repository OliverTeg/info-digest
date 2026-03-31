"""
RSS 抓取模块 — 解析 RSS/Atom feed 并提取文章
支持从原文链接抓取完整正文内容
"""

import feedparser
import time
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from database import update_feed_title, update_last_fetched, save_articles

# 全文抓取最大并发
FETCH_CONTENT_WORKERS = 3


def parse_published(entry) -> str:
    """从 feedparser entry 中提取发布时间"""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6]).isoformat()
            except Exception:
                pass
    return datetime.utcnow().isoformat()


def extract_content(entry) -> str:
    """提取文章正文（优先 content，回退到 summary）"""
    if hasattr(entry, "content") and entry.content:
        return entry.content[0].get("value", "")
    return getattr(entry, "summary", "")


def fetch_full_text(url: str) -> str:
    """
    从文章原始链接抓取完整正文。
    优先使用 trafilatura，回退到 requests + 简单提取。
    """
    if not url:
        return ""
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False,
                                       include_tables=True, favor_precision=True)
            if text and len(text) > 100:
                return text
    except ImportError:
        pass
    except Exception as e:
        print(f"    [全文抓取] trafilatura 失败 ({url[:60]}): {e}")

    # 回退：用 requests + 简单正则
    try:
        import requests
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        resp.raise_for_status()
        html = resp.text
        # 去掉 script/style 标签
        html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # 提取 <p> 标签内容
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL | re.IGNORECASE)
        text = '\n'.join(re.sub(r'<[^>]+>', '', p).strip() for p in paragraphs if len(p.strip()) > 20)
        if len(text) > 100:
            return text
    except Exception as e:
        print(f"    [全文抓取] requests 失败 ({url[:60]}): {e}")

    return ""


# 已知需要付费订阅的域名（仅用于提示，不阻止抓取）
_KNOWN_PAYWALL_DOMAINS = {
    "wsj.com", "ft.com", "economist.com", "bloomberg.com",
    "newyorker.com", "nytimes.com", "theathletic.com",
    "businessinsider.com", "hbr.org", "technologyreview.com",
}

def _is_known_paywall_domain(url: str) -> bool:
    """判断 URL 是否属于已知付费墙域名"""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower().lstrip("www.")
        return any(host == d or host.endswith("." + d) for d in _KNOWN_PAYWALL_DOMAINS)
    except Exception:
        return False


def _fetch_article_fulltext(article: dict) -> dict:
    """
    为单篇文章抓取全文并返回更新后的 dict。
    若抓取后内容仍然很短，判定为疑似付费墙并标注 is_paywalled=True。
    """
    link = article.get("link", "")
    existing_content = article.get("content", "")
    clean_existing = re.sub(r'<[^>]+>', '', existing_content).strip()

    # 如果 RSS 内容太短（< 500 字），尝试从原文抓取
    if link and len(clean_existing) < 500:
        full_text = fetch_full_text(link)
        if full_text and len(full_text) > len(clean_existing):
            article["content"] = full_text
            clean_existing = full_text
            print(f"    ✓ 全文抓取成功: {article['title'][:40]} ({len(full_text)} 字)")

    # 付费墙判断：内容仍然很短（< 150 字）或属于已知付费域名且内容 < 400 字
    clean_len = len(re.sub(r'<[^>]+>', '', article.get("content", "")).strip())
    is_known = _is_known_paywall_domain(link)
    if clean_len < 150 or (is_known and clean_len < 400):
        article["is_paywalled"] = True
        if is_known:
            print(f"    🔒 付费墙域名: {article['title'][:40]}")
        else:
            print(f"    🔒 内容疑似受限: {article['title'][:40]} ({clean_len} 字)")
    else:
        article["is_paywalled"] = False

    return article


def _is_cloudflare_challenge(resp_text: str) -> bool:
    """判断响应是否是 Cloudflare 机器验证页面"""
    markers = ["cf-browser-verification", "cf_clearance", "Cloudflare", "cloudflare",
               "checking your browser", "执行安全验证", "Just a moment"]
    return any(m in resp_text[:2000] for m in markers)


def _fetch_with_cloudscraper(url: str, timeout: int = 20) -> "requests.Response | None":
    """
    使用 cloudscraper 绕过 Cloudflare JS 验证，返回 Response 对象。
    若 cloudscraper 未安装，返回 None。
    注意：只能绕过自动 JS 验证，无法绕过需要人工点击的 CAPTCHA。
    """
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )
        return scraper.get(url, timeout=timeout)
    except ImportError:
        return None
    except Exception as e:
        print(f"  [cloudscraper] 失败: {e}")
        return None


def fetch_feed(url: str, fetch_fulltext: bool = True) -> dict:
    """
    抓取并解析一个 RSS/Atom feed。
    返回 { "feed_title": str, "articles": list[dict] }
    遇到 Cloudflare JS 验证时，自动用 cloudscraper 绕过后直接解析内容。
    当 fetch_fulltext=True 时，会并发抓取内容较短文章的完整正文。
    """
    _BROWSER_UA = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    # 预先抓取的内容（成功时直接传给 feedparser，避免二次请求再被拦）
    prefetched_content: str | None = None

    try:
        import requests as _req
        resp = _req.get(url, timeout=15, headers={"User-Agent": _BROWSER_UA})
        status = resp.status_code

        # ── 优先检测 Cloudflare（返回 403/503/200 均可能携带 CF 验证页） ──
        # 必须在其他状态码判断之前，否则 CF 返回 403 时会被误报为"需要登录"
        if _is_cloudflare_challenge(resp.text):
            print(f"  [Cloudflare] 检测到验证页（HTTP {status}），尝试 cloudscraper 绕过: {url[:60]}")
            cf_resp = _fetch_with_cloudscraper(url)
            if cf_resp is not None and cf_resp.status_code == 200 and not _is_cloudflare_challenge(cf_resp.text):
                print(f"  ✓ cloudscraper 绕过成功")
                prefetched_content = cf_resp.text
            elif cf_resp is not None and _is_cloudflare_challenge(cf_resp.text):
                raise ValueError(
                    "Cloudflare 要求人工验证（CAPTCHA），无法自动绕过。\n"
                    "建议：本地自建 RSSHub → docker run -d -p 1200:1200 diygod/rsshub\n"
                    "然后在 .env 中设置 RSSHUB_BASE=http://localhost:1200"
                )
            else:
                raise ValueError(
                    "cloudscraper 绕过失败，请确认已安装：\n"
                    "pip install cloudscraper --break-system-packages\n"
                    "或本地自建 RSSHub：docker run -d -p 1200:1200 diygod/rsshub"
                )
        # ── 非 Cloudflare 的正常状态码判断 ──
        elif status in (401, 403):
            raise ValueError(
                f"该订阅源拒绝访问（HTTP {status}）。\n"
                "可能原因：① 需要登录/付费订阅 ② 该网站禁止程序抓取"
            )
        elif status == 404:
            raise ValueError("订阅源地址不存在（HTTP 404），请检查 URL 是否正确")
        elif status == 429:
            raise ValueError("请求频率太高被限流（HTTP 429），请稍后再试")
        elif status >= 500:
            raise ValueError(f"服务器错误（HTTP {status}），该网站暂时不可用")
        else:
            ct = resp.headers.get("content-type", "")
            body_preview = resp.text[:500]
            is_html_body = "html" in ct or "<html" in body_preview.lower()
            if is_html_body:
                raise ValueError(
                    "该地址返回的是 HTML 页面，不是 RSS/Atom 格式。\n"
                    "请确认 URL 是 RSS 订阅链接，而非普通网页地址"
                )

    except ValueError:
        raise
    except Exception as e:
        err = str(e)
        if "timed out" in err or "timeout" in err.lower():
            raise ValueError(
                "连接超时（15 秒无响应）。\n"
                "可能原因：① 该网站在当前网络环境下被限制访问\n"
                "          ② 服务器响应太慢  ③ 本地网络不稳定"
            )
        if "Connection refused" in err:
            raise ValueError("连接被拒绝，服务器可能已关闭或端口不对")
        if "SSL" in err or "certificate" in err.lower():
            raise ValueError(
                f"SSL 证书验证失败：{e}\n"
                "可能是该网站的 HTTPS 证书有问题，或网络环境下 SSL 被干扰"
            )
        if "Name or service not known" in err or "getaddrinfo" in err:
            raise ValueError("无法解析域名，请检查网络连接或 URL 拼写是否正确")
        raise ValueError(f"网络请求失败：{e}")

    # 若已预先抓取到内容（绕过 Cloudflare 后），直接用字符串解析，不让 feedparser 再请求一次
    if prefetched_content is not None:
        parsed = feedparser.parse(prefetched_content)
    else:
        parsed = feedparser.parse(url)

    if parsed.bozo and not parsed.entries:
        bozo_msg = str(getattr(parsed, 'bozo_exception', '未知错误'))
        raise ValueError(f"RSS 格式解析失败：{bozo_msg}")

    feed_title = parsed.feed.get("title", url)
    articles = []

    for entry in parsed.entries:
        articles.append({
            "title": getattr(entry, "title", "无标题"),
            "link": getattr(entry, "link", ""),
            "author": getattr(entry, "author", ""),
            "summary": getattr(entry, "summary", "")[:500],
            "content": extract_content(entry),
            "published": parse_published(entry),
        })

    # 并发抓取全文
    if fetch_fulltext and articles:
        print(f"  [全文抓取] 正在检查 {len(articles)} 篇文章...")
        try:
            with ThreadPoolExecutor(max_workers=FETCH_CONTENT_WORKERS) as executor:
                futures = {executor.submit(_fetch_article_fulltext, a): a for a in articles}
                articles = [future.result() for future in as_completed(futures)]
        except Exception as e:
            print(f"  [全文抓取] 并发失败，使用 RSS 原始内容: {e}")

    return {"feed_title": feed_title, "articles": articles}


def fetch_and_store(feed_id: int, url: str) -> dict:
    """抓取 feed 并存入数据库，返回统计信息"""
    from database import get_feed
    result = fetch_feed(url)

    # 只有当用户没有手动填写名称时，才用 RSS 源自带标题自动填入
    # 若用户已填写名称（非空、非 URL 本身），则保留用户的名称不覆盖
    feed_row = get_feed(feed_id)
    current_title = (feed_row or {}).get("title", "")
    title_is_user_set = current_title and current_title != url
    if not title_is_user_set and result["feed_title"] and result["feed_title"] != url:
        update_feed_title(feed_id, result["feed_title"])

    new_count = save_articles(feed_id, result["articles"])
    update_last_fetched(feed_id)

    return {
        "feed_id": feed_id,
        "feed_title": result["feed_title"],
        "total_entries": len(result["articles"]),
        "new_articles": new_count,
    }


def fetch_all_feeds(feeds: list[dict]) -> list[dict]:
    """批量抓取所有已订阅的 feed"""
    results = []
    for feed in feeds:
        try:
            r = fetch_and_store(feed["id"], feed["url"])
            results.append(r)
            print(f"  ✓ [{feed['id']}] {r['feed_title']}: {r['new_articles']} 篇新文章")
        except Exception as e:
            print(f"  ✗ [{feed['id']}] {feed['url']}: {e}")
            results.append({"feed_id": feed["id"], "feed_title": feed.get("title", feed["url"]), "error": str(e)})
    return results
