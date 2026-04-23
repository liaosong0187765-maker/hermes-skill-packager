#!/usr/bin/env python3
"""
Skill Discover — 扫描系统中所有 skills，生成全景清单

用法:
    python3 discover.py --output /tmp/skills_inventory.json
    python3 discover.py --format markdown --output /tmp/skills_inventory.md
"""

import os
import json
import re
import argparse
from pathlib import Path
from datetime import datetime


def extract_skill_metadata(skill_path: str) -> dict:
    """读取 SKILL.md 提取元数据"""
    skill_md = os.path.join(skill_path, "SKILL.md")
    if not os.path.exists(skill_md):
        return None

    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read(3000)

    # 提取 frontmatter
    fm_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    frontmatter = fm_match.group(1) if fm_match else ""

    # 提取字段
    def extract_field(pattern, text, default=""):
        m = re.search(pattern, text, re.MULTILINE | re.DOTALL)
        return m.group(1).strip().replace('\n', ' ') if m else default

    name = extract_field(r'^name:\s*(.+)', frontmatter)
    desc = extract_field(r'^description:\s*(.+)', frontmatter)
    version = extract_field(r'^version:\s*(.+)', frontmatter, "0.0.0")
    author = extract_field(r'^author:\s*(.+)', frontmatter)

    # 提取 tags
    tags = []
    tags_match = re.search(r'tags:\s*\[(.*?)\]', frontmatter, re.DOTALL)
    if tags_match:
        tags_raw = tags_match.group(1)
        tags = [t.strip().strip('"').strip("'") for t in tags_raw.split(',') if t.strip()]

    # 提取 body 第一行作为补充描述
    body = content[len(fm_match.group(0)) if fm_match else 0:]
    lines = [l.strip() for l in body.split('\n') if l.strip() and not l.strip().startswith('#')]
    summary = lines[0][:150] if lines else ""

    # 检查是否有 scripts/
    has_scripts = os.path.isdir(os.path.join(skill_path, "scripts"))

    # 检查是否有 requirements.txt
    has_requirements = os.path.exists(os.path.join(skill_path, "requirements.txt"))

    return {
        "name": name or os.path.basename(skill_path),
        "dir_name": os.path.basename(skill_path),
        "description": desc or summary,
        "version": version,
        "author": author,
        "tags": tags,
        "has_scripts": has_scripts,
        "has_requirements": has_requirements,
    }


def scan_skills_directory(skills_dir: str, location_label: str) -> list:
    """扫描一个 skills 目录"""
    results = []
    if not os.path.isdir(skills_dir):
        return results

    for name in sorted(os.listdir(skills_dir)):
        path = os.path.join(skills_dir, name)
        if not os.path.isdir(path) or name.startswith("."):
            continue

        meta = extract_skill_metadata(path)
        if meta:
            meta["location"] = location_label
            meta["full_path"] = path
            results.append(meta)

    return results


def build_inventory(hermes_home: str = "~/.hermes") -> dict:
    """构建完整的 skills 清单"""
    hermes_home = os.path.expanduser(hermes_home)

    inventory = {
        "generated_at": datetime.now().isoformat(),
        "hermes_home": hermes_home,
        "sources": {},
        "all_skills": [],
        "duplicates": [],
        "statistics": {},
    }

    # 扫描主 skills
    main_dir = os.path.join(hermes_home, "skills")
    main_skills = scan_skills_directory(main_dir, "main")
    inventory["sources"]["main"] = {
        "path": main_dir,
        "count": len(main_skills),
        "skills": [s["dir_name"] for s in main_skills],
    }
    inventory["all_skills"].extend(main_skills)

    # 扫描各 profile
    profiles_dir = os.path.join(hermes_home, "profiles")
    if os.path.isdir(profiles_dir):
        for profile_name in sorted(os.listdir(profiles_dir)):
            profile_skills_dir = os.path.join(profiles_dir, profile_name, "skills")
            if os.path.isdir(profile_skills_dir):
                profile_skills = scan_skills_directory(profile_skills_dir, f"profile:{profile_name}")
                inventory["sources"][profile_name] = {
                    "path": profile_skills_dir,
                    "count": len(profile_skills),
                    "skills": [s["dir_name"] for s in profile_skills],
                }
                inventory["all_skills"].extend(profile_skills)

    # 计算重复
    name_to_locations = {}
    for s in inventory["all_skills"]:
        name = s["dir_name"]
        if name not in name_to_locations:
            name_to_locations[name] = []
        name_to_locations[name].append(s["location"])

    for name, locations in name_to_locations.items():
        if len(locations) > 1:
            inventory["duplicates"].append({
                "name": name,
                "locations": locations,
                "copies": len(locations),
            })

    # 统计
    inventory["statistics"] = {
        "total_unique": len(name_to_locations),
        "total_copies": len(inventory["all_skills"]),
        "duplicate_count": len(inventory["duplicates"]),
        "duplicate_skills": [d["name"] for d in inventory["duplicates"]],
        "main_only": [s["dir_name"] for s in main_skills if s["dir_name"] not in [d["name"] for d in inventory["duplicates"]]],
    }

    return inventory


def to_markdown(inventory: dict) -> str:
    """转为 Markdown 报告"""
    lines = [
        "# Skills 全景清单",
        f"",
        f"生成时间: {inventory['generated_at']}",
        f"",
        "## 统计",
        f"",
        f"- 唯一 skills: **{inventory['statistics']['total_unique']}**",
        f"- 总副本数: **{inventory['statistics']['total_copies']}**",
        f"- 重复 skills: **{inventory['statistics']['duplicate_count']}**",
        f"",
        "## 重复 Skills",
        f"",
    ]

    for dup in inventory["duplicates"]:
        lines.append(f"- `{dup['name']}` — 出现在: {', '.join(dup['locations'])}")

    lines.extend([
        f"",
        "## 所有 Skills 列表",
        f"",
    ])

    # 按位置分组
    by_location = {}
    for s in inventory["all_skills"]:
        loc = s["location"]
        if loc not in by_location:
            by_location[loc] = []
        by_location[loc].append(s)

    for loc, skills in sorted(by_location.items()):
        lines.append(f"### {loc} ({len(skills)})")
        lines.append("")
        for s in skills:
            tags_str = ", ".join(s['tags']) if s['tags'] else ""
            lines.append(f"- **{s['dir_name']}** | {s['description'][:80]} | tags: `{tags_str}`")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Discover all skills in the Hermes system")
    parser.add_argument("--output", "-o", required=True, help="Output file path")
    parser.add_argument("--format", "-f", choices=["json", "markdown"], default="json", help="Output format")
    parser.add_argument("--hermes-home", default="~/.hermes", help="Hermes home directory")
    args = parser.parse_args()

    print(f"🔍 扫描 skills 目录: {args.hermes_home}")
    inventory = build_inventory(args.hermes_home)

    if args.format == "json":
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(inventory, f, ensure_ascii=False, indent=2)
    else:
        md = to_markdown(inventory)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)

    print(f"✅ 发现 {inventory['statistics']['total_unique']} 个唯一 skills")
    print(f"✅ 总副本: {inventory['statistics']['total_copies']}")
    print(f"✅ 重复: {inventory['statistics']['duplicate_count']} 个")
    print(f"✅ 输出: {args.output}")


if __name__ == "__main__":
    main()
