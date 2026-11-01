import argparse
import json
import os
import re
from pathlib import Path

# 匹配文件名中 ID 的正则表达式
ID_PATTERN = re.compile(r'^(?P<title>.+?)_(?P<id>\d+)$')


def build_tree(root_dir: str, pattern: str = "*.html", separator: str = "--") -> list:
    """
    用 glob 模式筛选 root_dir 中（不递归）的文件，按文件名中的 separator 构建节点 JSON 树。
    无分隔符的文件忽略。

    Args:
        root_dir (str): 要扫描的目录
        pattern (str): 文件名匹配模式，默认 "*.html"
        separator (str): 文件名中的层级分隔符，默认 "--"
    
    Returns:
        节点树的列表，每个节点代表一个笔记，包含以下键：
            - cherry_id: 表示该 HTML 文件对应的 CherryTree 笔记 ID
            - title: 节点标题
            - fpath: HTML 文件的路径
            - childs: 子节点列表

    """
    root = Path(root_dir).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"不是有效目录: {root}")

    node_map = {}
    roots = []

    # glob(pattern) 只匹配当前层，不递归；is_file() 过滤掉匹配到的子目录
    for file_path in sorted(root.glob(pattern)):
        if not file_path.is_file():
            continue

        stem, ext = os.path.splitext(file_path.name)
        parts = [p.strip() for p in stem.split(separator) if p.strip()]

        # 无分隔符的文件忽略
        if len(parts) < 2:
            continue

        last = parts[-1]
        m = ID_PATTERN.match(last)
        if m:
            last_title = m.group('title')
            node_id = int(m.group('id'))
        else:
            last_title = last
            node_id = None

        titles = parts[:-1] + [last_title]

        current_path = ()
        parent_children = roots

        for i, title in enumerate(titles):
            current_path = current_path + (title,)
            is_leaf = (i == len(titles) - 1)

            if current_path not in node_map:
                node = {
                    "cherry_id": node_id,
                    "title": title,
                    "fpath": str(file_path.as_posix()) if is_leaf else None,
                    "childs": [],
                }
                node_map[current_path] = node
                parent_children.append(node)
            else:
                node = node_map[current_path]
                if is_leaf:
                    node["cherry_id"] = node_id
                    node["fpath"] = str(file_path.as_posix())

            parent_children = node["childs"]
    print("note tree ok")

    return roots



def sort_tree(nodes: list, key: str = "title") -> list:
    """递归排序节点。key 可选 title / id / fpath。"""
    def sort_key(n):
        v = n.get(key)
        if v is None:
            return (1, "")
        if isinstance(v, int):
            return (0, v)
        return (0, str(v))

    nodes.sort(key=sort_key)
    for n in nodes:
        sort_tree(n["childs"], key)
    return nodes


def main():
    parser = argparse.ArgumentParser(
        description="按文件名中的分隔符，将目录当前层匹配 glob 的文件整理为层级 JSON（不递归子目录）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python build_tree.py
  python build_tree.py ./notes
  python build_tree.py ./notes -g "*.md" -s "__" -o out.json
  python build_tree.py ./notes --sort id
        """,
    )

    parser.add_argument("directory", nargs="?", default=".",
                        help="要扫描的目录（默认: 当前目录）")
    parser.add_argument("-g", "--glob", default="*.html", dest="glob_pattern",
                        help="文件名匹配模式（默认: *.html）")
    parser.add_argument("-s", "--separator", default="--",
                        help="文件名中的层级分隔符（默认: --）")
    parser.add_argument("-o", "--output", default="tree.json",
                        help="输出 JSON 文件路径（默认: tree.json）")
    parser.add_argument("--sort", choices=["title", "id", "fpath", "none"],
                        default="title",
                        help="子节点排序依据（默认: title；none 表示不排序）")
    parser.add_argument("--indent", type=int, default=2,
                        help="JSON 缩进空格数（默认: 2；设为 0 则紧凑输出）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只打印统计信息，不写文件")
    parser.add_argument("--version", action="version", version="%(prog)s 1.2")

    args = parser.parse_args()

    try:
        tree = build_tree(args.directory, pattern=args.glob_pattern,
                          separator=args.separator)
    except NotADirectoryError as e:
        parser.error(str(e))

    if args.sort != "none":
        sort_tree(tree, key=args.sort)

    def count_nodes(nodes):
        total = len(nodes)
        leaves = sum(1 for n in nodes if not n["childs"])
        for n in nodes:
            t, l = count_nodes(n["childs"])
            total += t
            leaves += l
        return total, leaves

    total, leaves = count_nodes(tree)

    if args.dry_run:
        print(f"[dry-run] 根节点: {len(tree)}，总节点: {total}，叶子节点: {leaves}")
        print(f"[dry-run] 未写入 {args.output}")
        return

    indent = args.indent if args.indent > 0 else None
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=indent)

    print(f"已写入 {args.output}：根节点 {len(tree)}，总节点 {total}，叶子节点 {leaves}")


if __name__ == "__main__":
    main()

