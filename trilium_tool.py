import requests
import argparse
import json
import cherry_tool
import cherry_tree
from bs4 import BeautifulSoup as bsp
import os


config = {
    "base_url": "http://127.0.0.1:37840/etapi/",
    "api_key": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}




def create_note(title,content,pid="root",type="text"):
    '''创建笔记  
        title: 笔记标题  
        content: 笔记内容。@fpath 可用于引用文件。
        pid: 父笔记ID  
        type: 笔记类型

        returns: 创建成功返回笔记ID，失败返回None
    '''
    jdata = {
        "title": title,
        "content": content,
        "parentNoteId": pid,
        "type": type
    }
   
    #如果 content 以 @ 开头，则将其作为文件路径读取内容
    if content.startswith("@"):
        fpath = content[1:]
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                jdata["content"] = f.read()
        except Exception as e:
            print("读取文件失败:",fpath,e)
            return None
   

    rsp=requests.post(config["base_url"]+"create-note",
                      json=jdata,
                      headers={"Authorization": "Bearer "+config["api_key"]}
                      )
    if rsp.status_code!=201:
        print("创建笔记失败:",rsp.status_code,rsp.text)
        return None
    note_id=rsp.json()["note"]["noteId"]
    print(f"创建笔记成功: note_id={note_id}")    
    return note_id

def create_attachment(fpath,owner="root"):
    '''创建附件  
        fpath: 文件路径  
        owner: 附件所有者ID  
    '''
    #try read file
    try:
        with open(fpath,"rb") as f:
            f_data=f.read()
    except Exception as e:
        print("读取附件文件失败:",fpath,e)
        return None
    
    # get file mime
    import mimetypes
    mime_type, _ = mimetypes.guess_type(fpath)
    
    # 先创建一个附件记录
    j_data_1={
        "ownerId": owner,
        "role":"image",
        "mime": mime_type,
        "title": fpath.split("/")[-1]
    }
    rsp=requests.post(config["base_url"]+"attachments",json=j_data_1,headers={"Authorization": "Bearer "+config["api_key"]})
    if rsp.status_code!=201:
        print("创建占位附件失败:",rsp.status_code,rsp.text)
        return None
    print("创建占位附件成功:",rsp.json())

    # 写入附件内容
    attachment_id=rsp.json()["attachmentId"]
    
    rsp2=requests.put(config["base_url"]+f"attachments/{attachment_id}/content",
                     data=f_data,
                     headers={"Authorization": "Bearer "+config["api_key"],
                              "Content-Type": "application/octet-stream"}
                     )
    if rsp2.status_code!=204:
        print("写入附件内容失败:",rsp2.status_code,rsp2.text)
        return None
    print("写入附件内容成功:",attachment_id)
    
    return attachment_id


def update_note(note_id, content=None):
    '''更新笔记  
        note_id: 笔记ID  
        content: 笔记内容。@fpath 可用于引用文件。
    '''

    # 如果 content 以 @ 开头，则将其作为文件路径读取内容
    if content.startswith("@"):
        fpath = content[1:]
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print("读取文件失败:", fpath, e)
            return None
    
    rsp=requests.put(config["base_url"]+f"notes/{note_id}/content",
                     data=content,
                     headers={"Authorization": "Bearer "+config["api_key"],
                              "Content-Type": "text/plain"}
                        )
    if rsp.status_code!=204:
        print("更新笔记失败:",rsp.status_code,rsp.text)
        return None
    print("更新笔记成功:",note_id)
    return note_id




def import_html(fin:str,pid:str="root",title:str=None):
    '''导入HTML文件为 Trillium 笔记  
        fin: 单个 HTML文件路径。
        pid: 父笔记ID  
        title: 笔记标题，如果为None，则使用HTML文件名作为标题
        returns: 创建成功返回 [note_id,img_count,img_uploaded_count]，失败返回None
    '''
    if not fin:
        print(f"--err-[import_html] fin is None, pid={pid}")
        return None,0,0
    
    if not pid:
        print(f"--err-[import_html] pid is None")
        return None,0,0
    
    if title is None:
        title=os.path.splitext(os.path.basename(fin))[0]
    
    # 确保有一个临时目录，用来存放清理后的HTML文件
    temp_dir = os.path.join(os.path.dirname(fin), "temp")
    os.makedirs(temp_dir, exist_ok=True)


    # 获得干净的的 HTML 内容，并将其写入临时文件
    cleaned_html = cherry_tool.clean_html(fin, os.path.join(temp_dir, "step1_"+os.path.basename(fin)))
    html_content=cleaned_html    # 使用清理后的 HTML 内容
    
    # 先创建一个空笔记进行占位
    note_id = create_note(title, "to be updated", pid=pid)
    if not note_id:
        return None,0,0
    
    # 遍历HTML内容中的 <img> 标签，上传图片为附件，获得附件 ID，並替换 img.src 为附件 URL
    soup = bsp(html_content, "html.parser")

    img_count = 0             #HTML中图片的数量
    img_uploaded_count = 0    #上传附件成功的数量
    for img in soup.find_all("img"):
        img_src = img.get("src")
        img_count += 1
        if not img_src:
            continue

        # 如果 src 是相对路径，则转换为相对于 HTML 文件的绝对路径
        img_path = os.path.join(os.path.dirname(fin), img_src)
        print(f"[i_html]正在上传图片[{img_count}]: {img_path}")
        if not os.path.exists(img_path):
            print(f"[i_html]图片文件不存在: {img_path}")
            continue
        # 上传图片为附件
        attachment_id = create_attachment(img_path, owner=note_id)
        if not attachment_id:
            print(f"[i_html]上传图片失败: {img_path}")
            continue
        # 替换 <img> 标签的 src 为附件 URL
        img["src"] = f"api/attachments/{attachment_id}/image/image.png"
        img_uploaded_count += 1

    # 将修改后的 HTML 内容作为笔记内容更新
    html_content2 = str(soup)

    # 将修改后的 HTML 保存到一个临时文件中，以便调试
    temp_html_path = os.path.join(temp_dir, f"step2_{os.path.basename(fin)}")
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(html_content2)

    update_note(note_id, html_content2)    
    print(f"[i_html]导入HTML完成: note_id={note_id}, 图片总数={img_count}, 成功上传图片数={img_uploaded_count}")
    
    return note_id, img_count, img_uploaded_count


def walk_tree(nodes: list, depth: int = 0, stat=None):
    """
    深度优先前序遍历节点树，保证父节点先于子节点被访问。
    注意：当调用此函数时，第一层 node 必须已经拿到 pid（父笔记 ID）属性。

    Args:
        nodes (list): build_tree() 返回的顶层节点列表
        depth (int): 当前层级，用于打印缩进，外部调用保持默认 0
        stat: (dict): 统计信息。  
            stat['finished'] - int  己处理完成的节点数
    """
    stat={'finished':0} if not stat else stat

    for node in nodes:
        # 先处理当前节点（从上到下的“上”）
        print(f"{"{0:5d}".format(stat["finished"])}  {'****' * depth}{node['title']} (id={node.get('cherry_id')})")

        if node['fpath']:
            # 创建新笔记
            try:
                new_note_id,_,_=import_html(node['fpath'],node['pid'],node['title'])
            except Exception as e:
                print(e)
                with open("import_progress.json",'wb',encoding="utf-8") as f:
                    json.dump(nodes,indent=4)
                
        else:
            # 如果 fpath 为空，说明这是顶层虚拟节点，直接忽略这层，把 pid 透传到下层去
            new_note_id=node['pid']
        node['done']=1   #表示此节点己处理完了
        stat['finished']+=1   
        
        for node_2 in node['childs']:
            node_2['pid']=new_note_id
        
        # 再递归处理子节点（从上到下的“下”）
        walk_tree(node.get("childs", []), depth + 1,stat=stat)


def import_html_from_dir(root_dir:str,pid:str="root",glob="*.html"):
    '''导入目录下的所有 HTML 文件为 Trillium 笔记。
        具体规划：
        1. 调用 cherry_tree.build_tree() 将目录下的 HTML 文件组织成 JSON 格式的节点树（每个节点代表一个笔记）。
        2. 以此节点树为参考，在 Trillium 中创建笔记（树）
        Args:
            root_dir: HTML文件所在目录  
            pid: 父笔记ID  
            glob: 文件匹配模式，默认 "*.html"
    '''

    nodes:list =cherry_tree.build_tree(root_dir)
    for node_x in nodes:
        node_x['pid']=pid
    walk_tree(nodes,0)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Trillium Tool")
    
    #subcommand: create_note
    subparsers = parser.add_subparsers(dest="command", help="Subcommands: c_note，c_atm")
    subparsers.required = True

    # Arguments for create_note subcommand
    create_note_parser = subparsers.add_parser("c_note", help="Create a note in Trillium")
    create_note_parser.add_argument("title", type=str, help="Title of the note")
    create_note_parser.add_argument("content", type=str, help="note content. Use @filepath to reference a file.")
    create_note_parser.add_argument("--pid", type=str, default="root", help="Parent ID of the note (default: root)")
    create_note_parser.add_argument("--type", type=str, default="text", help="Type of the note (default: text)")

    # Arguments for create_attachment subcommand
    create_attachment_parser = subparsers.add_parser("c_atm", help="Create an attachment in Trillium")
    create_attachment_parser.add_argument("fpath", type=str, help="File path of the attachment")
    create_attachment_parser.add_argument("--owner", type=str, default="root", help="Owner ID of the attachment (default: root)")           

    # Arguments for update_note subcommand
    update_note_parser = subparsers.add_parser("u_note", help="Update a note in Trillium")
    update_note_parser.add_argument("note_id", type=str, help="ID of the note to update")
    update_note_parser.add_argument("content", type=str, help="New content for the note. Use @filepath to reference a file.")   
      
    # Arguments for import_html subcommand
    import_html_parser = subparsers.add_parser("i_html", help="Import an HTML file as a Trillium note")
    import_html_parser.add_argument("fin", type=str, help="Input HTML file path")
    import_html_parser.add_argument("--pid", type=str, default="root", help="Parent ID of the note (default: root)")
    import_html_parser.add_argument("--title", type=str, default=None, help="Title of the note (default: use HTML file name)")

   # Arguments for import_html_dir subcommand
    import_html_dir_parser = subparsers.add_parser("i_dir", help="Import an HTML dir into Trillium note")
    import_html_dir_parser.add_argument("fin", type=str, help="Input HTML dir")
    import_html_dir_parser.add_argument("--pid", type=str, default="root", help="Parent ID of the note (default: root)")
    

    args = parser.parse_args()

    if args.command == "create_note":
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
    
    


