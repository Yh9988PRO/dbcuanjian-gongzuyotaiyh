#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公众号创作工作台 - 信源自动采集脚本（智能通用版）
每6小时运行一次，抓取官方公开列表页，输出 sources.json

特点：
  - 智能解析：自动提取页面中的新闻/公告链接，无需配置CSS选择器
  - 关键词过滤：只保留与招聘/就业/校招/公告相关的内容
  - 自动去重：按标题去重
  - 失败降级：单个信源抓取失败不影响其他信源

使用方法：
  python fetch_sources.py

输出：
  data/sources.json
"""

import json
import re
import time
import os
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin

# ============ 配置区 ============
# 只需配置 name(显示名称) 和 url(列表页URL)
# 脚本会自动解析页面中的新闻/公告链接
SOURCES = [
    # ===== 国家级 =====
    {"name": "国资委", "url": "http://www.sasac.gov.cn/n2588035/n2588320/index.html"},
    {"name": "人社部", "url": "http://www.mohrss.gov.cn/SYrlzyhshbzb/zwgk/szrs/"},
    {"name": "教育部", "url": "http://www.moe.gov.cn/jyb_xwfb/gzdt_gzdt/"},
    {"name": "财政部", "url": "http://www.mof.gov.cn/zhengwuxinxi/caizhengxinwen/"},
    # ===== 国家级招聘平台 =====
    {"name": "国聘行动", "url": "https://www.iguopin.com/"},
    {"name": "国家大学生就业服务平台", "url": "https://www.ncss.cn/"},
    # ===== 地方级（深圳/广东）=====
    {"name": "深圳市人社局", "url": "http://hrss.sz.gov.cn/xxgk/zwdt/"},
    {"name": "深圳市考试院", "url": "http://hrss.sz.gov.cn/szksy/zwgk/kszl/"},
    {"name": "广东省人社厅", "url": "http://hrss.gd.gov.cn/zwgk/zwdt/"},
    # ===== 央国企招聘 =====
    {"name": "国资小新", "url": "https://weibo.com/sasacxw"},  # 微博可能抓不到，失败自动跳过
    # ===== 教育培训机构（作为补充信号）=====
    {"name": "中公教育", "url": "https://www.offcn.com/gqzp/"},
    {"name": "华图教育", "url": "https://www.huatu.com/gq/"},
]

# 关键词白名单：标题包含这些词才会被保留
KEYWORDS = [
    "招聘", "校招", "秋招", "春招", "提前批", "校园招聘", "应届",
    "公告", "通知", "发布", "启动", "报名", "笔试", "面试", "录用",
    "就业", "人才", "岗位", "职位", "招录", "招考", "考试",
    "央企", "国企", "事业单位", "公务员", "编制", "铁饭碗",
    "白皮书", "政策", "方案", "目录", "计划", "专项",
    "2025", "2026", "2027", "2028",
]

# 关键词黑名单：标题包含这些词会被过滤
BLACKLIST = [
    "登录", "注册", "下载", "客服", "关于我们", "联系方式", "隐私",
    "首页", "更多", "上一页", "下一页", "尾页", "跳转",
]

# 请求配置
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
TIMEOUT = 15
MAX_RETRIES = 2
RETRY_DELAY = 3
REQUEST_INTERVAL = 1.5  # 每个请求间隔秒数
MAX_PER_SOURCE = 10  # 每个信源最多保留条数

# 输出路径
OUTPUT_PATH = "data/sources.json"


# ============ 工具函数 ============
def fetch_url(url):
    """抓取 URL，带重试"""
    for attempt in range(MAX_RETRIES + 1):
        try:
            req = Request(url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            })
            with urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read()
                # 尝试多种编码
                for enc in ["utf-8", "gbk", "gb2312", "gb18030"]:
                    try:
                        return raw.decode(enc)
                    except (UnicodeDecodeError, LookupError):
                        continue
                return raw.decode("utf-8", errors="ignore")
        except (URLError, HTTPError, TimeoutError, Exception) as e:
            if attempt < MAX_RETRIES:
                print(f"  ⚠ 第{attempt+1}次失败，{RETRY_DELAY}秒后重试: {e}")
                time.sleep(RETRY_DELAY)
            else:
                print(f"  ❌ 抓取失败（已重试{MAX_RETRIES}次）: {e}")
                return None


def extract_links(html, base_url):
    """
    智能提取页面中的新闻/公告链接
    返回列表：[{"title": "...", "url": "...", "date": "..."}]
    """
    results = []
    seen_titles = set()

    # 移除 script 和 style 标签内容
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # 匹配所有 <a href="..." ...>标题</a>
    # 同时捕获链接前后的日期文本
    pattern = re.compile(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.DOTALL | re.IGNORECASE
    )

    for match in pattern.finditer(html):
        url = match.group(1).strip()
        title_raw = match.group(2)

        # 清理标题中的 HTML 标签
        title = re.sub(r'<[^>]+>', '', title_raw).strip()
        title = re.sub(r'\s+', ' ', title)

        # 过滤空标题和过短标题
        if not title or len(title) < 4 or len(title) > 100:
            continue

        # 黑名单过滤
        if any(kw in title for kw in BLACKLIST):
            continue

        # 白名单过滤（至少包含一个关键词）
        if not any(kw in title for kw in KEYWORDS):
            continue

        # 去重
        if title in seen_titles:
            continue
        seen_titles.add(title)

        # 处理相对 URL
        if url and not url.startswith(("http://", "https://", "javascript:", "#")):
            try:
                url = urljoin(base_url, url)
            except Exception:
                pass

        # 提取日期：从链接前后的文本中查找
        date = extract_date_near(html, match.start(), match.end())

        results.append({
            "title": title,
            "url": url if url.startswith("http") else "#",
            "date": date,
        })

    return results[:MAX_PER_SOURCE]


def extract_date_near(html, start, end):
    """从链接前后的文本中提取日期"""
    # 取链接前后各 100 个字符
    context_start = max(0, start - 100)
    context_end = min(len(html), end + 100)
    context = html[context_start:context_end]
    context = re.sub(r'<[^>]+>', ' ', context)

    # 匹配 2026-09-05 或 2026/09/05 或 2026年09月05日
    m = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})', context)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # 匹配 09-05 或 09/05（无年份，用当前年）
    m = re.search(r'(\d{1,2})[-/月](\d{1,2})[日号]?', context)
    if m:
        y = datetime.now().year
        return f"{y}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"

    return datetime.now().strftime("%Y-%m-%d")


# ============ 主流程 ============
def main():
    print("=" * 60)
    print("公众号创作工作台 - 信源自动采集（智能通用版）")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"配置信源数: {len(SOURCES)}")
    print("=" * 60)

    all_sources = []
    total_updates = 0
    success_count = 0
    fail_count = 0

    for src in SOURCES:
        print(f"\n📡 正在采集: {src['name']}")
        print(f"   URL: {src['url']}")

        html = fetch_url(src["url"])
        if not html:
            print(f"   ⚠ 采集失败，跳过此信源")
            fail_count += 1
            continue

        updates = extract_links(html, src["url"])
        print(f"   ✅ 解析到 {len(updates)} 条有效动态")

        if updates:
            # 补充 time 字段
            for u in updates:
                u["time"] = datetime.now().strftime("%H:%M")
                u["summary"] = u["title"]  # 摘要暂用标题

            all_sources.append({
                "name": src["name"],
                "updates": updates,
            })
            total_updates += len(updates)
            success_count += 1
        else:
            print(f"   ℹ 未解析到有效动态（可能页面结构特殊或无相关内容）")
            fail_count += 1

        time.sleep(REQUEST_INTERVAL)  # 请求间隔，避免被封

    # 输出结果
    result = {
        "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sources": all_sources,
        "stats": {
            "total_sources": len(SOURCES),
            "success": success_count,
            "failed": fail_count,
            "total_updates": total_updates,
        }
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"采集完成！")
    print(f"  配置信源: {len(SOURCES)} 个")
    print(f"  成功: {success_count} 个")
    print(f"  失败: {fail_count} 个")
    print(f"  动态总数: {total_updates} 条")
    print(f"  输出文件: {OUTPUT_PATH}")
    print(f"  完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
