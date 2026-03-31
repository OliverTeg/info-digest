# Information Digest MVP — RSS 抓取原型

一款帮助用户从繁冗信息中获取有效内容的工具，当前为 MVP 阶段，已实现 RSS 抓取核心功能。

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 运行演示
```bash
python demo.py
```
这会添加几个示例 RSS 源，抓取内容，并在命令行展示结果。

### 3. 启动 API 服务器
```bash
python main.py
```
服务启动后访问 `http://localhost:8000/docs` 查看交互式 API 文档。

## API 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/feeds` | 添加订阅源 |
| GET | `/feeds` | 列出所有订阅源 |
| DELETE | `/feeds/{id}` | 删除订阅源 |
| POST | `/feeds/{id}/fetch` | 立即抓取某个源 |
| POST | `/feeds/fetch-all` | 抓取所有源 |
| GET | `/articles` | 获取文章列表（支持分页和筛选） |
| GET | `/articles/{id}` | 获取文章详情 |
| DELETE | `/articles/{id}` | 删除文章 |
| PUT | `/scheduler` | 更新自动抓取间隔 |

## 项目结构

```
info-digest-mvp/
├── main.py          # FastAPI 主入口 & API 接口
├── database.py      # SQLite 数据存储
├── fetcher.py       # RSS 抓取 & 解析
├── scheduler.py     # 定时抓取调度
├── demo.py          # 快速演示脚本
├── requirements.txt # Python 依赖
└── README.md
```

## 后续规划

- [ ] AI 摘要与翻译（接入 LLM API）
- [ ] 前端卡片式界面
- [ ] 用户画像收集与推荐算法
- [ ] 邮件 Digest 推送（daily/weekly/monthly）
- [ ] 分组与文件夹管理
