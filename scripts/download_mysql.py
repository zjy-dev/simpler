#!/usr/bin/env python3
"""
爬取《MySQL 是怎样运行的》在线笔记的所有章节 Markdown 文件和图片。
来源: https://relph1119.github.io/mysql-learning-notes/
实际文件托管在 GitHub 仓库: https://github.com/Relph1119/mysql-learning-notes
"""

import os
import re
import time
import urllib.request
import urllib.parse
import urllib.error

BASE_RAW = "https://raw.githubusercontent.com/Relph1119/mysql-learning-notes/master"
BASE_SITE = "https://relph1119.github.io/mysql-learning-notes"

# 章节文件名列表 (从 _sidebar.md 提取)
CHAPTERS = [
    "mysql/00-万里长征第一步（非常重要）-如何愉快的阅读本小册.md",
    "mysql/01-装作自己是个小白-重新认识MySQL.md",
    "mysql/02-MySQL的调控按钮-启动选项和系统变量.md",
    "mysql/03-乱码的前世今生-字符集和比较规则.md",
    "mysql/04-从一条记录说起-InnoDB记录结构.md",
    "mysql/05-盛放记录的大盒子-InnoDB数据页结构.md",
    "mysql/06-快速查询的秘籍-B+树索引.md",
    "mysql/07-好东西也得先学会怎么用-B+树索引的使用.md",
    "mysql/08-数据的家-MySQL的数据目录.md",
    "mysql/09-存放页的大池子-InnoDB的表空间.md",
    "mysql/10-条条大路通罗马-单表访问方法.md",
    "mysql/11-两个表的亲密接触-连接的原理.md",
    "mysql/12-谁最便宜就选谁-MySQL基于成本的优化.md",
    "mysql/13-兵马未动，粮草先行-InnoDB统计数据是如何收集的.md",
    "mysql/14-不好看就要多整容-MySQL基于规则的优化（内含关于子查询优化二三事儿）.md",
    "mysql/15-查询优化的百科全书-Explain详解（上）.md",
    "mysql/16-查询优化的百科全书-Explain详解（下）.md",
    "mysql/17-神兵利器-optimizer trace的神器功效.md",
    "mysql/18-调节磁盘和CPU的矛盾-InnoDB的Buffer Pool.md",
    "mysql/19-从猫爷被杀说起-事务简介.md",
    "mysql/20-说过的话就一定要办到-redo日志（上）.md",
    "mysql/21-说过的话就一定要办到-redo日志（下）.md",
    "mysql/22-后悔了怎么办-undo日志（上）.md",
    "mysql/23-后悔了怎么办-undo日志（下）.md",
    "mysql/24-一条记录的多幅面孔-事务的隔离级别与MVCC.md",
    "mysql/25-工作面试老大难-锁.md",
    "mysql/26-写作本书时用到的一些重要的参考资料.md",
]

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "source", "mysql")
IMG_DIR = os.path.join(OUT_DIR, "images")


def download(url, retries=3, delay=2):
    """下载 URL 内容，返回 bytes。"""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            print(f"  [WARN] attempt {attempt+1}/{retries} failed for {url}: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    return None


def download_chapter(ch_path):
    """下载一个章节的 Markdown 文件。"""
    encoded = urllib.parse.quote(ch_path, safe="/")
    url = f"{BASE_RAW}/{encoded}"
    print(f"Downloading: {ch_path}")
    data = download(url)
    if data is None:
        print(f"  [ERROR] Failed to download {ch_path}")
        return None
    return data.decode("utf-8")


def download_images(md_text, ch_name):
    """解析 Markdown 中的图片链接，下载图片，并替换为本地路径。"""
    # 匹配 ![alt](url) 格式的图片
    img_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
    
    def replace_img(m):
        alt = m.group(1)
        img_url = m.group(2)
        
        # 处理相对路径和绝对路径
        if img_url.startswith("http"):
            full_url = img_url
        elif img_url.startswith("../"):
            full_url = f"{BASE_SITE}/{img_url.lstrip('../')}"
        else:
            full_url = f"{BASE_SITE}/{img_url}"
        
        # 提取文件名
        img_name = os.path.basename(urllib.parse.unquote(img_url.split("?")[0]))
        local_path = os.path.join(IMG_DIR, img_name)
        rel_path = f"images/{img_name}"
        
        if not os.path.exists(local_path):
            print(f"  Downloading image: {img_name}")
            img_data = download(full_url)
            if img_data:
                with open(local_path, "wb") as f:
                    f.write(img_data)
            else:
                print(f"  [WARN] Failed to download image: {full_url}")
                return m.group(0)  # 保留原始链接
        
        return f"![{alt}]({rel_path})"
    
    return img_pattern.sub(replace_img, md_text)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(IMG_DIR, exist_ok=True)
    
    for ch_path in CHAPTERS:
        ch_filename = os.path.basename(ch_path)
        out_path = os.path.join(OUT_DIR, ch_filename)
        
        if os.path.exists(out_path):
            print(f"Already exists, skipping: {ch_filename}")
            continue
        
        md_text = download_chapter(ch_path)
        if md_text is None:
            continue
        
        # 下载并替换图片路径
        md_text = download_images(md_text, ch_filename)
        
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_text)
        
        print(f"  Saved: {ch_filename}")
        time.sleep(0.5)  # 礼貌延迟
    
    print(f"\nDone! Files saved to {OUT_DIR}")
    print(f"Images saved to {IMG_DIR}")


if __name__ == "__main__":
    main()
