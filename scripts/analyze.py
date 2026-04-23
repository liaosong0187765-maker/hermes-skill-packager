#!/usr/bin/env python3
"""
Skill Analyze — 分析 skills 之间的关联，推荐可组合的工作流

用法:
    python3 analyze.py --inventory /tmp/skills_inventory.json --output /tmp/workflow_suggestions.md
"""

import json
import argparse
from collections import defaultdict


# 预定义的工作流模式（关键词映射）
WORKFLOW_PATTERNS = [
    {
        "name": "热点追踪 → 公众号爆款文章",
        "description": "从信息监控到公众号文章发布的完整流水线",
        "keywords": {
            "intake": ["blogwatcher", "arxiv", "github-finder", "x-tweet-fetcher", "web-to-FIM", "url-ingest", "newsletter", "follow-builders"],
            "research": ["content-research", "article-translator", "research"],
            "writing": ["wechat-article-writer", "copywriting", "content-strategy", "article-writer"],
            "visual": ["wechat-cover", "article-to-wechat-cover", "cover-generator", "illustrator", "image"],
            "publish": ["feishu-doc-to-wechat", "wechat-article-publisher", "bm-md-formatter", "post-to-wechat"],
            "review": ["diagnose-content", "social-media-analyzer", "llm-wiki"],
        }
    },
    {
        "name": "竞品监控 → 差异化内容反击",
        "description": "监控竞品动态并快速产出反击内容",
        "keywords": {
            "intake": ["competitive-ads", "x-tweet-fetcher", "lead-research", "social-media-analyzer"],
            "strategy": ["content-marketer", "marketing-ideas", "content-strategy"],
            "writing": ["copywriting", "social-post-creator", "wechat-article-writer"],
            "visual": ["social-media-designer", "brand-designer", "canvas-design"],
            "publish": ["baoyu-post-to-x", "x-article-publisher", "markdown-to-twitter", "xiaohongshu-converter"],
            "review": ["lead-research", "diagnose-channel", "competitive-ads"],
        }
    },
    {
        "name": "英文教程 → 中文短视频",
        "description": "将英文技术内容翻译并转化为中文短视频",
        "keywords": {
            "intake": ["arxiv", "github-finder", "article-translator", "youtube-content"],
            "script": ["video-outline", "explainer-video-scripter", "script-writer", "reel-script-writer"],
            "video": ["seedance-video", "manim-video", "motion-canvas", "remotion"],
            "audio": ["doubao-tts", "moss-tts"],
            "publish": ["social-post-creator", "xiaohongshu-images", "write-xiaohongshu"],
            "review": ["diagnose-channel", "video-transcript"],
        }
    },
    {
        "name": "小红书爆款笔记工厂",
        "description": "从选题到发布的完整小红书内容生产线",
        "keywords": {
            "intake": ["blogwatcher", "x-tweet-fetcher", "xiaohongshu-note-analyzer"],
            "writing": ["write-xiaohongshu", "copywriting", "article-translator"],
            "visual": ["xiaohongshu-cover", "xiaohongshu-images", "baoyu-xhs-images", "image-enhancer"],
            "publish": ["xiaohongshu-converter", "social-post-creator"],
            "review": ["xiaohongshu-note-analyzer", "diagnose-content"],
        }
    },
    {
        "name": "多平台社媒同步发布",
        "description": "一次写作，多平台（公众号/小红书/X）同步分发",
        "keywords": {
            "writing": ["wechat-article-writer", "write-xiaohongshu", "social-post-creator", "copywriting"],
            "adapt": ["xiaohongshu-converter", "markdown-to-twitter", "article-translator"],
            "visual": ["wechat-cover", "xiaohongshu-cover", "social-media-designer"],
            "publish": ["feishu-doc-to-wechat", "baoyu-post-to-x", "xiaohongshu-converter"],
            "review": ["social-media-analyzer", "diagnose-channel"],
        }
    },
    {
        "name": "知识沉淀 → 复利资产",
        "description": "将运营经验沉淀为可复用的知识资产",
        "keywords": {
            "collect": ["llm-wiki", "url-ingest", "feishu-wiki", "obsidian"],
            "organize": ["file-organizer", "mindmap-generator", "llm-wiki"],
            "repurpose": ["content-research-writer", "wechat-article-writer", "write-xiaohongshu"],
            "visual": ["baoyu-slide-deck", "baoyu-comic", "tech-manga-explainer"],
            "review": ["opc-dashboard", "opc-asset", "diagnose-content"],
        }
    },
]


def score_skill_match(skill: dict, keywords: list) -> float:
    """计算一个 skill 与一组关键词的匹配度"""
    score = 0.0
    text = (skill.get("name", "") + " " + skill.get("description", "") + " " + " ".join(skill.get("tags", []))).lower()

    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in text:
            # 目录名完全匹配权重最高
            if kw_lower == skill.get("dir_name", "").lower():
                score += 3.0
            # 名称匹配
            elif kw_lower in skill.get("name", "").lower():
                score += 2.0
            # tag 匹配
            elif any(kw_lower in t.lower() for t in skill.get("tags", [])):
                score += 1.5
            # 描述匹配
            else:
                score += 1.0

    return score


def find_best_match(skills: list, keywords: list, threshold: float = 1.0) -> dict:
    """从 skills 列表中找到与关键词最匹配的一个"""
    best = None
    best_score = 0

    for skill in skills:
        score = score_skill_match(skill, keywords)
        if score > best_score and score >= threshold:
            best_score = score
            best = skill

    return {"skill": best, "score": best_score} if best else None


def analyze_workflows(inventory: dict) -> list:
    """分析所有预定义工作流模式的匹配情况"""
    all_skills = inventory.get("all_skills", [])
    results = []

    for pattern in WORKFLOW_PATTERNS:
        workflow = {
            "name": pattern["name"],
            "description": pattern["description"],
            "steps": {},
            "matched_skills": [],
            "missing_steps": [],
            "coverage": 0.0,
        }

        total_steps = len(pattern["keywords"])
        matched_steps = 0

        for step_name, keywords in pattern["keywords"].items():
            match = find_best_match(all_skills, keywords, threshold=0.5)
            if match:
                workflow["steps"][step_name] = {
                    "skill": match["skill"]["dir_name"],
                    "name": match["skill"]["name"],
                    "description": match["skill"]["description"],
                    "location": match["skill"]["location"],
                    "score": round(match["score"], 1),
                }
                workflow["matched_skills"].append(match["skill"]["dir_name"])
                matched_steps += 1
            else:
                workflow["missing_steps"].append({
                    "step": step_name,
                    "suggested_keywords": keywords,
                })

        workflow["coverage"] = round(matched_steps / total_steps * 100, 1) if total_steps > 0 else 0
        workflow["ready"] = matched_steps == total_steps
        results.append(workflow)

    # 按覆盖率排序
    results.sort(key=lambda x: x["coverage"], reverse=True)
    return results


def to_markdown(workflows: list) -> str:
    """转为 Markdown 报告"""
    lines = [
        "# 工作流建议报告",
        "",
        f"基于当前系统的 skills 分析，共发现 {len(workflows)} 种可组合的工作流：",
        "",
    ]

    for i, wf in enumerate(workflows, 1):
        status = "✅ 可立即运行" if wf["ready"] else f"⚠️ 覆盖率 {wf['coverage']}%"
        lines.extend([
            f"## {i}. {wf['name']} — {status}",
            "",
            f"> {wf['description']}",
            "",
            "### 步骤与匹配 Skills",
            "",
        ])

        for step_name, step_info in wf["steps"].items():
            loc = step_info["location"]
            loc_badge = "[主]" if loc == "main" else f"[{loc}]"
            lines.append(f"- **{step_name}** → `{step_info['skill']}` {loc_badge} (匹配度: {step_info['score']})")

        if wf["missing_steps"]:
            lines.extend([
                "",
                "### 缺失步骤",
                "",
            ])
            for miss in wf["missing_steps"]:
                lines.append(f"- **{miss['step']}** — 建议安装匹配关键词: {', '.join(miss['suggested_keywords'][:3])}")

        if wf["matched_skills"]:
            lines.extend([
                "",
                "### 一键打包命令",
                "",
            ])
            skills_str = ",".join(wf["matched_skills"])
            lines.append(f"```bash")
            lines.append(f"python3 scripts/packager.py \\")
            lines.append(f"  --name '{wf['name'].replace(' ', '-').lower()}' \\")
            lines.append(f"  --skills '{skills_str}' \\")
            lines.append(f"  --description '{wf['description']}'")
            lines.append(f"```")

        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze skills and suggest workflow combinations")
    parser.add_argument("--inventory", "-i", required=True, help="Path to skills_inventory.json")
    parser.add_argument("--output", "-o", required=True, help="Output file path")
    parser.add_argument("--format", "-f", choices=["json", "markdown"], default="markdown", help="Output format")
    args = parser.parse_args()

    with open(args.inventory, "r", encoding="utf-8") as f:
        inventory = json.load(f)

    print(f"🔍 分析 {inventory['statistics']['total_unique']} 个 skills 的工作流组合...")
    workflows = analyze_workflows(inventory)

    ready_count = sum(1 for w in workflows if w["ready"])
    print(f"✅ 发现 {len(workflows)} 种工作流模式")
    print(f"✅ 其中 {ready_count} 种可以立即运行（100% 覆盖）")

    if args.format == "json":
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(workflows, f, ensure_ascii=False, indent=2)
    else:
        md = to_markdown(workflows)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)

    print(f"✅ 输出: {args.output}")


if __name__ == "__main__":
    main()
