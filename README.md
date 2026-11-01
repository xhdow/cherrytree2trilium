# cherry2trilium

Batch-import notes exported from CherryTree (HTML) into Trilium Notes: cleans the HTML, rebuilds the folder hierarchy from file names, uploads images and fixes their links.

## Requirements

- Python 3.10 or newer

## Dependencies

```
beautifulsoup4   HTML parsing
requests         HTTP requests
regex            regular expressions
```

Install:

```bash
pip install beautifulsoup4 requests regex
```

## Configuration

In Trilium open **Options → ETAPI → Create new ETAPI token**, create one and copy it, then set it as an environment variable:

```powershell
# PowerShell
$env:TRILIUM_API_KEY  = "your-token"
$env:TRILIUM_BASE_URL = "http://127.0.0.1:37840/etapi/"   # optional, this is the default
```

```bash
# Linux / macOS
export TRILIUM_API_KEY="your-token"
export TRILIUM_BASE_URL="http://127.0.0.1:37840/etapi/"   # optional
```

Verify the configuration:

```bash
python main.py doctor
```

## Usage

### 1. Export from CherryTree

`File → Export → Export to HTML`. Exported files are named like `Parent--Child--Note_123.html`.

### 2. Import

```bash
# import a whole directory
python main.py i_dir ./export --pid root

# import a single file
python main.py i_html ./export/MyNotes--Python_12.html --pid root
```

Notes can be imported under **any existing note tree node** in Trilium. `--pid` is the ID of that node and defaults to `root` (the tree root). You can find a note ID in the browser address bar or via *Note actions → Info*.

## Commands

| Command | Description |
|---|---|
| `i_dir <dir> [--pid ID]` | Import a directory as a note tree |
| `i_html <file> [--pid ID] [--title TITLE]` | Import a single HTML file |
| `c_note <title> <content> [--pid ID] [--type TYPE]` | Create a note; use `@path` as content to read it from a file |
| `u_note <note_id> <content>` | Update a note's content |
| `c_atm <file> [--owner NOTE_ID]` | Upload a file as an attachment |
| `clean <input> <output>` | Clean a single HTML export |
| `relevel --root <dir> [--nodry]` | Split `A--B--C.html` into folders (preview only by default) |
| `tree <dir> [-o out.json]` | Preview the note tree structure |
| `doctor` | Check the Trilium connection and credentials |

All commands support `-q` (quiet) and `-v` (verbose). For the full options of a command:

```bash
python main.py i_dir --help
```
