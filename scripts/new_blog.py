#!/usr/bin/env python3
"""Create a new blog post and tag it.

Usage:
    python3 scripts/new_blog.py

The script:
  1. records the current timestamp T (to the second),
  2. asks for the title H,
  3. creates blogs_src/{T}_{H}.md with "# {H}",
  4. parses Tags.md and lists every heading path (H1/H2/H3/...) as a tag,
  5. asks which tags to attach,
  6. writes a "# Tags" section with links to the matching headings,
  7. adds the post link under each matching heading in Tags.md.
"""

import os
import re
import sys
from datetime import datetime

from prompt_toolkit import prompt
from prompt_toolkit.validation import ValidationError, Validator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOGS_DIR = os.path.join(ROOT, "blogs_src")
TAGS_FILE = os.path.join(ROOT, "Tags.md")

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


class NotEmptyValidator(Validator):
    """Reject empty input."""

    def validate(self, document):
        if not document.text.strip():
            raise ValidationError(message="输入不能为空")


def slugify(text):
    """GitHub-style heading anchor."""
    text = text.strip().lower()
    # drop punctuation except word chars, spaces and hyphens
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text)
    return text


def parse_tags():
    """Return a list of dicts describing every heading in Tags.md.

    Each item: {"path": "Tech/llm", "level": 2, "title": "llm",
                "line": <index>, "slug": "anchor"}
    """
    with open(TAGS_FILE, encoding="utf-8") as f:
        lines = f.read().splitlines()

    stack = {}          # level -> title
    tags = []
    slug_counts = {}

    for idx, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()

        stack[level] = title
        # drop deeper levels
        for lv in list(stack):
            if lv > level:
                del stack[lv]

        path = "/".join(stack[lv] for lv in sorted(stack))
        slug = slugify(title)
        n = slug_counts.get(slug, 0)
        slug_counts[slug] = n + 1
        if n:
            slug = f"{slug}-{n}"

        tags.append({
            "path": path,
            "level": level,
            "title": title,
            "line": idx,
            "slug": slug,
        })

    return tags, lines


def choose_tags(tags):
    """Print tags 3 per line and let the user pick by index."""
    print("\n可用标签：")
    for i, tag in enumerate(tags, 1):
        cell = f"{i:>2}. {tag['path']}"
        print(cell.ljust(32), end="")
        if i % 3 == 0:
            print()
    if len(tags) % 3 != 0:
        print()

    raw = prompt("\n请输入要添加的标签序号（空格或逗号分隔，可留空）：").strip()
    if not raw:
        return []

    chosen = []
    for part in re.split(r"[\s,]+", raw):
        if not part:
            continue
        if not part.isdigit():
            print(f"忽略无效序号：{part}", file=sys.stderr)
            continue
        n = int(part)
        if 1 <= n <= len(tags):
            tag = tags[n - 1]
            if tag not in chosen:
                chosen.append(tag)
        else:
            print(f"忽略越界序号：{n}", file=sys.stderr)
    return chosen


def insert_into_tags(tags_file_lines, tag, blog_name, blog_rel):
    """Insert the blog link under the heading of `tag`."""
    link_line = f"- [{blog_name}]({blog_rel})"
    lines = tags_file_lines

    heading_idx = tag["line"]
    level = tag["level"]

    # find the end of this section (next heading of same or higher level)
    end = len(lines)
    for i in range(heading_idx + 1, len(lines)):
        m = HEADING_RE.match(lines[i])
        if m and len(m.group(1)) <= level:
            end = i
            break

    section = lines[heading_idx + 1:end]
    if any(blog_rel in ln for ln in section):
        return lines  # already linked

    # strip trailing blank lines of the section
    while section and section[-1].strip() == "":
        section.pop()

    section.append("")
    section.append(link_line)
    section.append("")

    return lines[:heading_idx + 1] + section + lines[end:]


def main():
    # 1. timestamp
    now = datetime.now()
    T = now.strftime("%Y-%m-%d_%H-%M-%S")

    # 2. title
    H = prompt("请输入博客标题：", validator=NotEmptyValidator()).strip()
    if not H:
        print("标题不能为空。", file=sys.stderr)
        return 1

    safe_H = H.replace("/", "-").replace("\\", "-")

    # 3. create blogs_src/{T}_{H}.md
    os.makedirs(BLOGS_DIR, exist_ok=True)
    blog_name = f"{T}_{safe_H}.md"
    blog_path = os.path.join(BLOGS_DIR, blog_name)

    # 4/5/6. title line + tag selection
    if not os.path.exists(TAGS_FILE):
        print(f"找不到 {TAGS_FILE}", file=sys.stderr)
        return 1

    tags, tags_lines = parse_tags()
    chosen = choose_tags(tags)

    # 7. write the post: title + Tags section
    content = [f"# {H}", ""]
    if chosen:
        content.append("# Tags")
        content.append("")
        for tag in chosen:
            content.append(f"[#{tag['path']}](../Tags.md#{tag['slug']})")
        content.append("")

    with open(blog_path, "w", encoding="utf-8") as f:
        f.write("\n".join(content).rstrip("\n") + "\n")

    # 8. add post link to Tags.md under each chosen tag
    blog_rel = f"blogs_src/{blog_name}"
    # re-read to keep indices valid while inserting
    for tag in chosen:
        current_tags, current = parse_tags()
        # locate the same tag in the freshly read file
        target = next((t for t in current_tags if t["path"] == tag["path"]), None)
        if target is None:
            print(f"警告：Tags.md 中找不到标签 {tag['path']}", file=sys.stderr)
            continue
        current = insert_into_tags(current, target, f"{safe_H}.md", blog_rel)
        with open(TAGS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(current) + "\n")

    print(f"\n已创建：{blog_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
