"""
DevTools MCP Server — 可视化 Demo 界面
展示所有 8 个工具的实际运行效果
"""
import sys
import asyncio
import json

sys.path.insert(0, "C:/Users/liko/Desktop/mcp-tool-server")
from server import mcp


async def demo():
    print("=" * 60)
    print("  DevTools MCP Server — 功能演示")
    print("=" * 60)

    # 1. 系统信息
    print("\n[1/8] system_info — 获取系统信息")
    r = await mcp.call_tool("system_info", {})
    print(f"  {r.content[0].text}")

    # 2. 列出目录
    print("\n[2/8] list_directory — 列出桌面文件")
    r = await mcp.call_tool("list_directory", {"path": "C:/Users/liko/Desktop"})
    # 只显示前5行
    lines = r.content[0].text.split("\n")
    print("\n".join(lines[:8]))
    if len(lines) > 8:
        print(f"  ... (共 {len(lines)} 行)")

    # 3. 写入文件
    print("\n[3/8] write_file — 创建一个测试文件")
    r = await mcp.call_tool(
        "write_file",
        {
            "path": "C:/Users/liko/Desktop/mcp-tool-server/demo_test.txt",
            "content": "这是 MCP DevTools 的演示文件。\nMCP (Model Context Protocol) 让 AI Agent 可以调用外部工具。",
        },
    )
    print(f"  {r.content[0].text}")

    # 4. 读取文件
    print("\n[4/8] read_file — 读取刚创建的文件")
    r = await mcp.call_tool(
        "read_file",
        {"path": "C:/Users/liko/Desktop/mcp-tool-server/demo_test.txt"},
    )
    print(f"  {r.content[0].text}")

    # 5. 搜索文件
    print("\n[5/8] search_files — 搜索所有 .py 文件")
    r = await mcp.call_tool(
        "search_files",
        {"directory": "C:/Users/liko/Desktop/mcp-tool-server", "pattern": "*.py"},
    )
    print(f"  {r.content[0].text}")

    # 6. 执行 Python 代码
    print("\n[6/8] run_python — 执行一段 Python 代码")
    r = await mcp.call_tool(
        "run_python",
        {
            "code": """
import datetime
now = datetime.datetime.now()
print(f"当前时间: {now}")
print(f"时间戳: {now.timestamp()}")
print(f"本周第 {now.weekday() + 1} 天")
"""
        },
    )
    print(f"  {r.content[0].text.strip()}")

    # 7. 网页抓取
    print("\n[7/8] web_fetch — 抓取网页内容")
    r = await mcp.call_tool(
        "web_fetch", {"url": "https://httpbin.org/json", "timeout": 10}
    )
    text = r.content[0].text
    if len(text) > 300:
        text = text[:300] + "\n  ...(已截断)"
    print(f"  {text}")

    # 8. SQLite 查询
    print("\n[8/8] sqlite_query — SQLite 数据库查询")
    import sqlite3, os

    db_path = "C:/Users/liko/Desktop/mcp-tool-server/demo.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users (id INTEGER, name TEXT, role TEXT)"
    )
    conn.execute("DELETE FROM users")
    conn.execute("INSERT INTO users VALUES (1, '李珂', 'AI工程师')")
    conn.execute("INSERT INTO users VALUES (2, '张三', '产品经理')")
    conn.execute("INSERT INTO users VALUES (3, '李四', '后端开发')")
    conn.commit()
    conn.close()

    r = await mcp.call_tool("sqlite_query", {"db_path": db_path, "query": "SELECT * FROM users"})
    print(f"  {r.content[0].text}")

    os.remove(db_path)

    # 资源
    print("\n" + "=" * 60)
    print("  资源 & 提示词")
    print("=" * 60)

    print("\n[资源] config://server")
    r = await mcp.read_resource("config://server")
    print(f"  {r.contents[0].content}")

    print("\n[提示词] code_review")
    r = await mcp.render_prompt("code_review", {"code": "def add(a,b): return a+b", "language": "python"})
    text = str(r)[:300]
    print(f"  {text}...")

    # 清理
    try:
        os.remove("C:/Users/liko/Desktop/mcp-tool-server/demo_test.txt")
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("  演示完成！以上所有操作都由 MCP 工具完成。")
    print("  将这些工具接入 Claude Code 后，AI 就能自动调用它们。")
    print("=" * 60)


asyncio.run(demo())
