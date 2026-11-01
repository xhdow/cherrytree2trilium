"""
Unified command line interface for the cherrytree-to-Trilium tools.

The commands simply forward to the functions of the existing modules; the
import logic itself is unchanged.

Subcommands:
    clean    Clean a CherryTree HTML export
    relevel  Organize flat HTML files into hierarchical directories
    tree     Build the note tree JSON from file names
    doctor   Check the connection and credentials of Trilium
    c_note   Create a note
    c_atm    Create an attachment
    u_note   Update a note
    i_html   Import an HTML file as a note
    i_dir    Import a directory of HTML files as a note tree
"""

import argparse
import json
import logging
import os
import sys

import cherry_tool
import cherry_tree
import trilium_tool
from log_util import get_logger

# Shared logger for this module.
log = get_logger("main")

#: Version of the whole toolset.
__version__ = "1.1"


def _add_common_args(parser):
    """Add the logging options shared by every subcommand."""
    group = parser.add_argument_group("logging")
    group.add_argument("-q", "--quiet", action="store_true",
                       help="Only show warnings and errors")
    group.add_argument("-v", "--verbose", action="store_true",
                       help="Show debug messages")


def _apply_logging(args):
    """Apply the -q / -v logging options of the parsed arguments."""
    level = logging.DEBUG if args.verbose else logging.INFO
    if args.quiet:
        level = logging.WARNING
    logging.getLogger().setLevel(level)
    for name in ("main", "cherry_tool", "cherry_tree", "trilium_tool"):
        logging.getLogger(name).setLevel(level)


def build_parser():
    """Create the top level argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="cherry2trilium",
        description="Import notes exported from CherryTree into Trilium.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py clean ./export/Notes_1.html ./cleaned.html
  python main.py relevel --root ./export
  python main.py relevel --root ./export --nodry
  python main.py tree ./export -o tree.json
  python main.py doctor
  python main.py i_html ./export/Notes--Python_12.html --pid root
  python main.py i_dir ./export --pid root
        """,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    # ---- HTML tools -------------------------------------------------
    clean_parser = subparsers.add_parser("clean", help="Clean a CherryTree HTML export")
    clean_parser.add_argument("fin", type=str, help="Input HTML file path")
    clean_parser.add_argument("fout", type=str, help="Output HTML file path")
    _add_common_args(clean_parser)
    clean_parser.set_defaults(func=_cmd_clean)

    relevel_parser = subparsers.add_parser(
        "relevel", help="Organize files by separator into hierarchical directories")
    relevel_parser.add_argument("--sep", type=str, default="--",
                                help="Separator for organizing files (default: '--')")
    relevel_parser.add_argument("--nodry", action="store_true",
                                help="No dry run, actually move files (default: dry run)")
    relevel_parser.add_argument("--root", type=str, default=".",
                                help="Root directory (default: current directory)")
    relevel_parser.add_argument("--glob", type=str, default="*.html",
                                help="Glob pattern of the files to organize (default: '*.html')")
    _add_common_args(relevel_parser)
    relevel_parser.set_defaults(func=_cmd_relevel)

    tree_parser = subparsers.add_parser("tree",
                                        help="Build the note tree JSON from file names")
    tree_parser.add_argument("directory", nargs="?", default=".",
                             help="Directory to scan (default: current directory)")
    tree_parser.add_argument("-g", "--glob", default="*.html", dest="glob_pattern",
                             help="File name pattern (default: *.html)")
    tree_parser.add_argument("-s", "--separator", default="--",
                             help="Hierarchy separator in file names (default: --)")
    tree_parser.add_argument("-o", "--output", default="tree.json",
                             help="Output JSON file path (default: tree.json)")
    tree_parser.add_argument("--sort", choices=["title", "id", "fpath", "none"],
                             default="title",
                             help="Child sort key (default: title; none means no sorting)")
    tree_parser.add_argument("--indent", type=int, default=2,
                             help="JSON indentation (default: 2; 0 for compact output)")
    tree_parser.add_argument("--dry-run", action="store_true",
                             help="Only print statistics, do not write the file")
    _add_common_args(tree_parser)
    tree_parser.set_defaults(func=_cmd_tree)

    # ---- Trilium tools ----------------------------------------------
    doctor_parser = subparsers.add_parser(
        "doctor", help="Check the connection and credentials of Trilium")
    _add_common_args(doctor_parser)
    doctor_parser.set_defaults(func=_cmd_doctor)

    note_parser = subparsers.add_parser("c_note", help="Create a note in Trilium")
    note_parser.add_argument("title", type=str, help="Title of the note")
    note_parser.add_argument("content", type=str,
                             help="note content. Use @filepath to reference a file.")
    note_parser.add_argument("--pid", type=str, default="root",
                             help="Parent ID of the note (default: root)")
    note_parser.add_argument("--type", type=str, default="text",
                             help="Type of the note (default: text)")
    _add_common_args(note_parser)
    note_parser.set_defaults(func=_cmd_create_note)

    attach_parser = subparsers.add_parser("c_atm", help="Create an attachment in Trilium")
    attach_parser.add_argument("fpath", type=str, help="File path of the attachment")
    attach_parser.add_argument("--owner", type=str, default="root",
                               help="Owner ID of the attachment (default: root)")
    _add_common_args(attach_parser)
    attach_parser.set_defaults(func=_cmd_create_attachment)

    update_parser = subparsers.add_parser("u_note", help="Update a note in Trilium")
    update_parser.add_argument("note_id", type=str, help="ID of the note to update")
    update_parser.add_argument("content", type=str,
                               help="New content for the note. Use @filepath to reference a file.")
    _add_common_args(update_parser)
    update_parser.set_defaults(func=_cmd_update_note)

    html_parser = subparsers.add_parser("i_html", help="Import an HTML file as a Trilium note")
    html_parser.add_argument("fin", type=str, help="Input HTML file path")
    html_parser.add_argument("--pid", type=str, default="root",
                             help="Parent ID of the note (default: root)")
    html_parser.add_argument("--title", type=str, default=None,
                             help="Title of the note (default: use HTML file name)")
    _add_common_args(html_parser)
    html_parser.set_defaults(func=_cmd_import_html)

    dir_parser = subparsers.add_parser("i_dir",
                                       help="Import a directory of HTML files as a note tree")
    dir_parser.add_argument("fin", type=str, help="Input HTML dir")
    dir_parser.add_argument("--pid", type=str, default="root",
                            help="Parent ID of the note (default: root)")
    _add_common_args(dir_parser)
    dir_parser.set_defaults(func=_cmd_import_dir)

    return parser


# --------------------------------------------------------------------------
# Command handlers: thin wrappers around the existing functions.
# --------------------------------------------------------------------------
def _cmd_clean(args):
    """Clean a single HTML file."""
    cherry_tool.clean_html(args.fin, args.fout)
    log.info("cleaned %s -> %s", args.fin, args.fout)
    return 0


def _cmd_relevel(args):
    """Organize flat HTML files into hierarchical directories."""
    cherry_tool.organize_files_by_separator(
        root_dir=args.root,
        glob=args.glob,
        separator=args.sep,
        dry_run=not args.nodry,
    )
    return 0


def _cmd_tree(args):
    """Build the note tree JSON from file names."""
    # Same steps as cherry_tree.main(), called directly so the "--" default
    # separator is not mistaken for an option terminator by argparse.
    try:
        tree = cherry_tree.build_tree(args.directory, pattern=args.glob_pattern,
                                      separator=args.separator)
    except NotADirectoryError as e:
        log.error("%s", e)
        return 1

    if args.sort != "none":
        cherry_tree.sort_tree(tree, key=args.sort)

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
        return 0

    indent = args.indent if args.indent > 0 else None
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=indent)

    log.info("wrote %s: root nodes: %d, total nodes: %d, leaf nodes: %d",
             args.output, len(tree), total, leaves)
    return 0


def _cmd_doctor(args):
    """Check that Trilium is reachable with the configured credentials."""
    url = trilium_tool.config["base_url"] + "app-info"
    log.info("checking %s (base_url: %s)", trilium_tool.config["base_url"],
             _config_source("TRILIUM_BASE_URL"))
    log.info("api_key: %s (%s)", _mask_secret(trilium_tool.config["api_key"]),
             _config_source("TRILIUM_API_KEY"))
    import requests
    try:
        rsp = requests.get(url, headers={"Authorization": "Bearer " + trilium_tool.config["api_key"]})
    except requests.RequestException as e:
        log.error("cannot reach Trilium: %s", e)
        return 1
    if rsp.status_code != 200:
        log.error("connection check failed (HTTP %s): %s", rsp.status_code, rsp.text)
        return 1
    info = rsp.json()
    log.info("connection OK (Trilium version: %s)", info.get("appVersion", "unknown"))
    return 0


def _config_source(env_name):
    """Describe where a connection setting comes from."""
    if os.environ.get(env_name, "").strip():
        return f"from ${env_name}"
    return "built-in default"


def _mask_secret(value):
    """Return a masked version of a secret so it can be shown in logs."""
    if not value:
        return "<empty>"
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def _cmd_create_note(args):
    """Create a note."""
    trilium_tool.create_note(args.title, args.content, args.pid, args.type)
    return 0


def _cmd_create_attachment(args):
    """Create an attachment."""
    trilium_tool.create_attachment(args.fpath, args.owner)
    return 0


def _cmd_update_note(args):
    """Update a note."""
    trilium_tool.update_note(args.note_id, args.content)
    return 0


def _cmd_import_html(args):
    """Import a single HTML file as a note."""
    trilium_tool.import_html(args.fin, args.pid, args.title)
    return 0


def _cmd_import_dir(args):
    """Import a directory of HTML files as a note tree."""
    trilium_tool.import_html_from_dir(args.fin, args.pid)
    return 0


def main(argv=None):
    """Run the CLI and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    _apply_logging(args)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
