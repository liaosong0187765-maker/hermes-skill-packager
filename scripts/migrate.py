#!/usr/bin/env python3
"""
Skill Migrate — 将工作流包迁移到目标 Hermes 实例

用法:
    # 方式一：本地迁移
    python3 migrate.py --package ~/.hermes/skills/hotspot-to-wechat-workflow --target-path /tmp/export/

    # 方式二：生成可安装的 tar 包
    python3 migrate.py --package ~/.hermes/skills/hotspot-to-wechat-workflow --format tar --output /tmp/hotspot-to-wechat.tar.gz

    # 方式三：推送到 GitHub（需先 git init）
    python3 migrate.py --package ~/.hermes/skills/hotspot-to-wechat-workflow --format git --remote https://github.com/user/repo.git
"""

import os
import json
import shutil
import subprocess
import argparse
from datetime import datetime


def export_package(package_dir: str, target_path: str, include_deps: bool = False):
    """导出工作流包到目标目录"""
    package_dir = os.path.expanduser(package_dir)
    target_path = os.path.expanduser(target_path)

    if not os.path.exists(package_dir):
        print(f"❌ 工作流包不存在: {package_dir}")
        return False

    # 读取 SKILL.md 获取依赖
    skill_md = os.path.join(package_dir, "SKILL.md")
    deps = []
    if os.path.exists(skill_md):
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()
        # 简单解析 dependencies 列表
        in_deps = False
        for line in content.split("\n"):
            if "dependencies:" in line:
                in_deps = True
                continue
            if in_deps:
                if line.strip().startswith("-"):
                    dep = line.strip().lstrip("-").strip()
                    deps.append(dep)
                elif not line.startswith(" ") and line.strip():
                    in_deps = False

    # 复制工作流包
    pkg_name = os.path.basename(package_dir)
    dst = os.path.join(target_path, pkg_name)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(package_dir, dst)

    print(f"✅ 工作流包已导出: {dst}")
    print(f"   包含 skills: {pkg_name}")

    # 如果需要，同时导出依赖 skills
    if include_deps and deps:
        hermes_home = os.path.expanduser("~/.hermes")
        deps_dir = os.path.join(target_path, "_deps")
        os.makedirs(deps_dir, exist_ok=True)

        for dep in deps:
            src = os.path.join(hermes_home, "skills", dep)
            if os.path.exists(src):
                dep_dst = os.path.join(deps_dir, dep)
                if os.path.exists(dep_dst):
                    shutil.rmtree(dep_dst)
                shutil.copytree(src, dep_dst)
                print(f"   + 依赖: {dep}")

        # 写安装脚本
        install_script = f"""#!/bin/bash
# 一键安装脚本
HERMES_SKILLS="${{HOME}}/.hermes/skills"
mkdir -p "$HERMES_SKILLS"

# 安装主工作流包
cp -r "$(dirname "$0")/{pkg_name}" "$HERMES_SKILLS/"

# 安装依赖 skills
for dep_dir in "$(dirname "$0")/_deps"/*; do
    if [ -d "$dep_dir" ]; then
        dep_name=$(basename "$dep_dir")
        if [ ! -d "$HERMES_SKILLS/$dep_name" ]; then
            cp -r "$dep_dir" "$HERMES_SKILLS/"
            echo "Installed: $dep_name"
        else
            echo "Skipped (exists): $dep_name"
        fi
    fi
done

echo "Done! Workflow '{pkg_name}' installed."
"""
        with open(os.path.join(target_path, "install.sh"), "w") as f:
            f.write(install_script)
        os.chmod(os.path.join(target_path, "install.sh"), 0o755)
        print(f"   + 生成 install.sh")

    return True


def create_tar(package_dir: str, output_path: str):
    """创建 tar.gz 包"""
    package_dir = os.path.expanduser(package_dir)
    output_path = os.path.expanduser(output_path)

    pkg_name = os.path.basename(package_dir)
    parent_dir = os.path.dirname(package_dir)

    subprocess.run(
        ["tar", "czf", output_path, "-C", parent_dir, pkg_name],
        check=True
    )

    print(f"✅ Tar 包已创建: {output_path}")
    size = os.path.getsize(output_path)
    print(f"   大小: {size / 1024:.1f} KB")


def push_git(package_dir: str, remote_url: str):
    """推送到 GitHub"""
    package_dir = os.path.expanduser(package_dir)

    # 检查是否已有 git
    git_dir = os.path.join(package_dir, ".git")
    if not os.path.exists(git_dir):
        subprocess.run(["git", "init"], cwd=package_dir, check=True)
        print("✅ git init")

    # 添加所有文件
    subprocess.run(["git", "add", "."], cwd=package_dir, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"Workflow package v1.0 - {datetime.now().isoformat()}"],
        cwd=package_dir, check=True,
        capture_output=True
    )
    print("✅ git commit")

    # 设置 remote 并 push
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=package_dir, capture_output=True, text=True
    )
    if result.returncode != 0:
        subprocess.run(["git", "remote", "add", "origin", remote_url], cwd=package_dir, check=True)

    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=package_dir, check=True)
    print(f"✅ 已推送到: {remote_url}")


def diff_skills(source_home: str, target_home: str):
    """对比两个 Hermes 实例的 skills 差异"""
    source_home = os.path.expanduser(source_home)
    target_home = os.path.expanduser(target_home)

    source_skills = set(os.listdir(os.path.join(source_home, "skills")))
    target_skills = set(os.listdir(os.path.join(target_home, "skills")))

    only_in_source = source_skills - target_skills
    only_in_target = target_skills - source_skills
    in_both = source_skills & target_skills

    print(f"\n📊 Skills 差异对比")
    print(f"   源实例: {source_home} ({len(source_skills)} skills)")
    print(f"   目标实例: {target_home} ({len(target_skills)} skills)")
    print(f"")
    print(f"✅ 两边都有 ({len(in_both)}):")
    for s in sorted(in_both):
        print(f"   {s}")

    if only_in_source:
        print(f"")
        print(f"📤 仅在源实例 ({len(only_in_source)}):")
        for s in sorted(only_in_source):
            print(f"   {s}")

    if only_in_target:
        print(f"")
        print(f"📥 仅在目标实例 ({len(only_in_target)}):")
        for s in sorted(only_in_target):
            print(f"   {s}")


def main():
    parser = argparse.ArgumentParser(description="Migrate workflow packages across Hermes instances")
    parser.add_argument("--package", "-p", help="工作流包路径")
    parser.add_argument("--target-path", "-t", help="目标目录（本地迁移）")
    parser.add_argument("--format", "-f", choices=["dir", "tar", "git"], default="dir", help="导出格式")
    parser.add_argument("--output", "-o", help="输出文件路径（tar 格式）")
    parser.add_argument("--remote", "-r", help="GitHub 远程仓库 URL")
    parser.add_argument("--include-deps", action="store_true", help="同时导出依赖 skills")
    parser.add_argument("--diff", action="store_true", help="对比两个 Hermes 实例的 skills")
    parser.add_argument("--source-home", default="~/.hermes", help="源 Hermes 目录")
    parser.add_argument("--target-home", help="目标 Hermes 目录（diff 模式）")
    args = parser.parse_args()

    if args.diff:
        if not args.target_home:
            print("❌ --diff 模式需要 --target-home")
            return 1
        diff_skills(args.source_home, args.target_home)
        return 0

    if not args.package:
        print("❌ 需要 --package")
        return 1

    if args.format == "dir":
        if not args.target_path:
            print("❌ dir 格式需要 --target-path")
            return 1
        export_package(args.package, args.target_path, args.include_deps)

    elif args.format == "tar":
        if not args.output:
            print("❌ tar 格式需要 --output")
            return 1
        create_tar(args.package, args.output)

    elif args.format == "git":
        if not args.remote:
            print("❌ git 格式需要 --remote")
            return 1
        push_git(args.package, args.remote)

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
