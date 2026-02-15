#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
pip install beautifulsoup4
pip install markdownify

URL（frame/iframe が含まれていても）から本文だけを取得し、
OCI Generate AI で要約する汎用ツール。

"""

import base64
import urllib.parse
from typing import List, Set

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as mdify

from oci.generative_ai_inference.models import (
    ImageUrl
)

class fetchmarkdown:
    # ------------------------------------------------------------
    # 設定項目
    # ------------------------------------------------------------
    MAX_DEPTH = 5                # フレームの最大探索深さ（無限ループ防止）
    REQUEST_TIMEOUT = 12         # 秒
    MAX_RESPONSE_BYTES = 5 * 1024 * 1024   # 5 MiB
    MAX_TOKENS = 10000            # OCI のモデル上限（概算文字数は 0.75 × token）
    MAX_IMAGES = 30             # 画像 最大枚数
    # ------------------------------------------------------------

    def __init__(self):
        return

    #
    # 相対 URL を base から絶対 URL に変換
    #
    def absolute_url(self,base: str, link: str) -> str:
        return urllib.parse.urljoin(base, link)

    #
    # URLからHTML取得
    # 
    def limited_get(self,url: str) -> bytes:
        headers = {
            "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
        }
        with requests.get(
            url,
            headers=headers,
            timeout=self.REQUEST_TIMEOUT,
            stream=True,
            allow_redirects=True,
        ) as resp:
            resp.raise_for_status()
            # Content-Type がテキスト系でなければ例外にする
            ctype = resp.headers.get("Content-Type", "")
            if not ctype.startswith(("text/html", "text/plain", "application/json", "image/jpeg", "image/png" )):
                raise ValueError(f"Unsupported Content-Type: {ctype}")

            chunks: List[bytes] = []
            total = 0
            for chunk in resp.iter_content(chunk_size=8192):
                total += len(chunk)
                if total > self.MAX_RESPONSE_BYTES:
                    raise ValueError(f"Response exceeds {self.MAX_RESPONSE_BYTES} bytes")
                chunks.append(chunk)
            return b"".join(chunks),ctype
    
    #
    # Markdown変換
    #
    def html_to_markdown(self, html: str, base_url: str) :
        # BeautifulSoup でスクリプトやスタイルを除去してから markdownify
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
            
        # 2️⃣ <img> を Markdown の画像記法に置換し、同時に画像をローカルへ保存
        saved_images: List[ImageUrl] = []
        for img in soup.find_all("img"):
            src = img.get("src")
            if not src:
                continue

            if len(saved_images) > self.MAX_IMAGES:
                continue

            # 絶対 URL に変換
            img_url = self.absolute_url(base_url, src)

            # ダウンロードし、資料としてImageUrlにする
            try:
                img_bytes,ctype = self.limited_get(img_url)
            except Exception as e:
                # 取得失敗はスキップ（Markdown には残さない）
                print(f"[WARN] Image download failed: {img_url} ({e})")
                continue

            base64_image = base64.b64encode(img_bytes).decode("utf-8")
            image_url = ImageUrl( url = f"data:{ctype};base64,"+base64_image )
            
            saved_images.append(image_url)

            # Markdown の画像記法に差し替え
            alt_text = img.get("alt", "")
            markdown_img = f"![{alt_text}]({image_url})"
            img.replace_with(markdown_img)
            
        # できるだけ見出し以降だけを残す（ヘッダー・フッター除去の簡易版）
        body = soup.body or soup
        markdown = mdify(str(body), heading_style="ATX")
        # 先頭のメタ情報や空行は削除
        lines = [ln.rstrip() for ln in markdown.splitlines() if ln.strip()]
        
        return "\n".join(lines), saved_images

    #
    # URLを起点に文字列内容をマークダウンに変換
    # 子フレーム対応
    #
    def fetch_recursive(self,url: str, depth: int, visited: Set[str]) :
        if depth > self.MAX_DEPTH:
            # 探索深度リミット
            return "",[]

        # ループ防止
        if url in visited:
            return ""
        visited.add(url)

        try:
            raw, ctype = self.limited_get(url)
        except Exception as e:
            return "",[]

        # マークダウン変換
        html = raw.decode("utf-8", errors="replace")
        
        md_body, images = self.html_to_markdown(html,url)

        # 子フレームを抽出
        soup = BeautifulSoup(html, "html.parser")
        srcs = [
            tag.get("src")
            for tag in soup.find_all(["frame", "iframe"])
            if tag.get("src")
        ]
        
        for src in srcs:
            child_url = self.absolute_url(url, src)
            child_md, child_imgs = self.fetch_recursive(child_url, depth + 1, visited)
            
            if child_md:
                md_body += "\n\n" + child_md

            images.extend(child_imgs)            

        return md_body, images

    #
    # トークンリミット処置
    #
    def truncate_to_token_limit(self,text: str, max_tokens: int = MAX_TOKENS) -> str:
        """
        おおよそのトークン数 = 文字数 * 0.75 と見積もり、上限を超えると先頭だけ残す。
        """
        if len(text) <= max_tokens:
            return text

        return text[:max_tokens]

    #
    # URLから文字列内容をMarkdownで取得
    #
    def fetchurl(self,start_url):
        try:
            # すべてのフレームを再帰取得し、Markdown に変換
            merged_md, images = self.fetch_recursive(start_url, depth=0, visited=set())
            if not merged_md.strip():
                return "",[]

            # トークン上限に合わせて切り詰めて返却
            return self.truncate_to_token_limit(merged_md), images
        except Exception as e:
            return "",[]
