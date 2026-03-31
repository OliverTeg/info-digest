"""
RSSHub 路由数据库与订阅源自动发现
用户只需输入网站名称，平台自动生成可抓取的 RSS URL

关于 rsshub.app 公共实例在中国大陆访问不稳定的问题：
  推荐本地自建 RSSHub：docker run -d -p 1200:1200 diygod/rsshub
  然后在 .env 文件中设置：RSSHUB_BASE=http://localhost:1200
"""

import os

# 从环境变量读取 RSSHub 实例地址，默认为公共实例
# 中国大陆用户推荐本地自建：docker run -d -p 1200:1200 diygod/rsshub
RSSHUB_BASE = os.getenv("RSSHUB_BASE", "https://rsshub.app").rstrip("/")

# ─────────────────── 路由数据库 ───────────────────
# 每条记录：
#   key        : 唯一标识
#   site       : 网站官方名称
#   aliases    : 搜索别名（中英文）
#   category   : 分类
#   description: 简介
#   native_rss : 网站自带的原生 RSS（不需要 RSSHub，最可靠）
#   routes     : RSSHub 路由列表（备选，需要 RSSHub 实例）
#                 name      : 路由名称
#                 path      : RSSHub 路径，{PARAM} 为需要填写的参数
#                 params    : [{"key":"uid","label":"用户UID","hint":"如何获取"}]
#                 example   : 完整示例 URL
#                 need_param: bool（是否需要用户填写参数）

ROUTES: list[dict] = [

    # ══════════════════ 技术资讯 ══════════════════
    {
        "key": "hackernews",
        "site": "Hacker News",
        "aliases": ["hn", "hacker news", "hackernews", "黑客新闻", "技术论坛"],
        "category": "技术",
        "description": "硅谷顶级技术社区，程序员必读",
        "native_rss": [
            {"name": "最新热帖", "url": "https://news.ycombinator.com/rss"},
        ],
        "routes": [
            {
                "name": "招聘信息（via RSSHub）",
                "path": "/hackernews/jobs",
                "params": [],
                "example": "https://rsshub.app/hackernews/jobs",
                "need_param": False,
            },
        ],
    },
    {
        "key": "github_trending",
        "site": "GitHub Trending",
        "aliases": ["github", "trending", "开源", "代码", "仓库"],
        "category": "技术",
        "description": "GitHub 每日/周/月热门开源项目",
        "routes": [
            {
                "name": "每日趋势（全语言）",
                "path": "/github/trending/daily",
                "params": [],
                "example": "https://rsshub.app/github/trending/daily",
                "need_param": False,
            },
            {
                "name": "每日趋势（指定语言）",
                "path": "/github/trending/daily/{language}",
                "params": [{"key": "language", "label": "语言", "hint": "如 python、javascript、go、rust"}],
                "example": "https://rsshub.app/github/trending/daily/python",
                "need_param": True,
            },
            {
                "name": "用户动态",
                "path": "/github/user/{username}",
                "params": [{"key": "username", "label": "GitHub 用户名", "hint": "如 torvalds"}],
                "example": "https://rsshub.app/github/user/torvalds",
                "need_param": True,
            },
        ],
    },
    {
        "key": "producthunt",
        "site": "Product Hunt",
        "aliases": ["ph", "producthunt", "product hunt", "产品", "创业"],
        "category": "技术",
        "description": "每日最热门新产品发现",
        "native_rss": [
            {"name": "今日热门", "url": "https://www.producthunt.com/feed"},
        ],
        "routes": [],
    },
    {
        "key": "v2ex",
        "site": "V2EX",
        "aliases": ["v2ex", "v站", "way to explore"],
        "category": "技术",
        "description": "中文技术创意工作者社区",
        "routes": [
            {
                "name": "最新主题",
                "path": "/v2ex/topics/latest",
                "params": [],
                "example": "https://rsshub.app/v2ex/topics/latest",
                "need_param": False,
            },
            {
                "name": "热门主题",
                "path": "/v2ex/topics/hot",
                "params": [],
                "example": "https://rsshub.app/v2ex/topics/hot",
                "need_param": False,
            },
        ],
    },
    {
        "key": "sspai",
        "site": "少数派",
        "aliases": ["sspai", "少数派", "效率", "app"],
        "category": "技术",
        "description": "面向效率提升与优质数字生活方式的内容平台",
        "routes": [
            {
                "name": "最新文章",
                "path": "/sspai/latest",
                "params": [],
                "example": "https://rsshub.app/sspai/latest",
                "need_param": False,
            },
        ],
    },
    {
        "key": "infoq",
        "site": "InfoQ 中文",
        "aliases": ["infoq", "架构", "云计算", "devops"],
        "category": "技术",
        "description": "面向软件开发者的技术媒体",
        "routes": [
            {
                "name": "最新文章",
                "path": "/infoq/news",
                "params": [],
                "example": "https://rsshub.app/infoq/news",
                "need_param": False,
            },
        ],
    },

    # ══════════════════ 科技媒体 ══════════════════
    {
        "key": "36kr",
        "site": "36氪",
        "aliases": ["36kr", "36氪", "创投", "科技媒体"],
        "category": "科技媒体",
        "description": "中国领先科技与创业媒体",
        "routes": [
            {
                "name": "最新资讯",
                "path": "/36kr/latest",
                "params": [],
                "example": "https://rsshub.app/36kr/latest",
                "need_param": False,
            },
            {
                "name": "早报",
                "path": "/36kr/news/latest",
                "params": [],
                "example": "https://rsshub.app/36kr/news/latest",
                "need_param": False,
            },
        ],
    },
    {
        "key": "huxiu",
        "site": "虎嗅",
        "aliases": ["虎嗅", "huxiu", "商业", "深度"],
        "category": "科技媒体",
        "description": "科技商业深度资讯平台",
        "routes": [
            {
                "name": "热门文章",
                "path": "/huxiu/article",
                "params": [],
                "example": "https://rsshub.app/huxiu/article",
                "need_param": False,
            },
        ],
    },
    {
        "key": "theverge",
        "site": "The Verge",
        "aliases": ["verge", "the verge", "科技新闻"],
        "category": "科技媒体",
        "description": "美国顶级科技媒体",
        "native_rss": [
            {"name": "全部文章", "url": "https://www.theverge.com/rss/index.xml"},
        ],
        "routes": [],
    },
    {
        "key": "arstechnica",
        "site": "Ars Technica",
        "aliases": ["ars", "ars technica", "科学技术"],
        "category": "科技媒体",
        "description": "深度科技报道媒体",
        "native_rss": [
            {"name": "全部", "url": "https://feeds.arstechnica.com/arstechnica/index"},
            {"name": "科技", "url": "https://feeds.arstechnica.com/arstechnica/technology-lab"},
            {"name": "科学", "url": "https://feeds.arstechnica.com/arstechnica/science"},
        ],
        "routes": [],
    },
    {
        "key": "wired",
        "site": "Wired",
        "aliases": ["wired", "连线"],
        "category": "科技媒体",
        "description": "科技与文化交汇的顶级媒体",
        "native_rss": [
            {"name": "最新文章", "url": "https://www.wired.com/feed/rss"},
        ],
        "routes": [],
    },

    # ══════════════════ 新闻 ══════════════════
    {
        "key": "bbc",
        "site": "BBC News",
        "aliases": ["bbc", "英国广播公司", "国际新闻"],
        "category": "新闻",
        "description": "英国广播公司国际新闻（原生 RSS，无需 RSSHub）",
        "native_rss": [
            {"name": "头条新闻", "url": "https://feeds.bbci.co.uk/news/rss.xml"},
            {"name": "科技频道", "url": "https://feeds.bbci.co.uk/news/technology/rss.xml"},
            {"name": "科学与环境", "url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"},
            {"name": "世界新闻", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
            {"name": "商业财经", "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
        ],
        "routes": [],
    },
    {
        "key": "reuters",
        "site": "Reuters 路透社",
        "aliases": ["reuters", "路透", "路透社"],
        "category": "新闻",
        "description": "全球最大通讯社（原生 RSS）",
        "native_rss": [
            {"name": "头条新闻", "url": "https://feeds.reuters.com/reuters/topNews"},
            {"name": "科技新闻", "url": "https://feeds.reuters.com/reuters/technologyNews"},
            {"name": "商业财经", "url": "https://feeds.reuters.com/reuters/businessNews"},
        ],
        "routes": [],
    },
    {
        "key": "nytimes",
        "site": "New York Times",
        "aliases": ["nyt", "nytimes", "纽约时报"],
        "category": "新闻",
        "description": "美国权威新闻媒体（部分内容付费）",
        "native_rss": [
            {"name": "头条（免费）", "url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"},
            {"name": "科技（免费）", "url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"},
        ],
        "routes": [
            {
                "name": "头条（via RSSHub）",
                "path": "/nytimes/index",
                "params": [],
                "example": "https://rsshub.app/nytimes/index",
                "need_param": False,
            },
        ],
    },
    {
        "key": "pengpai",
        "site": "澎湃新闻",
        "aliases": ["澎湃", "pengpai", "时政"],
        "category": "新闻",
        "description": "聚焦时事与调查报道",
        "native_rss": [],
        "routes": [
            {
                "name": "首页要闻",
                "path": "/thepaper",
                "params": [],
                "example": "https://rsshub.app/thepaper",
                "need_param": False,
            },
        ],
    },
    {
        "key": "zaobao",
        "site": "联合早报",
        "aliases": ["早报", "zaobao", "新加坡", "华文"],
        "category": "新闻",
        "description": "新加坡华文主流媒体",
        "native_rss": [],
        "routes": [
            {
                "name": "即时新闻",
                "path": "/zaobao/znews/singapore",
                "params": [],
                "example": "https://rsshub.app/zaobao/znews/singapore",
                "need_param": False,
            },
        ],
    },
    {
        "key": "ap",
        "site": "AP News 美联社",
        "aliases": ["ap", "associated press", "美联社"],
        "category": "新闻",
        "description": "美国权威通讯社（via RSSHub）",
        "native_rss": [],
        "routes": [
            {
                "name": "头条新闻",
                "path": "/apnews/topics/ap-top-news",
                "params": [],
                "example": "https://rsshub.app/apnews/topics/ap-top-news",
                "need_param": False,
            },
            {
                "name": "科技新闻",
                "path": "/apnews/topics/technology",
                "params": [],
                "example": "https://rsshub.app/apnews/topics/technology",
                "need_param": False,
            },
        ],
    },

    # ══════════════════ 社交媒体 ══════════════════
    {
        "key": "bilibili",
        "site": "哔哩哔哩 (B站)",
        "aliases": ["bilibili", "b站", "b站", "bv", "av"],
        "category": "社交媒体",
        "description": "中国最大的年轻人视频社区",
        "routes": [
            {
                "name": "用户投稿视频",
                "path": "/bilibili/user/video/{uid}",
                "params": [{"key": "uid", "label": "用户 UID", "hint": "打开B站个人主页，URL中的数字即为UID，如 546195"}],
                "example": "https://rsshub.app/bilibili/user/video/546195",
                "need_param": True,
            },
            {
                "name": "分区热门视频",
                "path": "/bilibili/hot",
                "params": [],
                "example": "https://rsshub.app/bilibili/hot",
                "need_param": False,
            },
        ],
    },
    {
        "key": "zhihu",
        "site": "知乎",
        "aliases": ["zhihu", "知乎", "问答"],
        "category": "社交媒体",
        "description": "中文问答与知识分享社区",
        "routes": [
            {
                "name": "知乎热榜",
                "path": "/zhihu/hot",
                "params": [],
                "example": "https://rsshub.app/zhihu/hot",
                "need_param": False,
            },
            {
                "name": "用户动态",
                "path": "/zhihu/people/activities/{id}",
                "params": [{"key": "id", "label": "知乎用户名", "hint": "打开知乎个人主页，URL中 /people/ 后的字符串"}],
                "example": "https://rsshub.app/zhihu/people/activities/excited-vczh",
                "need_param": True,
            },
            {
                "name": "话题精华",
                "path": "/zhihu/topic/{id}",
                "params": [{"key": "id", "label": "话题 ID", "hint": "打开知乎话题页，URL中的数字"}],
                "example": "https://rsshub.app/zhihu/topic/19552207",
                "need_param": True,
            },
        ],
    },
    {
        "key": "weibo",
        "site": "微博",
        "aliases": ["weibo", "微博", "wb"],
        "category": "社交媒体",
        "description": "中国最大的微博客平台",
        "routes": [
            {
                "name": "微博热搜",
                "path": "/weibo/search/hot",
                "params": [],
                "example": "https://rsshub.app/weibo/search/hot",
                "need_param": False,
            },
            {
                "name": "用户微博",
                "path": "/weibo/user/{uid}",
                "params": [{"key": "uid", "label": "用户 UID", "hint": "打开微博个人页，URL中的数字"}],
                "example": "https://rsshub.app/weibo/user/1195230310",
                "need_param": True,
            },
        ],
    },
    {
        "key": "twitter",
        "site": "Twitter / X",
        "aliases": ["twitter", "x", "推特", "推"],
        "category": "社交媒体",
        "description": "全球实时信息平台",
        "routes": [
            {
                "name": "用户推文",
                "path": "/twitter/user/{username}",
                "params": [{"key": "username", "label": "Twitter 用户名", "hint": "@ 后的字符串，如 elonmusk"}],
                "example": "https://rsshub.app/twitter/user/elonmusk",
                "need_param": True,
            },
        ],
    },
    {
        "key": "reddit",
        "site": "Reddit",
        "aliases": ["reddit", "subreddit", "论坛"],
        "category": "社交媒体",
        "description": "全球最大论坛社区",
        "routes": [
            {
                "name": "子版块热门",
                "path": "/reddit/subreddit/{subreddit}",
                "params": [{"key": "subreddit", "label": "子版块名称", "hint": "如 technology、worldnews、MachineLearning"}],
                "example": "https://rsshub.app/reddit/subreddit/technology",
                "need_param": True,
            },
        ],
    },

    # ══════════════════ 学术/科研 ══════════════════
    {
        "key": "nature",
        "site": "Nature",
        "aliases": ["nature", "自然", "科学杂志", "学术"],
        "category": "学术",
        "description": "全球顶级科学期刊",
        "native_rss": [
            {"name": "最新研究文章", "url": "https://www.nature.com/nature.rss"},
        ],
        "routes": [
            {
                "name": "新闻与评论（via RSSHub）",
                "path": "/nature/nature/news-and-comment",
                "params": [],
                "example": "https://rsshub.app/nature/nature/news-and-comment",
                "need_param": False,
            },
        ],
    },
    {
        "key": "arxiv",
        "site": "arXiv",
        "aliases": ["arxiv", "预印本", "论文", "cs", "ai"],
        "category": "学术",
        "description": "开放获取学术预印本平台",
        "native_rss": [
            {"name": "CS.AI 人工智能", "url": "https://arxiv.org/rss/cs.AI"},
            {"name": "CS.LG 机器学习", "url": "https://arxiv.org/rss/cs.LG"},
            {"name": "CS.CV 计算机视觉", "url": "https://arxiv.org/rss/cs.CV"},
        ],
        "routes": [],
    },
    {
        "key": "mit_tech_review",
        "site": "MIT Technology Review",
        "aliases": ["mit", "mit tech", "麻省理工", "tech review"],
        "category": "学术",
        "description": "MIT 权威技术评论",
        "native_rss": [
            {"name": "最新文章", "url": "https://www.technologyreview.com/feed/"},
        ],
        "routes": [],
    },

    # ══════════════════ 财经 ══════════════════
    {
        "key": "xueqiu",
        "site": "雪球",
        "aliases": ["xueqiu", "雪球", "股票", "投资"],
        "category": "财经",
        "description": "投资者社区与财经资讯",
        "routes": [
            {
                "name": "用户动态",
                "path": "/xueqiu/user/{id}/update",
                "params": [{"key": "id", "label": "雪球用户 ID", "hint": "打开雪球个人页，URL中 /u/ 后的数字"}],
                "example": "https://rsshub.app/xueqiu/user/8152922784/update",
                "need_param": True,
            },
        ],
    },
    {
        "key": "wallstreetcn",
        "site": "华尔街见闻",
        "aliases": ["华尔街见闻", "wallstreet", "财经"],
        "category": "财经",
        "description": "实时全球财经资讯",
        "routes": [
            {
                "name": "快讯",
                "path": "/wallstreetcn/news/global",
                "params": [],
                "example": "https://rsshub.app/wallstreetcn/news/global",
                "need_param": False,
            },
        ],
    },

    # ══════════════════ AI/科技动态 ══════════════════
    {
        "key": "openai_blog",
        "site": "OpenAI Blog",
        "aliases": ["openai", "chatgpt", "gpt", "ai"],
        "category": "AI",
        "description": "OpenAI 官方博客与研究动态",
        "native_rss": [
            {"name": "官方博客", "url": "https://openai.com/news/rss.xml"},
        ],
        "routes": [],
    },
    {
        "key": "anthropic",
        "site": "Anthropic News",
        "aliases": ["anthropic", "claude", "ai safety"],
        "category": "AI",
        "description": "Anthropic 官方动态（Claude 开发商）",
        "native_rss": [
            {"name": "官方新闻", "url": "https://www.anthropic.com/news.rss"},
        ],
        "routes": [
            {
                "name": "官方新闻（via RSSHub，备用）",
                "path": "/anthropic/news",
                "params": [],
                "example": "https://rsshub.app/anthropic/news",
                "need_param": False,
            },
        ],
    },

    # ══════════════════ 生活/娱乐 ══════════════════
    {
        "key": "douban",
        "site": "豆瓣",
        "aliases": ["douban", "豆瓣", "书影音", "评分"],
        "category": "生活",
        "description": "书影音评论与生活社区",
        "routes": [
            {
                "name": "新上映电影",
                "path": "/douban/movie/playing",
                "params": [],
                "example": "https://rsshub.app/douban/movie/playing",
                "need_param": False,
            },
            {
                "name": "一周口碑电影榜",
                "path": "/douban/movie/weekly",
                "params": [],
                "example": "https://rsshub.app/douban/movie/weekly",
                "need_param": False,
            },
        ],
    },
    {
        "key": "youtube",
        "site": "YouTube",
        "aliases": ["youtube", "yt", "视频"],
        "category": "生活",
        "description": "全球最大视频平台",
        "routes": [
            {
                "name": "频道视频",
                "path": "/youtube/user/{username}/video",
                "params": [{"key": "username", "label": "频道用户名", "hint": "频道页URL中 @后的名称"}],
                "example": "https://rsshub.app/youtube/user/mkbhd/video",
                "need_param": True,
            },
        ],
    },
]


# ─────────────────── 搜索函数 ───────────────────

def search_routes(query: str, limit: int = 10) -> list[dict]:
    """
    模糊搜索 RSSHub 路由。
    支持中英文关键词，不区分大小写。
    返回按相关度排序的路由列表。
    """
    if not query:
        return []

    q = query.lower().strip()
    results = []

    for route in ROUTES:
        score = 0

        # 精确匹配 key
        if q == route['key']:
            score += 100

        # site 名称匹配
        site_lower = route['site'].lower()
        if q in site_lower:
            score += 50 + (10 if site_lower.startswith(q) else 0)

        # aliases 匹配
        for alias in route['aliases']:
            al = alias.lower()
            if q == al:
                score += 80
            elif q in al:
                score += 30
            elif al in q:
                score += 20

        # category 匹配
        if q in route['category'].lower():
            score += 15

        # description 匹配
        if q in route['description'].lower():
            score += 10

        if score > 0:
            results.append({'score': score, 'route': route})

    results.sort(key=lambda x: x['score'], reverse=True)
    return [r['route'] for r in results[:limit]]


def get_all_categories() -> list[str]:
    """获取所有路由分类"""
    cats = []
    for r in ROUTES:
        if r['category'] not in cats:
            cats.append(r['category'])
    return cats


def get_routes_by_category(category: str) -> list[dict]:
    """按分类获取路由"""
    return [r for r in ROUTES if r['category'] == category]


def build_url(path: str, params: dict) -> str:
    """将参数填入路径模板，生成完整 URL"""
    filled = path
    for k, v in params.items():
        filled = filled.replace('{' + k + '}', v)
    return RSSHUB_BASE + filled
