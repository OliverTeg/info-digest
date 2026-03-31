"""
每日信息整合报告
- AI 真正阅读所有文章全文（而非复用摘要），生成编辑级别的深度整合分析
- 输出自包含 HTML 页面，用户通过浏览器"打印→保存PDF"获取 PDF
"""

import re
import json
import html as html_lib
import math
from datetime import datetime
from database import list_articles, list_feeds
from config import KIMI_API_KEY, KIMI_MODEL


# ─────────────────── 工具函数 ───────────────────

def _strip_html(text: str) -> str:
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _escape(text: str) -> str:
    return html_lib.escape(str(text or ''), quote=True)


def _estimate_reading_time(text: str) -> int:
    chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
    english = len(re.findall(r'[a-zA-Z]+', text))
    return max(1, round(chinese / 400 + english / 200))


# ─────────────────── AI 深度整合分析 ───────────────────

def _get_kimi_client():
    try:
        from openai import OpenAI
    except ImportError:
        return None
    if not KIMI_API_KEY:
        return None
    return OpenAI(api_key=KIMI_API_KEY, base_url="https://api.moonshot.cn/v1")


def _build_reading_material(articles: list[dict]) -> str:
    """
    把所有文章的完整内容打包成 AI 可读的文本块。
    每篇文章优先使用 content（全文），回退到 summary，最后用 ai_summary_zh。
    智能截断：保证总 token 在 30k 以内。
    """
    # 估算每篇允许的字符数（32k token ≈ 24000 中文字）
    total_budget = 22000
    per_article_budget = max(500, total_budget // max(len(articles), 1))

    parts = []
    for i, a in enumerate(articles, 1):
        title = a.get('title_zh') or a.get('title', '无标题')
        original_title = a.get('title', '')

        # 获取最详细的内容
        raw = a.get('content', '') or a.get('summary', '') or a.get('ai_summary_zh', '')
        clean = _strip_html(raw)

        # 如果全文很短，补充 ai_summary_zh
        if len(clean) < 100 and a.get('ai_summary_zh'):
            clean = a['ai_summary_zh'] + '\n' + clean

        # 截断到预算
        if len(clean) > per_article_budget:
            clean = clean[:per_article_budget] + '…（全文已截断）'

        feed_title = a.get('_feed_title', '')
        kw = a.get('keywords', '')
        pub = a.get('published', '')[:10] if a.get('published') else ''

        part = f"""━━ 文章 {i}【{title}】
来源：{feed_title}  发布：{pub}  关键词：{kw}
{"原始标题：" + original_title if original_title and original_title != title else ""}
正文内容：
{clean}"""
        parts.append(part)

    return '\n\n'.join(parts)


def generate_digest_analysis(articles: list[dict]) -> dict:
    """
    让 AI 真正阅读全部文章内容，生成深度整合分析。
    返回结构化 dict：
    {
      overview:     str,  # 600-800字宏观分析文章
      key_insights: [str],  # 5-7条核心洞察
      connections:  str,  # 文章间信息关联分析
      article_notes: [{"idx":1,"comment":str,"association":str}],
      model_used:   str,
    }
    """
    client = _get_kimi_client()
    if not client:
        return _fallback_analysis(articles)

    reading_material = _build_reading_material(articles)
    n = len(articles)

    prompt = f"""你是一位资深的信息分析师和新闻编辑。以下是今日 {n} 篇文章的完整内容（来自不同订阅源）。

请仔细阅读所有内容，然后生成一份深度整合报告。注意：这不是让你重新摘要每篇文章，而是让你作为编辑，从宏观角度分析今日信息的整体面貌、内在联系和深层含义。

返回以下 JSON（不要 markdown 代码块，不要其他文字）：

{{
  "overview": "【今日全景】宏观叙事分析，600-800字。不是逐篇罗列，而是从信息整体中提炼出今日的核心叙事、趋势和值得关注的现象。用第一人称，有见地，像一篇社论短文。",
  "key_insights": [
    "洞察1：跨文章发现的关键趋势或规律（不超过2句话）",
    "洞察2",
    "洞察3",
    "洞察4",
    "洞察5"
  ],
  "connections": "【信息连接】这些文章之间的隐含联系、共同主题、或相互印证的内容（150-200字）",
  "article_notes": [
    {{"idx": 1, "comment": "对该文章的精辟一句话点评", "association": "联想延伸：该话题与其他领域的关联，或对未来的启示（1-2句）"}},
    ...为每篇文章生成
  ]
}}

以下是今日文章内容：

{reading_material}"""

    # 优先用 32k 模型，回退到 8k
    models_to_try = []
    if '8k' in KIMI_MODEL:
        models_to_try = ['moonshot-v1-32k', 'moonshot-v1-8k', KIMI_MODEL]
    else:
        models_to_try = [KIMI_MODEL, 'moonshot-v1-32k', 'moonshot-v1-8k']

    for model in models_to_try:
        try:
            print(f"  [整合分析] 使用模型 {model}，阅读 {n} 篇文章...")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是深度信息分析师。只返回JSON，不要markdown代码块。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=3000,
            )
            reply = response.choices[0].message.content.strip()

            # 提取 JSON（兼容 markdown 代码块）
            m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', reply, re.DOTALL)
            if m:
                reply = m.group(1)
            # 清理尾部多余逗号
            reply = re.sub(r',\s*([}\]])', r'\1', reply)

            data = json.loads(reply)
            data['model_used'] = model
            print(f"  [整合分析] ✓ 分析完成，使用 {model}")
            return data

        except json.JSONDecodeError as e:
            print(f"  [整合分析] JSON 解析失败: {e}，尝试下一个模型")
            continue
        except Exception as e:
            err_str = str(e)
            if 'context_length' in err_str or 'token' in err_str.lower():
                print(f"  [整合分析] {model} 上下文超限，尝试下一个模型")
                continue
            print(f"  [整合分析] {model} 调用失败: {e}")
            continue

    print("  [整合分析] 所有模型均失败，使用后备分析")
    return _fallback_analysis(articles)


def _fallback_analysis(articles: list[dict]) -> dict:
    """AI 不可用时的简单后备分析"""
    from collections import Counter
    all_kw = []
    for a in articles:
        if a.get('keywords'):
            all_kw.extend(k.strip() for k in a['keywords'].split(',') if k.strip())
    top = Counter(all_kw).most_common(5)
    kw_str = '、'.join(k for k, _ in top) if top else '综合资讯'

    return {
        'overview': f'今日共收录来自各订阅源的 {len(articles)} 篇文章，主要涉及 {kw_str} 等领域。请配置 KIMI_API_KEY 以启用 AI 深度分析功能。',
        'key_insights': [f'主要关键词：{kw_str}', f'共 {len(articles)} 篇文章'],
        'connections': '请配置 KIMI_API_KEY 以启用跨文章关联分析。',
        'article_notes': [
            {'idx': i + 1, 'comment': a.get('ai_summary_zh', '')[:80] + '...', 'association': ''}
            for i, a in enumerate(articles)
        ],
        'model_used': 'fallback',
    }


# ─────────────────── HTML 渲染 ───────────────────

def _render_digest_html(articles: list[dict], analysis: dict, stats: dict, date_str: str) -> str:
    """渲染完整的自包含 HTML 整合报告"""

    n = len(articles)
    total_rt = stats['total_reading_time']
    digest_rt = stats['digest_reading_time']
    time_saved = stats['time_saved']
    saved_pct = stats['time_saved_pct']

    # Build article HTML items
    article_notes_map = {c.get('idx', 0): c for c in analysis.get('article_notes', [])}
    article_parts = []

    for i, a in enumerate(articles, 1):
        title = a.get('title_zh') or a.get('title', '无标题')
        original_title = a.get('title', '')
        summary = a.get('ai_summary_zh', '')
        kw = a.get('keywords', '')
        rt = a.get('reading_time', 0)
        link = a.get('link', '')
        feed_name = a.get('_feed_title', '未知来源')
        pub = a.get('published', '')[:10] if a.get('published') else ''

        note = article_notes_map.get(i, {})
        comment = note.get('comment', '')
        association = note.get('association', '')

        item = '<div class="article-item">'
        item += '<div class="article-header">'
        item += '<div class="article-meta-top">'
        item += '<span class="feed-badge">' + _escape(feed_name) + '</span>'
        if pub:
            item += '<span class="pub-date">' + _escape(pub) + '</span>'
        if rt:
            item += '<span class="reading-time">&#x23F1; ' + str(rt) + ' \u5206\u949f</span>'
        item += '</div>'
        item += '<h3 class="article-title">' + _escape(title) + '</h3>'
        if original_title and original_title != title:
            item += '<div class="article-original-title">' + _escape(original_title) + '</div>'
        item += '</div>'  # article-header
        item += '<div class="article-body">'
        if summary:
            item += '<p class="article-summary">' + _escape(summary) + '</p>'
        if comment:
            item += '<div class="ai-note comment"><span class="note-label">&#x1F4AC; AI\u70b9\u8bc4</span>' + _escape(comment) + '</div>'
        if association:
            item += '<div class="ai-note association"><span class="note-label">&#x1F52E; \u8054\u60f3\u5ef6\u4f38</span>' + _escape(association) + '</div>'
        if kw:
            kw_tags = ''.join('<span class="kw-tag">' + _escape(k.strip()) + '</span>' for k in kw.split(',') if k.strip())
            item += '<div class="kw-tags">' + kw_tags + '</div>'
        if link:
            item += '<a href="' + _escape(link) + '" target="_blank" class="article-link">\u9605\u8bfb\u539f\u6587 &rarr;</a>'
        item += '</div>'  # article-body
        item += '</div>'  # article-item
        article_parts.append(item)

    articles_html = '\n'.join(article_parts)

    insights = analysis.get('key_insights', [])
    insights_items = '\n'.join('<li>' + _escape(s) + '</li>' for s in insights if s)

    overview = _escape(analysis.get('overview', ''))
    overview_br = overview.replace('\n', '<br>')
    connections = _escape(analysis.get('connections', ''))
    model_used = _escape(analysis.get('model_used', ''))

    insights_block = ''
    if insights_items:
        insights_block = (
            '<div class="section">'
            '<div class="section-title">&#x1F3AF; \u6838\u5fc3\u6d1e\u5bdf</div>'
            '<ol class="insights-list">' + insights_items + '</ol>'
            '</div>'
        )

    connections_block = ''
    if connections:
        connections_block = (
            '<div class="section">'
            '<div class="section-title">&#x1F517; \u4fe1\u606f\u8fde\u63a5</div>'
            '<div class="connections-card">' + connections + '</div>'
            '</div>'
        )

    # Build the full HTML using string concatenation
    parts = []
    parts.append('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n')
    parts.append('<meta charset="UTF-8">\n')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">\n')
    parts.append('<title>Information Digest \u2014 ' + _escape(date_str) + '</title>\n')
    parts.append('''<style>
    :root {
      --primary: #f97316; --primary-light: #fff7ed; --primary-dark: #ea580c;
      --text: #1e293b; --text-light: #64748b; --border: #e2e8f0;
      --bg: #f8fafc; --radius: 12px;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB",
           "Microsoft YaHei", "Segoe UI", sans-serif;
           background: var(--bg); color: var(--text); line-height: 1.7; font-size: 15px; }
    .digest-header { background: linear-gradient(135deg, var(--primary-dark) 0%, var(--primary) 100%);
                     color: white; padding: 40px 48px 32px; }
    .digest-header h1 { font-size: 28px; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 6px; }
    .digest-header .subtitle { font-size: 14px; opacity: 0.85; margin-bottom: 24px; }
    .stats-row { display: flex; gap: 32px; flex-wrap: wrap; }
    .stat-item { display: flex; flex-direction: column; }
    .stat-value { font-size: 28px; font-weight: 700; line-height: 1; }
    .stat-label { font-size: 12px; opacity: 0.8; margin-top: 4px; }
    .stat-highlight .stat-value { color: #fcd34d; }
    .digest-body { max-width: 900px; margin: 0 auto; padding: 32px 24px 60px; }
    .section { margin-bottom: 32px; }
    .section-title { font-size: 17px; font-weight: 700; color: var(--text);
                     margin-bottom: 14px; padding-bottom: 10px;
                     border-bottom: 2px solid var(--primary); }
    .overview-card { background: white; border: 1px solid var(--border);
                     border-radius: var(--radius); padding: 24px; line-height: 1.9; }
    .insights-list { list-style: none; display: flex; flex-direction: column; gap: 10px;
                     counter-reset: insight-counter; }
    .insights-list li { background: white; border: 1px solid var(--border);
                        border-left: 4px solid var(--primary); border-radius: 0 8px 8px 0;
                        padding: 12px 16px; font-size: 14px; line-height: 1.6;
                        counter-increment: insight-counter; }
    .insights-list li::before { content: counter(insight-counter, decimal-leading-zero);
                                 color: var(--primary); font-weight: 700; font-size: 12px; margin-right: 10px; }
    .connections-card { background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
                        border: 1px solid #bae6fd; border-radius: var(--radius);
                        padding: 20px 24px; color: #0c4a6e; font-size: 14px; line-height: 1.8; }
    .article-item { background: white; border: 1px solid var(--border);
                    border-radius: var(--radius); padding: 20px 22px; margin-bottom: 14px; }
    .article-meta-top { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }
    .feed-badge { background: var(--primary-light); color: var(--primary-dark);
                  font-size: 11px; font-weight: 600; padding: 2px 10px; border-radius: 12px; }
    .pub-date, .reading-time { font-size: 11px; color: var(--text-light); }
    .article-title { font-size: 15px; font-weight: 700; line-height: 1.4; margin-bottom: 4px; }
    .article-original-title { font-size: 11px; color: var(--text-light); font-style: italic; margin-bottom: 6px; }
    .article-summary { font-size: 13px; color: var(--text-light); line-height: 1.7; margin-bottom: 10px; }
    .ai-note { font-size: 13px; line-height: 1.6; padding: 8px 12px; border-radius: 6px; margin-bottom: 6px; }
    .ai-note.comment { background: #faf5ff; color: #6b21a8; }
    .ai-note.association { background: #eff6ff; color: #1e40af; }
    .note-label { font-weight: 600; margin-right: 6px; }
    .kw-tags { margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; }
    .kw-tag { background: #f1f5f9; color: var(--text-light); font-size: 11px; padding: 2px 10px; border-radius: 4px; }
    .article-link { display: inline-block; margin-top: 10px; font-size: 12px; color: var(--primary);
                    text-decoration: none; font-weight: 500; }
    .article-link:hover { text-decoration: underline; }
    .print-bar { position: fixed; bottom: 24px; right: 24px; display: flex; gap: 10px; z-index: 100; }
    .print-btn { background: var(--primary); color: white; border: none; padding: 12px 22px;
                 border-radius: 10px; font-size: 14px; font-weight: 600; cursor: pointer;
                 box-shadow: 0 4px 14px rgba(249,115,22,0.4); font-family: inherit; }
    .print-btn:hover { background: var(--primary-dark); }
    .print-btn.secondary { background: white; color: var(--text); border: 1px solid var(--border);
                           box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
    .digest-footer { text-align: center; padding: 24px; color: var(--text-light);
                     font-size: 12px; border-top: 1px solid var(--border); margin-top: 16px; }
    @media print {
      .print-bar { display: none !important; }
      body { background: white; font-size: 13px; }
      .digest-header { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
      .article-item { break-inside: avoid; page-break-inside: avoid; }
      .section { break-inside: avoid; }
    }
  </style>\n''')
    parts.append('</head>\n<body>\n')
    # Header
    parts.append('<div class="digest-header">\n')
    parts.append('<h1>&#x1F4F0; Information Digest</h1>\n')
    parts.append('<div class="subtitle">' + _escape(date_str) + ' &middot; AI \u6df1\u5ea6\u6574\u5408\u62a5\u544a &middot; ' + model_used + '</div>\n')
    parts.append('<div class="stats-row">\n')
    parts.append('<div class="stat-item"><span class="stat-value">' + str(n) + '</span><span class="stat-label">\u7bc7\u6587\u7ae0</span></div>\n')
    parts.append('<div class="stat-item"><span class="stat-value">' + str(total_rt) + '</span><span class="stat-label">\u5206\u949f\uff08\u539f\u6587\uff09</span></div>\n')
    parts.append('<div class="stat-item"><span class="stat-value">' + str(digest_rt) + '</span><span class="stat-label">\u5206\u949f\uff08\u672c\u62a5\u544a\uff09</span></div>\n')
    parts.append('<div class="stat-item stat-highlight"><span class="stat-value">&#x2193;' + str(saved_pct) + '%</span><span class="stat-label">\u8282\u7701 ' + str(time_saved) + ' \u5206\u949f</span></div>\n')
    parts.append('</div>\n</div>\n')  # stats-row, digest-header
    # Body
    parts.append('<div class="digest-body">\n')
    # Overview
    parts.append('<div class="section">')
    parts.append('<div class="section-title">&#x1F30E; \u4eca\u65e5\u5168\u666f</div>')
    parts.append('<div class="overview-card">' + overview_br + '</div>')
    parts.append('</div>\n')
    # Insights
    parts.append(insights_block)
    # Connections
    parts.append(connections_block)
    # Articles
    parts.append('<div class="section">')
    parts.append('<div class="section-title">&#x1F4C4; \u6587\u7ae0\u8be6\u60c5\u4e0e AI \u70b9\u8bc4</div>')
    parts.append(articles_html)
    parts.append('</div>\n')
    parts.append('</div>\n')  # digest-body
    # Footer
    parts.append('<div class="digest-footer">')
    parts.append('Information Digest &middot; ' + _escape(date_str))
    parts.append(' &middot; \u5171 ' + str(n) + ' \u7bc7\u6587\u7ae0')
    parts.append(' &middot; \u539f\u6587\u9605\u8bfb ' + str(total_rt) + ' \u5206\u949f &rarr; \u6574\u5408\u62a5\u544a ' + str(digest_rt) + ' \u5206\u949f\uff0c\u8282\u7701 ' + str(time_saved) + ' \u5206\u949f')
    parts.append('</div>\n')
    # Print bar
    parts.append('<div class="print-bar">')
    parts.append('<button class="print-btn secondary" onclick="window.close()">&#x2715; \u5173\u95ed</button>')
    parts.append('<button class="print-btn" onclick="window.print()">&#x1F5A8; \u6253\u5370 / \u4fdd\u5b58\u4e3a PDF</button>')
    parts.append('</div>\n')
    parts.append('</body>\n</html>')
    return ''.join(parts)


# ─────────────────── 主入口 ───────────────────

def generate_digest(date_str: str = None) -> tuple[str, dict]:
    """
    生成每日整合报告 HTML。
    返回 (html_str, stats_dict)
    """
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # 获取已摘要文章
    all_articles = list_articles(limit=200)
    summarized = [a for a in all_articles if a.get('ai_summary_zh') and a['ai_summary_zh'].strip()]

    if not summarized:
        raise ValueError("没有已摘要的文章，请先抓取并生成摘要")

    # 注入 feed 名称
    feeds = list_feeds()
    feeds_map = {f['id']: f for f in feeds}
    for a in summarized:
        feed = feeds_map.get(a['feed_id'], {})
        a['_feed_title'] = feed.get('title') or feed.get('category') or '未分类'

    # 统计阅读时间
    total_rt = sum(a.get('reading_time', 0) for a in summarized)
    digest_rt = max(2, math.ceil(len(summarized) * 0.4))  # 每篇约 24 秒
    time_saved = max(0, total_rt - digest_rt)

    stats = {
        'total_articles': len(summarized),
        'total_reading_time': total_rt,
        'digest_reading_time': digest_rt,
        'time_saved': time_saved,
        'time_saved_pct': round(time_saved / total_rt * 100) if total_rt > 0 else 0,
    }

    # AI 深度分析（读全文）
    analysis = generate_digest_analysis(summarized)

    # 渲染 HTML
    html = _render_digest_html(summarized, analysis, stats, date_str)

    return html, stats
