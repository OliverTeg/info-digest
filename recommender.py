"""
用户画像 → AI Bundle 推荐模块
根据用户的兴趣、职业、目标，由 Kimi AI 从订阅源库中挑选最合适的 RSS bundle
"""

import json
import re
from config import KIMI_API_KEY, KIMI_MODEL
from openai import OpenAI

KIMI_BASE_URL = "https://api.moonshot.cn/v1"


def _get_client() -> OpenAI:
    if not KIMI_API_KEY:
        raise ValueError("未设置 KIMI_API_KEY，请在 .env 文件中填入。")
    return OpenAI(api_key=KIMI_API_KEY, base_url=KIMI_BASE_URL)


def _build_feed_catalog() -> str:
    """
    把 rsshub.py 中的订阅源整理成 AI 可读的目录文本。
    每条记录包含 key、名称、分类、描述、可用 URL。
    """
    from rsshub import ROUTES, RSSHUB_BASE
    lines = []
    for r in ROUTES:
        urls = []
        for n in r.get("native_rss", []):
            urls.append(f"[直连] {n['name']}: {n['url']}")
        for ro in r.get("routes", []):
            if not ro.get("need_param"):
                full = RSSHUB_BASE + ro["path"]
                urls.append(f"[RSSHub] {ro['name']}: {full}")
        if not urls:
            continue
        url_str = " | ".join(urls)
        lines.append(
            f"- key={r['key']} [{r['category']}] {r['site']}：{r['description']} → {url_str}"
        )
    return "\n".join(lines)


def recommend_bundle(name: str, profession: str,
                     interests: list[str], goals: list[str],
                     custom_note: str = "") -> dict:
    """
    调用 Kimi，根据用户画像从订阅源库中挑选推荐 bundle。
    返回结构：
    {
      "greeting": "一句个性化欢迎语",
      "bundles": [
        {
          "group": "分组名称（如 AI 前沿、商业洞察）",
          "reason": "为什么推荐这组",
          "feeds": [
            { "key": "hackernews", "name": "Hacker News - 最新热帖",
              "url": "https://...", "reason": "..." }
          ]
        }
      ]
    }
    """
    catalog = _build_feed_catalog()
    interests_str = "、".join(interests) if interests else "未指定"
    goals_str = "、".join(goals) if goals else "未指定"

    prompt = (
        f"你是一位资讯订阅顾问。根据用户画像，从以下订阅源目录中为用户挑选最合适的 RSS bundle。\n\n"
        f"【用户画像】\n"
        f"姓名：{name or '用户'}\n"
        f"职业：{profession or '未填写'}\n"
        f"兴趣领域：{interests_str}\n"
        f"目标：{goals_str}\n"
        f"补充说明：{custom_note or '无'}\n\n"
        f"【可用订阅源目录】\n{catalog}\n\n"
        f"【要求】\n"
        f"1. 挑选 8-15 个最适合该用户的订阅源，分成 2-4 个主题分组\n"
        f"2. 优先选择有[直连]URL的源（更稳定），[RSSHub]源作为补充\n"
        f"3. 每个分组写明推荐理由（1-2句话），每个订阅源写一句简短推荐语\n"
        f"4. 只返回 JSON，格式如下（不要markdown代码块）：\n"
        f'{{"greeting":"欢迎语（称呼用户名字，结合职业和目标，20字以内）",'
        f'"bundles":[{{"group":"分组名","reason":"推荐理由",'
        f'"feeds":[{{"key":"source_key","name":"显示名称","url":"完整URL","reason":"一句推荐语"}}]}}]}}'
    )

    client = _get_client()
    response = client.chat.completions.create(
        model="moonshot-v1-32k",
        messages=[
            {"role": "system", "content": "你是资讯订阅顾问。只返回JSON，不要任何解释文字。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=2000,
    )

    reply = response.choices[0].message.content.strip()

    # 提取 JSON（防止 AI 包裹了 markdown）
    json_match = re.search(r'\{.*\}', reply, re.DOTALL)
    if json_match:
        reply = json_match.group(0)

    try:
        data = json.loads(reply)
    except json.JSONDecodeError:
        # 容错：返回基础推荐
        data = _fallback_recommend(interests)

    # 校验结构完整性
    if "bundles" not in data:
        data = _fallback_recommend(interests)

    return data


def _fallback_recommend(interests: list[str]) -> dict:
    """AI 不可用时的兜底推荐（基于规则）"""
    from rsshub import ROUTES, RSSHUB_BASE

    # 按兴趣分类匹配
    interest_set = {i.lower() for i in interests}
    cat_map = {
        "技术": ["技术", "tech", "开发", "编程", "ai", "人工智能"],
        "新闻": ["新闻", "时事", "国际", "政治"],
        "财经": ["财经", "金融", "投资", "商业", "创业"],
        "学术": ["学术", "研究", "论文", "科学"],
    }

    selected = []
    for r in ROUTES:
        for cat, keywords in cat_map.items():
            if any(k in interest_set or k in r["category"].lower() for k in keywords):
                for n in r.get("native_rss", [])[:1]:
                    selected.append({
                        "key": r["key"], "name": r["site"] + " · " + n["name"],
                        "url": n["url"], "reason": r["description"]
                    })
                break

    return {
        "greeting": "欢迎使用 Information Digest！",
        "bundles": [{"group": "为你推荐", "reason": "根据你的兴趣匹配", "feeds": selected[:12]}]
    }
