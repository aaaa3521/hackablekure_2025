# hackablekure_2025
"""
呉市場 生鮮品目別・月別取扱高表 → CSV変換スクリプト
=====================================================
使い方：
  1. pip install pdfplumber
  2. このスクリプトと同じフォルダに年ごとのPDFを置く
     例: 2018.pdf, 2019.pdf, 2020.pdf ... 2025.pdf
  3. python convert.py
  4. kure_market_data.csv が生成されます
"""

import pdfplumber
import re
import csv
import os

# ── 設定 ──────────────────────────────────────────
OUTPUT_FILE = "kure_market_data.csv"

# PDFのファイル名と対応する年（自由に追加してください）
PDF_FILES = {
    2018: "2018.pdf",
    2019: "2019.pdf",
    2020: "2020.pdf",
    2021: "2021.pdf",
    2022: "2022.pdf",
    2023: "2023.pdf",
    2024: "2024.pdf",
    2025: "2025.pdf",
}

# 対象品目リスト
ITEMS = [
    "あじ", "さば", "いわし", "こいわし", "さより", "このしろ",
    "さわら", "ヤズ", "はまち", "ぶり", "まなかつお", "かつお",
    "かじき", "まぐろ", "いさき", "たちうお", "ぼら", "たい",
    "ちだい", "ちぬ", "れんこ", "めんたい", "すずき", "ぐち",
    "はぎ", "かれい", "ひらめ", "めばる", "ほご", "あいなめ",
    "おこぜ", "こち", "たなご", "べら", "むつ", "さごし",
    "わち", "はも", "あなご", "えい", "さけ", "ふぐ",
    "いか", "たこ", "かに", "うに", "なまこ", "えび",
    "大正えび", "伊勢えび", "あさり", "はまぐり", "さざえ",
    "あわび", "とり貝", "みる貝", "その他貝類", "あゆ",
    "うなぎ", "その他淡水魚類", "その他鮮魚類", "かき",
]

# ── 関数 ──────────────────────────────────────────
def parse_numbers(s):
    """カンマ区切り数字を抽出"""
    return [int(n.replace(",", "")) for n in re.findall(r'[\d,]+', s)
            if int(n.replace(",", "")) > 0]

def extract_from_pdf(pdf_path, year):
    """PDFから品目×月別データを抽出"""
    results = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            lines = text.split("\n")

            for i, line in enumerate(lines):
                line = line.strip()

                # 品目名 + "合計" の行を探す
                matched_item = None
                for item in ITEMS:
                    if line.startswith(item) and "合計" in line:
                        matched_item = item
                        break

                if not matched_item:
                    continue

                # 数量を取得
                qty_part = line[line.index("合計") + 2:].strip()
                qty_nums = parse_numbers(qty_part)

                # 次の行から金額を取得
                amount_nums = []
                if i + 1 < len(lines):
                    amount_nums = parse_numbers(lines[i + 1])

                # 先頭が年間合計、以降が月別
                if len(qty_nums) >= 2:
                    monthly_qty = qty_nums[1:13]
                    # 月数が12未満の場合0埋め
                    monthly_qty += [0] * (12 - len(monthly_qty))
                else:
                    continue

                if len(amount_nums) >= 2:
                    monthly_amount = amount_nums[1:13]
                    monthly_amount += [0] * (12 - len(monthly_amount))
                else:
                    monthly_amount = [0] * 12

                for month_idx, (qty, amt) in enumerate(zip(monthly_qty, monthly_amount)):
                    if qty > 0:
                        results.append({
                            "year": year,
                            "month": month_idx + 1,
                            "item": matched_item,
                            "quantity_kg": qty,
                            "amount_yen": amt,
                        })

    return results

# ── メイン ────────────────────────────────────────
def main():
    all_data = []

    for year, filename in sorted(PDF_FILES.items()):
        if not os.path.exists(filename):
            print(f"[SKIP] {filename} が見つかりません")
            continue

        print(f"[処理中] {filename} ({year}年)...")
        data = extract_from_pdf(filename, year)
        all_data.extend(data)
        print(f"  → {len(data)} 件抽出")

    if not all_data:
        print("データが取得できませんでした。PDFファイルを確認してください。")
        return

    # CSV保存
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=["year", "month", "item", "quantity_kg", "amount_yen"]
        )
        writer.writeheader()
        writer.writerows(all_data)

    print(f"\n完了！ {OUTPUT_FILE} に {len(all_data)} 件保存しました")
    print(f"対象年: {sorted(set(d['year'] for d in all_data))}")
    print(f"対象品目数: {len(set(d['item'] for d in all_data))}")

if __name__ == "__main__":
    main()