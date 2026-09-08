#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
中国産業概観 RSSフィード生成スクリプト（Selenium Manager版）
ChromeDriverの手動ダウンロードは不要！Seleniumが自動で管理します
"""

import re
import sys
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 定数設定
TARGET_URL = "https://www.mizuhobank.co.jp/corporate/world/info/cndb/economics/others/index.html"
OUTPUT_FILE = "rss_feed.xml"
SITE_NAME = "中国産業概観（みずほ銀行）"
SITE_URL = "https://www.mizuhobank.co.jp/corporate/world/info/cndb/economics/others/"
SITE_DESCRIPTION = "みずほ銀行 中国自動車業界レポートのRSSフィード"

# 日本時間（UTC+9）のタイムゾーン
JST = timezone(timedelta(hours=9))


def get_jst_now() -> datetime:
    """日本時間の現在時刻をタイムゾーン付きで取得"""
    return datetime.now(JST)


def clean_title(title: str) -> str:
    """
    タイトルからファイルサイズ情報（(PDF/XXXKB)）を削除
    例: "中国産業概観【中国自動車業界レポート（2020年9月）】(PDF/643KB)" 
       -> "中国産業概観【中国自動車業界レポート（2020年9月）】"
    """
    # (PDF/数字KB) または (PDF/数字KB) のパターンを削除
    cleaned = re.sub(r'\(PDF/\d+KB\)', '', title)
    # 余分な空白を削除
    cleaned = cleaned.strip()
    return cleaned


def fetch_page_with_selenium(url: str) -> str:
    """
    Selenium Managerを使用してページのHTMLを取得
    ChromeDriverのパス指定は不要！自動で管理されます
    """
    options = Options()
    
    # ヘッドレスモード（画面表示なし）
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # 日本語表示と画面サイズ
    options.add_argument("--lang=ja")
    options.add_argument("--window-size=1920,1080")
    
    # SSL証明書エラーを回避（会社のネットワーク対策）
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors")
    options.add_argument("--allow-running-insecure-content")
    
    # User-Agentを設定
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    print("Chromeを起動中（Selenium Managerが自動でドライバーを管理します）...")
    
    # Selenium Managerが自動でChromeDriverを管理！
    driver = webdriver.Chrome(options=options)
    
    try:
        print(f"ページにアクセス中: {url}")
        driver.get(url)
        
        # テーブルが読み込まれるまで最大30秒待機
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "type1"))
        )
        
        # 追加の待機（JavaScriptの実行を確実にするため）
        driver.implicitly_wait(3)
        
        html = driver.page_source
        print("ページの取得に成功しました")
        return html
        
    except Exception as e:
        print(f"エラーが発生しました: {e}", file=sys.stderr)
        raise
        
    finally:
        driver.quit()
        print("Chromeを終了しました")


def parse_date(date_str: str) -> datetime:
    """
    日付文字列をdatetimeオブジェクトに変換（タイムゾーン付き）
    例: "2026年8月24日" -> datetime(2026, 8, 24, tzinfo=JST)
    """
    # 全角数字を半角に変換
    date_str = date_str.replace("年", "/").replace("月", "/").replace("日", "")
    date_str = date_str.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    
    try:
        year, month, day = map(int, date_str.split("/"))
        # タイムゾーン付きの日時を作成（時刻は0時0分）
        return datetime(year, month, day, tzinfo=JST)
    except ValueError:
        print(f"日付のパースに失敗: {date_str}", file=sys.stderr)
        return get_jst_now()


def extract_reports(html_content: str) -> list:
    """
    HTMLからレポート情報を抽出
    """
    soup = BeautifulSoup(html_content, "html.parser")
    reports = []
    
    # テーブルを検索
    table = soup.find("table", class_="type1")
    if not table:
        print("テーブルが見つかりませんでした", file=sys.stderr)
        return reports
    
    rows = table.find_all("tr")
    print(f"{len(rows)}行のデータを検出しました")
    
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        
        # タイトルセルからリンクとタイトルを抽出
        title_cell = cells[0]
        link_tag = title_cell.find("a")
        
        if not link_tag:
            continue
        
        # PDFリンク
        pdf_url = link_tag.get("href", "")
        if not pdf_url.endswith(".pdf"):
            continue
        
        # 絶対URLに変換
        if pdf_url.startswith("/"):
            pdf_url = "https://www.mizuhobank.co.jp" + pdf_url
        
        # タイトル（ファイルサイズ情報を含む）
        raw_title = link_tag.get_text(strip=True)
        
        # ファイルサイズを抽出（後でdescriptionに使用）
        size_match = re.search(r"\(PDF/(\d+)KB\)", raw_title)
        file_size = f"{size_match.group(1)}KB" if size_match else ""
        
        # タイトルからファイルサイズ情報を削除（クリーンなタイトル）
        clean_title_text = clean_title(raw_title)
        
        # 報告年月を抽出（例：2026年7月）
        match = re.search(r"（(\d{4})年(\d+)月）", clean_title_text)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            report_date = datetime(year, month, 1, tzinfo=JST)
        else:
            report_date = get_jst_now()
        
        # 掲載日
        date_cell = cells[1]
        date_text = date_cell.get_text(strip=True)
        pub_date = parse_date(date_text)
        
        # サマリー
        summary_cell = cells[2]
        summary = summary_cell.get_text(strip=True)
        
        # 月名（日本語）
        month_names = ["1月", "2月", "3月", "4月", "5月", "6月",
                      "7月", "8月", "9月", "10月", "11月", "12月"]
        
        report_info = {
            "title": clean_title_text,  # クリーンなタイトル（ファイルサイズ情報なし）
            "link": pdf_url,
            "pub_date": pub_date,
            "summary": summary,
            "report_date": report_date,
            "file_size": file_size,  # ファイルサイズは別途保持
            "year": report_date.year,
            "month": month_names[report_date.month - 1] if 1 <= report_date.month <= 12 else ""
        }
        
        reports.append(report_info)
        print(f"  レポートを検出: {clean_title_text[:30]}...")
    
    # 掲載日の新しい順（降順）にソート
    reports.sort(key=lambda x: x["pub_date"], reverse=True)
    
    return reports


def generate_rss(reports: list):
    """
    RSSフィードを生成
    """
    if not reports:
        print("レポートがないためRSSフィードを生成できません", file=sys.stderr)
        return
    
    fg = FeedGenerator()
    fg.title(SITE_NAME)
    fg.link(href=SITE_URL, rel="alternate")
    fg.description(SITE_DESCRIPTION)
    fg.language("ja")
    
    # タイムゾーン付きの日時を設定
    now_jst = get_jst_now()
    fg.lastBuildDate(now_jst)
    fg.generator("Python FeedGen")
    
    for report in reports:
        fe = fg.add_entry()
        
        # クリーンなタイトルを設定（ファイルサイズ情報なし）
        fe.title(report["title"])
        
        fe.link(href=report["link"], rel="alternate")
        
        # pubDateはタイムゾーン情報が既に含まれている
        fe.pubDate(report["pub_date"])
        
        # descriptionにはファイルサイズ情報を含める
        description = report["summary"]
        if report["file_size"]:
            description += f" （ファイルサイズ: {report['file_size']}）"
        fe.description(description)
        
        fe.guid(report["link"], permalink=True)
    
    # RSSファイルを出力
    rss_str = fg.rss_str(pretty=True)
    with open(OUTPUT_FILE, "wb") as f:
        f.write(rss_str)
    
    print(f"\n[ステッカー] RSSフィードを生成しました: {OUTPUT_FILE}")
    print(f"[ステッカー] レポート総数: {len(reports)}件")
    if reports:
        print(f"[ステッカー] 最新レポート: {reports[0]['title']}")
        print(f"[ステッカー] 最新掲載日: {reports[0]['pub_date'].strftime('%Y年%m月%d日')}")


def main():
    """
    メイン処理
    """
    print("=" * 60)
    print("中国産業概観 RSSフィード生成ツール")
    print("=" * 60)
    
    # 1. ページ取得
    print(f"\n[ステッカー] 対象URL: {TARGET_URL}")
    html_content = fetch_page_with_selenium(TARGET_URL)
    
    # 2. レポート抽出
    print("\n[ステッカー] レポート情報を抽出中...")
    reports = extract_reports(html_content)
    
    if not reports:
        print("\n[ステッカー] レポートが見つかりませんでした", file=sys.stderr)
        sys.exit(1)
    
    # 3. RSS生成
    print("\n[ステッカー] RSSフィードを生成中...")
    generate_rss(reports)
    
    print("\n" + "=" * 60)
    print("[ステッカー] 処理が完了しました！")
    print("=" * 60)


if __name__ == "__main__":
    main()
