import requests
import argparse
import json
import cherry_tool
import cherry_tree
from bs4 import BeautifulSoup as bsp
import os

from log_util import get_logger

# Shared logger for this module.
log = get_logger("trilium_tool")


#: Default ETAPI root URL, used when TRILIUM_BASE_URL is not set.
DEFAULT_BASE_URL = "http://127.0.0.1:37840/etapi/"

#: Default ETAPI token, used when TRILIUM_API_KEY is not set.
DEFAULT_API_KEY = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"


def load_config():
    '''
    Build the Trilium connection settings.

    The values are taken from the environment variables below; the constants
    above are used as a fallback when a variable is missing or empty.

        TRILIUM_BASE_URL: ETAPI root URL. A trailing "/" is added when missing.
        TRILIUM_API_KEY: ETAPI token.

    Returns:
        dict: A dict with the keys "base_url" and "api_key".
    '''
    base_url = os.environ.get("TRILIUM_BASE_URL", "").strip() or DEFAULT_BASE_URL
    if not base_url.endswith("/"):
        base_url += "/"

    api_key = os.environ.get("TRILIUM_API_KEY", "").strip() or DEFAULT_API_KEY

    return {
        "base_url": base_url,
        "api_key": api_key,
    }


config = load_config()



def create_note(title,content,pid="root",type="text"):
    '''Create a note.
        title: note title
        content: note content. @fpath can be used to reference a file.
        pid: parent note ID
        type: note type

        returns: the note ID on success, None on failure
    '''
    jdata = {
        "title": title,
        "content": content,
        "parentNoteId": pid,
        "type": type
    }

    # If content starts with @, treat the rest as a file path and read it.
    if content.startswith("@"):
        fpath = content[1:]
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                jdata["content"] = f.read()
        except Exception as e:
            log.error("failed to read file %s: %s", fpath, e)
            return None


    rsp=requests.post(config["base_url"]+"create-note",
                      json=jdata,
                      headers={"Authorization": "Bearer "+config["api_key"]}
                      )
    if rsp.status_code!=201:
        log.error("failed to create note (HTTP %s): %s", rsp.status_code, rsp.text)
        return None
    note_id=rsp.json()["note"]["noteId"]
    log.debug("note created: id=%s", note_id)
    return note_id

def create_attachment(fpath,owner="root"):
    '''Create an attachment.
        fpath: file path
        owner: owner ID of the attachment
    '''
    #try read file
    try:
        with open(fpath,"rb") as f:
            f_data=f.read()
    except Exception as e:
        log.error("failed to read attachment file %s: %s", fpath, e)
        return None

    # get file mime
    import mimetypes
    mime_type, _ = mimetypes.guess_type(fpath)

    # Create the attachment record first.
    j_data_1={
        "ownerId": owner,
        "role":"image",
        "mime": mime_type,
        "title": fpath.split("/")[-1]
    }
    rsp=requests.post(config["base_url"]+"attachments",json=j_data_1,headers={"Authorization": "Bearer "+config["api_key"]})
    if rsp.status_code!=201:
        log.error("failed to create attachment placeholder (HTTP %s): %s", rsp.status_code, rsp.text)
        return None
    log.debug("attachment placeholder created: %s", rsp.json())

    # Write the attachment content.
    attachment_id=rsp.json()["attachmentId"]

    rsp2=requests.put(config["base_url"]+f"attachments/{attachment_id}/content",
                     data=f_data,
                     headers={"Authorization": "Bearer "+config["api_key"],
                              "Content-Type": "application/octet-stream"}
                     )
    if rsp2.status_code!=204:
        log.error("failed to write attachment content (HTTP %s): %s", rsp2.status_code, rsp2.text)
        return None
    log.debug("attachment content written: %s", attachment_id)

    return attachment_id


def update_note(note_id, content=None):
    '''Update a note.
        note_id: note ID
        content: note content. @fpath can be used to reference a file.
    '''

    # If content starts with @, treat the rest as a file path and read it.
    if content.startswith("@"):
        fpath = content[1:]
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            log.error("failed to read file %s: %s", fpath, e)
            return None

    rsp=requests.put(config["base_url"]+f"notes/{note_id}/content",
                     data=content,
                     headers={"Authorization": "Bearer "+config["api_key"],
                              "Content-Type": "text/plain"}
                        )
    if rsp.status_code!=204:
        log.error("failed to update note (HTTP %s): %s", rsp.status_code, rsp.text)
        return None
    log.debug("note updated: %s", note_id)
    return note_id




def import_html(fin:str,pid:str="root",title:str=None):
    '''Import an HTML file as a Trilium note.
        fin: a single HTML file path.
        pid: parent note ID
        title: note title; when None, the HTML file name is used as title
        returns: [note_id,img_count,img_uploaded_count] on success, None on failure
    '''
    if not fin:
        log.error("[import_html] fin is None, pid=%s", pid)
        return None,0,0

    if not pid:
        log.error("[import_html] pid is None")
        return None,0,0

    if title is None:
        title=os.path.splitext(os.path.basename(fin))[0]

    # Make sure a temporary directory exists to hold the cleaned HTML files.
    temp_dir = os.path.join(os.path.dirname(fin), "temp")
    os.makedirs(temp_dir, exist_ok=True)


    # Get the cleaned HTML content and write it to a temporary file.
    cleaned_html = cherry_tool.clean_html(fin, os.path.join(temp_dir, "step1_"+os.path.basename(fin)))
    html_content=cleaned_html    # Use the cleaned HTML content.

    # Create an empty note first as a placeholder.
    note_id = create_note(title, "to be updated", pid=pid)
    if not note_id:
        return None,0,0

    # Walk the <img> tags of the HTML content, upload each image as an
    # attachment, get its attachment ID and replace img.src with the
    # attachment URL.
    soup = bsp(html_content, "html.parser")

    img_count = 0             #Number of images in the HTML.
    img_uploaded_count = 0    #Number of successfully uploaded attachments.
    for img in soup.find_all("img"):
        img_src = img.get("src")
        img_count += 1
        if not img_src:
            continue

        # If src is a relative path, resolve it against the HTML file.
        img_path = os.path.join(os.path.dirname(fin), img_src)
        log.debug("[i_html] uploading image [%d/%d]: %s", img_count, img_count, img_path)
        if not os.path.exists(img_path):
            log.warning("[i_html] image file not found: %s", img_path)
            continue
        # Upload the image as an attachment.
        attachment_id = create_attachment(img_path, owner=note_id)
        if not attachment_id:
            log.warning("[i_html] failed to upload image: %s", img_path)
            continue
        # Replace the src of the <img> tag with the attachment URL.
        img["src"] = f"api/attachments/{attachment_id}/image/image.png"
        img_uploaded_count += 1

    # Update the note with the modified HTML content.
    html_content2 = str(soup)

    # Save the modified HTML to a temporary file for debugging.
    temp_html_path = os.path.join(temp_dir, f"step2_{os.path.basename(fin)}")
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(html_content2)

    update_note(note_id, html_content2)
    log.info("[i_html] HTML imported: note_id=%s, images=%d, uploaded=%d",
             note_id, img_count, img_uploaded_count)

    return note_id, img_count, img_uploaded_count


def walk_tree(nodes: list, depth: int = 0, stat=None):
    """
    Traverse the node tree depth-first in pre-order so that every parent is
    visited before its children.
    Note: when this function is called, the first level of nodes must already
    have the pid (parent note ID) attribute.

    Args:
        nodes (list): the top level node list returned by build_tree()
        depth (int): the current level, used for indentation; keep the default
            0 when calling from outside
        stat: (dict): statistics.
            stat['finished'] - int  number of processed nodes
    """
    stat={'finished':0} if not stat else stat

    for node in nodes:
        # Process the current node first (the "top" of the top-down traversal).
        log.info("%5d  %s%s (id=%s)", stat["finished"],
                 '****' * depth, node['title'], node.get('cherry_id'))

        if node['fpath']:
            # Create a new note.
            try:
                new_note_id,_,_=import_html(node['fpath'],node['pid'],node['title'])
            except Exception as e:
                log.error("%s", e)
                with open("import_progress.json",'w',encoding="utf-8") as f:
                    json.dump(nodes,indent=4)

        else:
            # If fpath is empty this is a top level virtual node: skip this
            # level and pass the parent ID down to the children.
            new_note_id=node['pid']
        node['done']=1   #Mark this node as processed.
        stat['finished']+=1

        for node_2 in node['childs']:
            node_2['pid']=new_note_id

        # Then recurse into the children (the "bottom" of the top-down traversal).
        walk_tree(node.get("childs", []), depth + 1,stat=stat)


def import_html_from_dir(root_dir:str,pid:str="root",glob="*.html"):
    '''Import all HTML files of a directory as Trilium notes.
        Plan:
        1. Call cherry_tree.build_tree() to organize the HTML files of the
           directory into a JSON node tree (each node represents one note).
        2. Use that node tree as a reference to create the notes (tree) in Trilium.
        Args:
            root_dir: the directory containing the HTML files
            pid: parent note ID
            glob: file matching pattern, defaults to "*.html"
    '''

    nodes:list =cherry_tree.build_tree(root_dir)
    for node_x in nodes:
        node_x['pid']=pid
    walk_tree(nodes,0)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Trilium Tool")

    #subcommand: create_note
    subparsers = parser.add_subparsers(dest="command", help="Subcommands: c_note, c_atm, u_note, i_html, i_dir")
    subparsers.required = True

    # Arguments for create_note subcommand
    create_note_parser = subparsers.add_parser("c_note", help="Create a note in Trilium")
    create_note_parser.add_argument("title", type=str, help="Title of the note")
    create_note_parser.add_argument("content", type=str, help="note content. Use @filepath to reference a file.")
    create_note_parser.add_argument("--pid", type=str, default="root", help="Parent ID of the note (default: root)")
    create_note_parser.add_argument("--type", type=str, default="text", help="Type of the note (default: text)")

    # Arguments for create_attachment subcommand
    create_attachment_parser = subparsers.add_parser("c_atm", help="Create an attachment in Trilium")
    create_attachment_parser.add_argument("fpath", type=str, help="File path of the attachment")
    create_attachment_parser.add_argument("--owner", type=str, default="root", help="Owner ID of the attachment (default: root)")

    # Arguments for update_note subcommand
    update_note_parser = subparsers.add_parser("u_note", help="Update a note in Trilium")
    update_note_parser.add_argument("note_id", type=str, help="ID of the note to update")
    update_note_parser.add_argument("content", type=str, help="New content for the note. Use @filepath to reference a file.")

    # Arguments for import_html subcommand
    import_html_parser = subparsers.add_parser("i_html", help="Import an HTML file as a Trilium note")
    import_html_parser.add_argument("fin", type=str, help="Input HTML file path")
    import_html_parser.add_argument("--pid", type=str, default="root", help="Parent ID of the note (default: root)")
    import_html_parser.add_argument("--title", type=str, default=None, help="Title of the note (default: use HTML file name)")

    # Arguments for import_html_dir subcommand
    import_html_dir_parser = subparsers.add_parser("i_dir", help="Import an HTML dir into Trilium note")
    import_html_dir_parser.add_argument("fin", type=str, help="Input HTML dir")
    import_html_dir_parser.add_argument("--pid", type=str, default="root", help="Parent ID of the note (default: root)")


    args = parser.parse_args()

    if args.command == "c_note":
        create_note(args.title, args.content, args.pid, args.type)
    elif args.command == "c_atm":
        create_attachment(args.fpath, args.owner)
    elif args.command == "u_note":
        update_note(args.note_id, args.content)
    elif args.command == "i_html":
        import_html(args.fin, args.pid, args.title)
    elif args.command=="i_dir":
        import_html_from_dir(args.fin,args.pid)
    else:
        parser.print_help()
