from bs4 import BeautifulSoup as bsp
import shutil
from pathlib import Path
import os,regex as re

from log_util import get_logger

# Shared logger for this module.
log = get_logger("cherry_tool")


def clean_html(fin: str, fout: str) -> str:
    '''
    Cleans the HTML file.
    - delete:
        - meta[name="generator"]
        - link
        - script
        - empty <h5> <h4> <h3> <h2> <h1> tags
    - translate:
        - div[class="codebox"] as <code>
        - local <a> href as "cherry:node_<id>"

    Args:
        fin (str): The path to the input HTML file.
        fout (str): The path to the output HTML file.

    Returns:
        str: The cleaned HTML content.
    '''
    with open(fin, "r", encoding="utf-8") as f:
        html_content = f.read()

    soup = bsp(html_content, "html.parser")

    # Delete meta[name="generator"]
    for meta in soup.find_all("meta", attrs={"name": "generator"}):
        meta.decompose()

    # Delete link tags
    for link in soup.find_all("link"):
        link.decompose()

    # Delete script tags
    for script in soup.find_all("script"):
        script.decompose()

    # Delete empty <h5> tags
    for h in soup.find_all("h5"):
        if not h.get_text().strip():
            h.decompose()

    # Delete empty <h4> tags
    for h4 in soup.find_all("h4"):
        if not h4.get_text().strip():
            h4.decompose()

    # Delete empty <h3> tags
    for h3 in soup.find_all("h3"):
        if not h3.get_text().strip():
            h3.decompose()

    # Delete empty <h2> tags
    for h2 in soup.find_all("h2"):
        if not h2.get_text().strip():
            h2.decompose()

    # Delete empty <h1> tags
    for h1 in soup.find_all("h1"):
        if not h1.get_text().strip():
            h1.decompose()

    # Turn div[class="codebox"] into <code>
    for div in soup.find_all("div", attrs={"class": "codebox"}):
        div.name = "code"

    '''
    # Translate local <a> href as "cherry:node_<id>"
    eg: href="mynote--Python--pip--requests_1414.html"
    the note id is 1414, so the href should be "cherry:node_1414"
    ---
    Anchor format: <a name="SSL"></a>
    '''
    for a in soup.find_all("a"):
        href = a.get("href","")

        # Remove anchors: the element is empty and carries no content.
        if not a.getText().strip():
            a.decompose()

        # if href  regex match the pattern "_\d+\.html" at the end, then extract the id
        m=re.search(r'_(\d+)\.html$', href)
        if m:
            note_id = m.group(1)
            a["href"] = f"cherry:node_{note_id}"


    # Write the cleaned HTML to the output file
    with open(fout, "w", encoding="utf-8") as f:
        f.write(str(soup))

    return str(soup)

def organize_files_by_separator(root_dir: str = ".",glob="*.html", separator: str = "--", dry_run: bool = False):
    """
    Organize the files in the current directory into a hierarchical directory
    structure based on the separator in their file names. Files whose names
    contain no separator are skipped.

    For example:
        mynote--scripts--Markdown--Latex--JLatexMath_2128.html
    is moved to:
        mynote/scripts/Markdown/Latex/JLatexMath_2128.html

    Args:
        root_dir: The root directory to process; defaults to the current directory.
        glob: The file pattern to process; defaults to "*.html".
        separator: The separator used in file names; defaults to "--".
        dry_run: When True, only print the plan without moving any file.
    """
    root = Path(root_dir).resolve()

    for file_path in root.glob(glob):
        # Process files only, skip directories.
        if not file_path.is_file():
            continue

        # Split a file name such as "a--b--c.txt".
        name = file_path.name
        stem, ext = os.path.splitext(name)  # Separate the stem and the extension.

        parts = [p.strip() for p in stem.split(separator) if p.strip()]
        if len(parts) < 2:
            # No separator found, skip this file.
            log.info("[skip] no separator: %s", name)
            continue

        # The last part becomes the file name, the others become directories.
        *dir_parts, file_stem = parts
        target_dir = root.joinpath(*dir_parts)
        target_path = target_dir / f"{file_stem}{ext}"

        if dry_run:
            log.info("[plan] %s  ->  %s", file_path.relative_to(root), target_path.relative_to(root))
            continue

        target_dir.mkdir(parents=True, exist_ok=True)

        # Avoid overwriting an existing file with the same name.
        if target_path.exists():
            base, suffix = os.path.splitext(target_path.name)
            i = 1
            while target_path.exists():
                target_path = target_dir / f"{base}_{i}{suffix}"
                i += 1

        shutil.move(str(file_path), str(target_path))
        log.info("[move] %s  ->  %s", file_path.relative_to(root), target_path.relative_to(root))

# Command line arguments
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clean HTML file.")
    #add subcommand for organizing files
    subparsers = parser.add_subparsers(dest="command", help="Subcommands: clean or relevel")
    subparsers.required = True

    # Subcommand for cleaning HTML
    clean_parser = subparsers.add_parser("clean", help="Clean HTML file")
    clean_parser.add_argument("fin", type=str, help="Input HTML file path")
    clean_parser.add_argument("fout", type=str, help="Output HTML file path")

    # Subcommand for organizing files
    organize_parser = subparsers.add_parser("relevel", help="reorganize files by separator into hierarchical directories")
    organize_parser.add_argument("--sep", type=str, default="--", help="Separator for organizing files (default: '--')")
    organize_parser.add_argument("--nodry", action="store_true", help="No dry run, actually move files (default: dry run)")
    organize_parser.add_argument("--root", type=str, default=".", help="Root directory for organizing files (default: current directory)")
    organize_parser.add_argument("--glob", type=str, default="*.html", help="Glob pattern for files to organize (default: '*.html')")
    args = parser.parse_args()

    if args.command == "relevel":
        organize_files_by_separator(
            root_dir=args.root  ,
            glob=args.glob,
            separator=args.sep,
            dry_run=not args.nodry
        )
    elif args.command == "clean":
        clean_html(args.fin, args.fout)
    else:
        parser.print_help()
