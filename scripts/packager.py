#!/usr/bin/env python3
"""
Skill Packager — 将一组 skills 打包成可迁移的工作流包

用法:
    python3 packager.py \
      --name "hotspot-to-wechat" \
      --skills "blogwatcher,wechat-article-writer,wechat-title-generator,article-to-wechat-cover,bm-md-formatter,feishu-doc-to-wechat-draft" \
      --description "热点追踪到公众号爆款文章的完整流水线" \
      --output ~/.hermes/skills/hotspot-to-wechat-workflow \
      --hermes-home ~/.hermes
"""

import os
import sys
import json
import re
import shutil
import argparse
from pathlib import Path

# 引入 verify 模块做前置核验
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
from verify import verify_workflow


RUN_PY_TEMPLATE = '''#!/usr/bin/env python3
r"""
__WORKFLOW_NAME__ — 工作流编排执行器

用法:
    python3 run.py --topic "AI Agent 最新进展"
    python3 run.py --config workflow_config.json
"""

import os
import sys
import json
import argparse

# 加载依赖检查
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_deps import check_dependencies

HERMES_HOME = os.path.expanduser("~/.hermes")


def run_step(step_name: str, skill_name: str, args: dict):
    """执行一个工作流步骤"""
    print(f"\\n{'='*60}")
    print(f"▶ Step: {step_name}")
    print(f"  Skill: {skill_name}")
    print(f"{'='*60}")

    skill_path = os.path.join(HERMES_HOME, "skills", skill_name)
    if not os.path.exists(skill_path):
        # 尝试在 profile 中查找
        profiles_dir = os.path.join(HERMES_HOME, "profiles")
        if os.path.isdir(profiles_dir):
            for profile in os.listdir(profiles_dir):
                alt_path = os.path.join(profiles_dir, profile, "skills", skill_name)
                if os.path.exists(alt_path):
                    skill_path = alt_path
                    break

    if not os.path.exists(skill_path):
        print(f"❌ Skill not found: {skill_name}")
        return False

    # 查找执行入口
    run_script = os.path.join(skill_path, "scripts", "run.py")
    if os.path.exists(run_script):
        print(f"  执行: {run_script}")
        # 这里可以扩展为实际调用
        # os.system(f"cd {skill_path} && python3 {run_script} ...")
        return True

    print(f"  ℹ️  Skill {skill_name} 需要手动调用")
    return True


def main():
    parser = argparse.ArgumentParser(description="__WORKFLOW_NAME__")
    parser.add_argument("--topic", "-t", help="工作流主题/输入")
    parser.add_argument("--config", "-c", help="配置文件路径")
    parser.add_argument("--dry-run", action="store_true", help="只显示步骤，不执行")
    args = parser.parse_args()

    print("🚀 启动工作流: __WORKFLOW_NAME__")
    print("📋 描述: __WORKFLOW_DESCRIPTION__")

    # 检查依赖
    deps_ok, missing, _found = check_dependencies()
    if not deps_ok:
        print(f"\\n⚠️  缺失依赖 skills: {missing}")
        print("   运行: python3 install_deps.py")
        return 1

    # 工作流步骤定义
    steps = __STEPS_JSON__

    print(f"\\n📊 共 {len(steps)} 个步骤")

    if args.dry_run:
        print("\\n🔍 [DRY RUN] 步骤预览:")
        for i, (step_name, skill_name) in enumerate(steps.items(), 1):
            print(f"  {i}. {step_name} → {skill_name}")
        return 0

    # 执行步骤
    for step_name, skill_name in steps.items():
        if not run_step(step_name, skill_name, vars(args)):
            print(f"\\n❌ 工作流在步骤 '{step_name}' 中断")
            return 1

    print("\\n✅ 工作流执行完成!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


CHECK_DEPS_TEMPLATE = '''#!/usr/bin/env python3
"""检查工作流依赖的 skills 是否已安装"""

import os
import json

HERMES_HOME = os.path.expanduser("~/.hermes")
DEPENDENCIES = {deps_json}


def check_dependencies():
    """检查所有依赖 skills 是否存在"""
    missing = []
    found = []

    for dep in DEPENDENCIES:
        # 检查主 skills 目录
        main_path = os.path.join(HERMES_HOME, "skills", dep)
        if os.path.exists(main_path):
            found.append(dep)
            continue

        # 检查各 profile
        found_in_profile = False
        profiles_dir = os.path.join(HERMES_HOME, "profiles")
        if os.path.isdir(profiles_dir):
            for profile in os.listdir(profiles_dir):
                profile_path = os.path.join(profiles_dir, profile, "skills", dep)
                if os.path.exists(profile_path):
                    found.append(f"{{dep}} (profile: {{profile}})")
                    found_in_profile = True
                    break

        if not found_in_profile:
            missing.append(dep)

    return len(missing) == 0, missing, found


def main():
    ok, missing, found = check_dependencies()

    print("📦 依赖检查报告")
    print(f"\\n✅ 已安装 ({{len(found)}}):")
    for f in found:
        print(f"  • {{f}}")

    if missing:
        print(f"\\n❌ 缺失 ({{len(missing)}}):")
        for m in missing:
            print(f"  • {{m}}")
        print("\\n💡 运行: python3 install_deps.py 自动安装")
    else:
        print("\\n🎉 所有依赖已就绪!")

    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
'''


INSTALL_DEPS_TEMPLATE = '''#!/usr/bin/env python3
"""自动安装缺失的依赖 skills"""

import os
import subprocess
import json

HERMES_HOME = os.path.expanduser("~/.hermes")
DEPENDENCIES = {deps_json}

# 已知 GitHub 仓库映射（可根据需要扩展）
GITHUB_MAP = {{
    "blogwatcher": "NousResearch/hermes-agent/tree/main/skills/research/blogwatcher",
    "url-ingest-llmwiki": "NousResearch/hermes-agent/tree/main/skills/research/url-ingest-llmwiki",
    "feishu-doc-to-wechat-draft": "dracohu2025-cloud/draco-skills-collection/tree/main/feishu-doc-to-wechat-draft",
    "wechat-article-writer": "dracohu2025-cloud/skills/tree/main/wechat-article-writer",
    "wechat-title-generator": "dracohu2025-cloud/skills/tree/main/wechat-title-generator",
    "wechat-cover-generator": "dracohu2025-cloud/skills/tree/main/wechat-cover-generator",
    "article-to-wechat-cover": "dracohu2025-cloud/draco-skills-collection/tree/main/article-to-wechat-cover",
    "bm-md-formatter": "dracohu2025-cloud/skills/tree/main/bm-md-formatter",
    "write-xiaohongshu": "dracohu2025-cloud/skills/tree/main/write-xiaohongshu",
    "xiaohongshu-cover-generator": "dracohu2025-cloud/skills/tree/main/xiaohongshu-cover-generator",
    "xiaohongshu-images": "dracohu2025-cloud/skills/tree/main/xiaohongshu-images",
    "content-research-writer": "dracohu2025-cloud/skills/tree/main/content-research-writer",
    "copywriting": "dracohu2025-cloud/skills/tree/main/copywriting",
    "competitive-ads-extractor": "dracohu2025-cloud/skills/tree/main/competitive-ads-extractor",
    "lead-research-assistant": "dracohu2025-cloud/skills/tree/main/lead-research-assistant",
    "social-post-creator": "dracohu2025-cloud/skills/tree/main/social-post-creator",
    "diagnose-content-system": "NousResearch/hermes-agent/tree/main/skills/diagnose-content-system",
    "diagnose-channel-and-traffic": "NousResearch/hermes-agent/tree/main/skills/diagnose-channel-and-traffic",
    "llm-wiki": "NousResearch/hermes-agent/tree/main/skills/research/llm-wiki",
    "feishu-wiki": "NousResearch/hermes-agent/tree/main/skills/feishu-wiki",
}}


def install_skill(skill_name: str) -> bool:
    """安装一个 skill"""
    print(f"\\n📥 安装 {{skill_name}}...")

    # 检查是否已在本地存在
    main_path = os.path.join(HERMES_HOME, "skills", skill_name)
    if os.path.exists(main_path):
        print(f"  ✅ 已存在: {{main_path}}")
        return True

    # 尝试从 GitHub 安装
    github_path = GITHUB_MAP.get(skill_name)
    if github_path:
        # 解析仓库路径
        parts = github_path.split("/tree/main/")
        if len(parts) == 2:
            repo = parts[0]
            subdir = parts[1]
            url = f"https://github.com/{{repo}}.git"
            print(f"  从 {{url}} 克隆...")
            # 先 clone 到临时目录，再拷贝子目录
            tmp_dir = f"/tmp/magicskills_install_{{skill_name}}"
            try:
                subprocess.run(["rm", "-rf", tmp_dir], check=False)
                subprocess.run(["git", "clone", "--depth", "1", url, tmp_dir], check=True, capture_output=True)
                src = os.path.join(tmp_dir, subdir)
                if os.path.exists(src):
                    dst = os.path.join(HERMES_HOME, "skills", skill_name)
                    shutil.copytree(src, dst)
                    print(f"  ✅ 安装成功: {{dst}}")
                    return True
                else:
                    print(f"  ❌ 子目录不存在: {{src}}")
            except Exception as e:
                print(f"  ❌ 安装失败: {{e}}")
        else:
            print(f"  ⚠️  无法解析 GitHub 路径: {{github_path}}")
    else:
        print(f"  ⚠️  未知来源，请手动安装: {{skill_name}}")

    return False


def main():
    import shutil

    print("🚀 安装工作流依赖 skills")
    print(f"   共 {{len(DEPENDENCIES)}} 个依赖")

    success = 0
    failed = []

    for dep in DEPENDENCIES:
        if install_skill(dep):
            success += 1
        else:
            failed.append(dep)

    print(f"\\n" + "="*50)
    print(f"✅ 成功: {{success}}/{{len(DEPENDENCIES)}}")
    if failed:
        print(f"❌ 失败 ({{len(failed)}}):")
        for f in failed:
            print(f"  • {{f}}")
        print("\\n💡 请手动安装失败的 skills")
        return 1

    print("\\n🎉 所有依赖安装完成!")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
'''


def extract_skill_step_mapping(skills: list, workflow_name: str) -> dict:
    """根据工作流名称，推断 skills 对应步骤"""
    # 简单的关键词映射
    step_keywords = {
        "intake": ["blogwatcher", "github-finder", "x-tweet-fetcher", "arxiv", "url-ingest", "newsletter", "follow-builders", "web-to-FIM"],
        "research": ["content-research", "article-translator", "research"],
        "writing": ["wechat-article-writer", "write-xiaohongshu", "copywriting", "article-writer"],
        "title": ["wechat-title-generator", "title-generator"],
        "visual": ["cover", "illustrator", "image", "designer", "slide", "comic"],
        "publish": ["feishu-doc-to-wechat", "publisher", "post-to", "formatter", "converter"],
        "review": ["diagnose", "analyzer", "llm-wiki", "dashboard"],
    }

    steps = {}
    assigned = set()

    for step_name, keywords in step_keywords.items():
        for skill_name in skills:
            if skill_name in assigned:
                continue
            skill_lower = skill_name.lower()
            for kw in keywords:
                if kw.lower() in skill_lower:
                    steps[step_name] = skill_name
                    assigned.add(skill_name)
                    break

    # 剩余的放其他
    for skill_name in skills:
        if skill_name not in assigned:
            steps[f"tool_{skill_name}"] = skill_name

    return steps


def build_skill_md(name: str, description: str, skills: list, steps: dict) -> str:
    """生成工作流包的 SKILL.md"""
    deps_yaml = "\n".join([f"  - {s}" for s in skills])
    steps_yaml = "\n".join([f"  {k}: {v}" for k, v in steps.items()])

    return f"""---
name: {name}
description: "{description}"
version: 1.0.0
author: Skill Packager
dependencies:
{deps_yaml}
---

# {name}

{description}

## 触发词

- "跑{name.replace('-', ' ')}"
- "执行 {name}"

## 工作流步骤

{steps_yaml}

## 依赖安装

```bash
python3 check_deps.py   # 检查依赖
python3 install_deps.py # 自动安装缺失的 skills
```

## 运行

```bash
python3 run.py --topic "你的主题"
```
"""


def package_workflow(args):
    """打包工作流"""
    output_dir = os.path.expanduser(args.output)
    skills = [s.strip() for s in args.skills.split(",")]

    # 推断步骤映射
    steps = extract_skill_step_mapping(skills, args.name)

    # 创建目录结构
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "scripts"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "references"), exist_ok=True)

    # 1. 写 SKILL.md
    skill_md = build_skill_md(args.name, args.description, skills, steps)
    with open(os.path.join(output_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(skill_md)

    # 2. 写 run.py
    deps_json = json.dumps(skills, ensure_ascii=False, indent=2)
    steps_json = json.dumps(steps, ensure_ascii=False, indent=2)
    run_py = (
        RUN_PY_TEMPLATE
        .replace("__WORKFLOW_NAME__", args.name)
        .replace("__WORKFLOW_DESCRIPTION__", args.description)
        .replace("__STEPS_JSON__", steps_json)
    )
    with open(os.path.join(output_dir, "scripts", "run.py"), "w", encoding="utf-8") as f:
        f.write(run_py)
    os.chmod(os.path.join(output_dir, "scripts", "run.py"), 0o755)

    # 3. 写 check_deps.py
    check_deps = CHECK_DEPS_TEMPLATE.format(deps_json=deps_json)
    with open(os.path.join(output_dir, "scripts", "check_deps.py"), "w", encoding="utf-8") as f:
        f.write(check_deps)

    # 4. 写 install_deps.py
    install_deps = INSTALL_DEPS_TEMPLATE.format(deps_json=deps_json)
    with open(os.path.join(output_dir, "scripts", "install_deps.py"), "w", encoding="utf-8") as f:
        f.write(install_deps)

    # 5. 复制依赖 skills 的引用文档（可选）
    hermes_home = os.path.expanduser(args.hermes_home)
    for skill_name in skills:
        src_refs = os.path.join(hermes_home, "skills", skill_name, "references")
        if os.path.isdir(src_refs):
            dst_refs = os.path.join(output_dir, "references", skill_name)
            shutil.copytree(src_refs, dst_refs, dirs_exist_ok=True)

    print(f"✅ 工作流包已创建: {output_dir}")
    print(f"   Skills: {len(skills)} 个")
    print(f"   步骤: {len(steps)} 个")
    print(f"")
    print(f"📋 文件结构:")
    for root, dirs, files in os.walk(output_dir):
        level = root.replace(output_dir, '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            print(f"{subindent}{file}")

    print(f"")
    print(f"🚀 使用方法:")
    print(f"   cd {output_dir}")
    print(f"   python3 scripts/check_deps.py")
    print(f"   python3 scripts/install_deps.py")
    print(f"   python3 scripts/run.py --dry-run")


def main():
    parser = argparse.ArgumentParser(description="Package skills into a workflow")
    parser.add_argument("--name", "-n", required=True, help="工作流包名称")
    parser.add_argument("--skills", "-s", required=True, help="逗号分隔的 skills 列表")
    parser.add_argument("--description", "-d", required=True, help="工作流描述")
    parser.add_argument("--output", "-o", required=True, help="输出目录")
    parser.add_argument("--hermes-home", default="~/.hermes", help="Hermes home 目录")
    parser.add_argument("--skip-verify", action="store_true", help="跳过前置核验（不推荐）")
    parser.add_argument("--verify-strict", action="store_true", help="严格核验模式（警告也视为失败）")
    args = parser.parse_args()

    skill_names = [s.strip() for s in args.skills.split(",")]

    # 前置核验
    if not args.skip_verify:
        print("🔍 打包前核验 skills...")
        report = verify_workflow(skill_names, strict=args.verify_strict)
        if not report["can_package"]:
            print("\n❌ 核验未通过，终止打包。")
            if not args.verify_strict and report.get("warnings", 0) > 0 and report.get("errors", 0) == 0:
                print("💡 提示: 只有警告无错误，可用 --skip-verify 跳过（不推荐）")
            return 1
        print("\n✅ 核验通过，开始打包...\n")
    else:
        print("⚠️ 已跳过前置核验（不推荐）\n")

    package_workflow(args)


if __name__ == "__main__":
    main()
