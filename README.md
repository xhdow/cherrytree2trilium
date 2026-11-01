# cherry2trilium

将 CherryTree 导出的 HTML 笔记批量导入 Trilium Notes：自动清理 HTML、按文件名还原目录层级、上传图片并修正图片链接。

## 运行环境

- Python 3.10 及以上

## 依赖库

```
beautifulsoup4   解析 HTML
requests         HTTP 请求
regex            正则匹配
```

安装：

```bash
pip install beautifulsoup4 requests regex
```

## 配置

在 Trilium 中打开 **Options → ETAPI → Create new ETAPI token**，创建并复制 token，然后设置为环境变量：

```powershell
# PowerShell
$env:TRILIUM_API_KEY  = "你的-token"
$env:TRILIUM_BASE_URL = "http://127.0.0.1:37840/etapi/"   # 可选，默认值即此
```

```bash
# Linux / macOS
export TRILIUM_API_KEY="你的-token"
export TRILIUM_BASE_URL="http://127.0.0.1:37840/etapi/"   # 可选
```

验证配置：

```bash
python main.py doctor
```

## 使用

### 1. 从 CherryTree 导出

`文件 → 导出 → 导出为 HTML`。导出文件形如 `父级--子级--笔记_123.html`。

### 2. 导入

```bash
# 导入整个目录
python main.py i_dir ./export --pid root

# 导入单个文件
python main.py i_html ./export/我的笔记--Python_12.html --pid root
```

导入目标可以是 Trilium 中**任意一个已存在的笔记树节点**。`--pid` 即该节点的 ID，默认值为 `root`（笔记树根节点）。节点 ID 可从浏览器地址栏或 *笔记操作 → 信息* 中查看。

## 命令

| 命令 | 说明 |
|---|---|
| `i_dir <目录> [--pid ID]` | 导入整个目录为笔记树 |
| `i_html <文件> [--pid ID] [--title 标题]` | 导入单个 HTML 文件 |
| `c_note <标题> <内容> [--pid ID] [--type 类型]` | 创建笔记，内容写 `@文件路径` 可从文件读取 |
| `u_note <笔记ID> <内容>` | 更新笔记内容 |
| `c_atm <文件> [--owner 笔记ID]` | 上传文件作为附件 |
| `clean <输入文件> <输出文件>` | 清理单个 HTML 导出文件 |
| `relevel --root <目录> [--nodry]` | 按 `A--B--C.html` 拆分为目录结构（默认仅预览） |
| `tree <目录> [-o 输出.json]` | 预览笔记树结构 |
| `doctor` | 检查 Trilium 连接和凭据 |

所有命令均支持 `-q`（安静模式）和 `-v`（详细日志）。查看某个命令的完整参数：

```bash
python main.py i_dir --help
```
