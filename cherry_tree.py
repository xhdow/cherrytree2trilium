import argparse
import json
import os
import re
from pathlib import Path

from log_util import get_logger

# Shared logger for this module.
log = get_logger("cherry_tree")

# Regular expression matching the note ID in a file name.
ID_PATTERN = re.compile(r'^(?P<title>.+?)_(?P<id>\d+)$')


def build_tree(root_dir: str, pattern: str = "*.html", separator: str = "--") -> list:
    """
    Select the files of root_dir (non-recursive) with a glob pattern and build
    a node JSON tree from the separator used in the file names.
    Files without the separator are ignored.

    Args:
        root_dir (str): The directory to scan.
        pattern (str): The file name pattern, defaults to "*.html".
        separator (str): The hierarchy separator in file names, defaults to "--".

    Returns:
        A list of node trees. Each node represents one note and contains:
            - cherry_id: the CherryTree note ID of the corresponding HTML file
            - title: the node title
            - fpath: the path of the HTML file
            - childs: the list of child nodes

    """
    root = Path(root_dir).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"not a valid directory: {root}")

    node_map = {}
    roots = []

    # glob(pattern) only matches the current level (non-recursive);
    # is_file() filters out matched sub-directories.
    for file_path in sorted(root.glob(pattern)):
        if not file_path.is_file():
            continue

        stem, ext = os.path.splitext(file_path.name)
        parts = [p.strip() for p in stem.split(separator) if p.strip()]

        # Ignore files without the separator.
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
    log.debug("note tree ready: %d root node(s)", len(roots))

    return roots



def sort_tree(nodes: list, key: str = "title") -> list:
    """Recursively sort the nodes. key can be title / id / fpath."""
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
        description="Build a hierarchical JSON from the files of the current directory "
                    "level that match the glob pattern, based on the separator in the file names "
                    "(sub-directories are not scanned).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cherry_tree.py
  python cherry_tree.py ./notes
  python cherry_tree.py ./notes -g "*.md" -s "__" -o out.json
  python cherry_tree.py ./notes --sort id
        """,
    )

    parser.add_argument("directory", nargs="?", default=".",
                        help="Directory to scan (default: current directory)")
    parser.add_argument("-g", "--glob", default="*.html", dest="glob_pattern",
                        help="File name pattern (default: *.html)")
    parser.add_argument("-s", "--separator", default="--",
                        help="Hierarchy separator in file names (default: --)")
    parser.add_argument("-o", "--output", default="tree.json",
                        help="Output JSON file path (default: tree.json)")
    parser.add_argument("--sort", choices=["title", "id", "fpath", "none"],
                        default="title",
                        help="Child sort key (default: title; none means no sorting)")
    parser.add_argument("--indent", type=int, default=2,
                        help="JSON indentation (default: 2; 0 for compact output)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only print statistics, do not write the file")
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
        log.info("[dry-run] root nodes: %d, total nodes: %d, leaf nodes: %d",
                 len(tree), total, leaves)
        log.info("[dry-run] %s was not written", args.output)
        return

    indent = args.indent if args.indent > 0 else None
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=indent)

    log.info("wrote %s: root nodes: %d, total nodes: %d, leaf nodes: %d",
             args.output, len(tree), total, leaves)


if __name__ == "__main__":
    main()
