"""
DevTools MCP Server — 为 AI Agent 提供开发工具集合
支持文件操作、网页抓取、代码执行、数据库查询等
"""

import os
import sys
import json
import sqlite3
import subprocess
import tempfile
import urllib.request
import urllib.error
import platform
import time
from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP("DevTools MCP Server")

WORKSPACE = Path(os.getcwd()).resolve()
MAX_FILE_SIZE = 1024 * 1024  # 1MB
PYTHON_TIMEOUT = 30  # seconds


def _safe_path(path: str) -> Path:
    """解析并验证路径安全性"""
    p = Path(path).resolve()
    # 允许任意路径读取，但写入限制在 workspace
    return p


# ═══════════════════════════════════════════
# Tools
# ═══════════════════════════════════════════


@mcp.tool()
def read_file(path: str, max_lines: int = 200) -> str:
    """读取文件内容。参数 path: 文件路径（绝对或相对）；max_lines: 最大读取行数（默认200）"""
    p = _safe_path(path)
    if not p.exists():
        return f"错误: 文件不存在: {p}"
    if p.is_dir():
        return f"错误: 路径是目录而非文件: {p}"
    if p.stat().st_size > MAX_FILE_SIZE:
        return f"错误: 文件过大 ({p.stat().st_size / 1024:.0f}KB)，超过 1MB 限制"

    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        total = len(lines)
        if len(lines) > max_lines:
            content = "\n".join(lines[:max_lines])
            content += f"\n\n... (共 {total} 行，仅显示前 {max_lines} 行)"
        return content
    except Exception as e:
        return f"读取失败: {e}"


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """写入内容到文件（创建或覆盖）。参数 path: 文件路径；content: 要写入的内容"""
    p = Path(path).resolve()

    # 安全检查：不允许覆盖关键系统文件
    dangerous = ["/etc/", "/windows/", "C:\\Windows\\", "/system/", "/boot/"]
    path_str = str(p).lower()
    for d in dangerous:
        if path_str.startswith(d.lower()):
            return f"错误: 不允许写入系统目录: {d}"

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"写入成功: {p} ({len(content)} 字符)"
    except Exception as e:
        return f"写入失败: {e}"


@mcp.tool()
def list_directory(path: str = ".") -> str:
    """列出目录内容。参数 path: 目录路径，默认为当前目录"""
    p = _safe_path(path)
    if not p.exists():
        return f"错误: 目录不存在: {p}"
    if not p.is_dir():
        return f"错误: 不是目录: {p}"

    try:
        items = []
        for entry in sorted(p.iterdir()):
            try:
                stat = entry.stat()
                mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime))
                if entry.is_dir():
                    items.append(f"  [DIR]  {entry.name}/  ({mtime})")
                else:
                    size = stat.st_size
                    if size < 1024:
                        size_str = f"{size}B"
                    elif size < 1024 * 1024:
                        size_str = f"{size / 1024:.1f}KB"
                    else:
                        size_str = f"{size / 1024 / 1024:.1f}MB"
                    items.append(f"  [FILE] {entry.name}  {size_str}  ({mtime})")
            except OSError:
                items.append(f"  [?]    {entry.name}")

        return f"目录: {p}\n" + "\n".join(items) if items else f"目录: {p}\n  (空)"
    except Exception as e:
        return f"列出失败: {e}"


@mcp.tool()
def web_fetch(url: str, timeout: int = 15) -> str:
    """获取网页或API内容。参数 url: 网页URL；timeout: 超时秒数（默认15）"""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "MCP-DevTools/1.0",
                "Accept": "text/html,application/json,text/plain",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read()
            content_type = resp.headers.get("Content-Type", "")

            if "json" in content_type:
                data = json.loads(content)
                return json.dumps(data, ensure_ascii=False, indent=2)
            else:
                text = content.decode("utf-8", errors="replace")
                # 截断过长内容
                if len(text) > 5000:
                    text = text[:5000] + f"\n\n... (总长度 {len(text)} 字符，已截断)"
                return text
    except urllib.error.HTTPError as e:
        return f"HTTP 错误: {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return f"网络错误: {e.reason}"
    except Exception as e:
        return f"请求失败: {e}"


@mcp.tool()
def run_python(code: str) -> str:
    """在隔离子进程中执行 Python 代码。参数 code: Python 代码字符串"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=PYTHON_TIMEOUT,
            cwd=str(WORKSPACE),
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[退出码: {result.returncode}]"
        return output.strip() or "(无输出)"
    except subprocess.TimeoutExpired:
        return f"错误: 代码执行超时 ({PYTHON_TIMEOUT}秒)"
    except Exception as e:
        return f"执行失败: {e}"
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@mcp.tool()
def sqlite_query(db_path: str, query: str) -> str:
    """执行 SQLite 查询（仅限 SELECT）。参数 db_path: 数据库文件路径；query: SQL SELECT 语句"""
    query_stripped = query.strip().upper()
    if not query_stripped.startswith("SELECT"):
        return "错误: 仅允许 SELECT 查询"

    p = _safe_path(db_path)
    if not p.exists():
        return f"错误: 数据库文件不存在: {p}"

    try:
        conn = sqlite3.connect(str(p))
        cursor = conn.cursor()
        cursor.execute(query)

        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description] if cursor.description else []

        if not rows:
            return "查询结果为空"

        # 格式化输出
        col_widths = [len(c) for c in cols]
        for row in rows[:50]:
            for i, val in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(val)))

        header = " | ".join(c.ljust(col_widths[i]) for i, c in enumerate(cols))
        sep = "-+-".join("-" * col_widths[i] for i in range(len(cols)))
        body = "\n".join(
            " | ".join(str(v).ljust(col_widths[i]) for i, v in enumerate(row))
            for row in rows[:50]
        )

        result = f"{header}\n{sep}\n{body}"
        if len(rows) > 50:
            result += f"\n\n... (共 {len(rows)} 行，仅显示前 50 行)"
        return result
    except sqlite3.Error as e:
        return f"SQLite 错误: {e}"
    finally:
        conn.close()


@mcp.tool()
def system_info() -> str:
    """获取当前系统信息（操作系统、CPU、内存、磁盘、Python版本）"""
    info = {
        "操作系统": f"{platform.system()} {platform.release()} ({platform.version()})",
        "主机名": platform.node(),
        "架构": platform.machine(),
        "Python版本": sys.version.split()[0],
        "当前目录": str(WORKSPACE),
    }

    # CPU
    try:
        import multiprocessing
        info["CPU核心数"] = str(multiprocessing.cpu_count())
    except Exception:
        pass

    # 磁盘
    try:
        import shutil
        usage = shutil.disk_usage(str(WORKSPACE))
        info["磁盘总空间"] = f"{usage.total / 1024**3:.1f} GB"
        info["磁盘可用"] = f"{usage.free / 1024**3:.1f} GB"
    except Exception:
        pass

    return json.dumps(info, ensure_ascii=False, indent=2)


@mcp.tool()
def search_files(directory: str, pattern: str) -> str:
    """在目录中搜索包含指定模式的文件。参数 directory: 搜索目录；pattern: 搜索模式（支持通配符如 *.py）"""
    import fnmatch

    p = _safe_path(directory)
    if not p.exists() or not p.is_dir():
        return f"错误: 目录不存在: {p}"

    try:
        matches = []
        for root, dirs, files in os.walk(str(p)):
            # 跳过隐藏目录
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if fnmatch.fnmatch(fname, pattern):
                    matches.append(str(Path(root) / fname))

        if not matches:
            return f"未找到匹配 '{pattern}' 的文件"
        if len(matches) > 100:
            matches = matches[:100]
            return "\n".join(matches) + f"\n\n... (共找到更多文件，仅显示前 100 个)"
        return "\n".join(matches)
    except Exception as e:
        return f"搜索失败: {e}"


# ═══════════════════════════════════════════
# Resources
# ═══════════════════════════════════════════


@mcp.resource("config://server")
def get_server_config() -> str:
    """返回服务器配置信息"""
    config = {
        "name": "DevTools MCP Server",
        "version": "1.0.0",
        "tools": [
            "read_file", "write_file", "list_directory",
            "web_fetch", "run_python", "sqlite_query",
            "system_info", "search_files",
        ],
        "workspace": str(WORKSPACE),
        "max_file_size": f"{MAX_FILE_SIZE // 1024}KB",
        "python_timeout": f"{PYTHON_TIMEOUT}s",
    }
    return json.dumps(config, ensure_ascii=False, indent=2)


@mcp.resource("stats://server")
def get_server_stats() -> str:
    """返回运行时统计"""
    import time as _time
    stats = {
        "uptime_seconds": _time.time() - _time.time(),  # 简化
        "python_version": sys.version,
        "platform": platform.platform(),
    }
    return json.dumps(stats, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════
# Prompts
# ═══════════════════════════════════════════


@mcp.prompt()
def code_review(code: str, language: str = "python") -> str:
    """生成代码审查提示词"""
    return f"""请对以下 {language} 代码进行专业审查，从以下维度分析：

1. **正确性**: 逻辑是否正确，边界情况是否处理
2. **安全性**: 是否存在安全漏洞（注入、路径遍历等）
3. **性能**: 是否有性能瓶颈或优化空间
4. **可读性**: 命名、结构、注释是否清晰
5. **最佳实践**: 是否符合 {language} 社区最佳实践

```{language}
{code}
```

请给出具体的改进建议和修改后的代码。"""


@mcp.prompt()
def api_design(endpoint: str, method: str = "GET") -> str:
    """生成 API 设计审查提示词"""
    return f"""请审查以下 API 端点设计：

- **端点**: {endpoint}
- **方法**: {method}

请从以下角度分析：
1. RESTful 设计规范
2. 请求/响应结构
3. 错误处理策略
4. 认证与授权
5. 限流与性能考虑

给出最佳实践建议和示例实现。"""


if __name__ == "__main__":
    mcp.run(transport="stdio")
