#!/usr/bin/env python3
"""Download Redis设计与实现 chapters from GitHub."""
import os
import urllib.request
import urllib.parse

BASE = "https://raw.githubusercontent.com/mailjobblog/book-redis-design/main/docs/doc"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "source", "redis")
os.makedirs(OUT_DIR, exist_ok=True)

chapters = [
    ("01", "引言"),
    ("02", "简单动态字符串"),
    ("03", "链表"),
    ("04", "字典"),
    ("05", "跳跃表"),
    ("06", "整数集合"),
    ("07", "压缩列表"),
    ("08", "对象"),
    ("09", "数据库"),
    ("10", "RDB持久化"),
    ("11", "AOF持久化"),
    ("12", "事件"),
    ("13", "客户端"),
    ("14", "重点回顾"),
    ("15", "复制"),
    ("16", "Sentinel"),
    ("17", "集群"),
    ("18", "发布与订阅"),
    ("19", "事务"),
    ("20", "Lua脚本"),
    ("21", "排序"),
    ("22", "二进制位数组"),
    ("23", "慢查询日志"),
    ("24", "监视器"),
]

for num, name in chapters:
    fname = f"{num}-{name}.md"
    url = f"{BASE}/{urllib.parse.quote(fname)}"
    outfile = os.path.join(OUT_DIR, f"ch{num}-{name}.md")
    print(f"Downloading ch{num}: {name} ... ", end="", flush=True)
    try:
        urllib.request.urlretrieve(url, outfile)
        size = os.path.getsize(outfile)
        print(f"OK ({size} bytes)")
    except Exception as e:
        print(f"FAILED: {e}")

print("\nDone! Files in", OUT_DIR)
for f in sorted(os.listdir(OUT_DIR)):
    print(f"  {f}")
