"""
呉市場 生鮮水産物 品目産地別・月別取扱高表 PDF → CSV 変換スクリプト v3
pdfplumber の x座標ベースで月列を正確に判定

出力カラム: 品目, 産地, 年, 月, 数量_kg, 金額_円
"""

import re
import csv
import sys
from pathlib import Path
import pdfplumber

PDF_PATH = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/令和7年_生鮮品目別_月別取扱高表.pdf"
OUTPUT_PATH = sys.argv[2] if len(sys.argv) > 2 else "/mnt/user-data/outputs/kure_fish_market.csv"

REIWA_BASE = 2018

def detect_year(pdf_path: str) -> int:
    import re as _re
    m = _re.search(r'令和([０-９\d]+)年', pdf_path)
    if m:
        num = m.group(1).translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        return REIWA_BASE + int(num)
    with pdfplumber.open(pdf_path) as pdf:
        for w in pdf.pages[0].extract_words()[:30]:
            m = _re.match(r'令和([０-９\d]+)年', w['text'])
            if m:
                num = m.group(1).translate(str.maketrans('０１２３４５６７８９', '0123456789'))
                return REIWA_BASE + int(num)
    return 2025

YEAR = detect_year(PDF_PATH)

# 品目名の正規化マッピング
NAME_MAP = {
    'まなかつ': 'まなかつお',
    'その他淡': 'その他淡水魚類',
    'その他貝': 'その他貝類',
    'その他鮮': 'その他鮮魚類',
}

ORIGINS = {'合計', '広島', '愛媛', '東京', '福岡', '山口', '三重', '大分', '熊本', '島根', '福井'}

SKIP_TEXTS = {'生鮮水産物', '品目産地別・月別取扱高表', '単位', '上段', '下段', '数量', '金額',
              '令和', '月別', '品目', '産地別', '合', '計'}


def is_number(text: str) -> bool:
    return bool(re.match(r'^[\d,]+$', text.strip()))


def parse_int(text: str) -> int:
    return int(text.replace(',', ''))


# データ値はヘッダーのx0より約20pt右に配置される（右寄せのため）
DATA_X_OFFSET = 20.3

def get_month_x_ranges(words: list[dict]) -> list[tuple[float, float]]:
    """
    ヘッダー行の月数字（１〜１２）のx0座標からデータ値の列範囲を計算する。
    データ値は右寄せのためヘッダーx0より DATA_X_OFFSET だけ右にある。
    戻り値: [(x_start, x_end), ...] 1月〜12月の12要素
    """
    MONTH_CHARS = {'１', '２', '３', '４', '５', '６', '７', '８', '９', '１０', '１１', '１２'}
    MONTH_ORDER = ['１', '２', '３', '４', '５', '６', '７', '８', '９', '１０', '１１', '１２']

    header_top = None
    month_positions = {}

    for w in words:
        if w['text'] in MONTH_CHARS:
            if header_top is None:
                header_top = w['top']
            if abs(w['top'] - header_top) < 5:
                month_positions[w['text']] = w['x0']

    if len(month_positions) < 12:
        return []

    # ヘッダーx0 + オフセット = データ値の中心x座標
    centers = [month_positions[m] + DATA_X_OFFSET for m in MONTH_ORDER if m in month_positions]
    if len(centers) < 12:
        return []

    # 境界 = 隣接月の中点
    ranges = []
    for i, center in enumerate(centers):
        x_start = (centers[i - 1] + center) / 2 if i > 0 else center - 30
        x_end = (center + centers[i + 1]) / 2 if i < len(centers) - 1 else center + 30
        ranges.append((x_start, x_end))

    return ranges


def get_col_x_range(words: list[dict]) -> tuple[float, float] | None:
    """合計列のx範囲を取得"""
    for w in words:
        if w['text'] == '合' and 80 < w['top'] < 100:
            x0 = w['x0']
            return (x0 - 5, x0 + 50)
    return None


def assign_to_month(x0: float, month_ranges: list[tuple[float, float]]) -> int | None:
    """x0座標から月番号(1-12)を返す。どの月にも属さない場合はNone"""
    for i, (x_start, x_end) in enumerate(month_ranges):
        if x_start <= x0 < x_end:
            return i + 1
    return None


def group_rows_by_top(words: list[dict], tolerance: float = 2.0) -> list[list[dict]]:
    """同じtop（行）のワードをグループ化"""
    if not words:
        return []

    rows = []
    current_row = [words[0]]

    for w in words[1:]:
        if abs(w['top'] - current_row[0]['top']) <= tolerance:
            current_row.append(w)
        else:
            rows.append(sorted(current_row, key=lambda x: x['x0']))
            current_row = [w]
    rows.append(sorted(current_row, key=lambda x: x['x0']))

    return rows


def parse_page(page, month_ranges: list[tuple[float, float]]) -> list[dict]:
    records = []
    words = page.extract_words()

    # top でグループ化
    rows = group_rows_by_top(words)

    current_item = None
    current_origin = None
    pending_row = None  # 数量行（次の行が金額行）

    for row in rows:
        texts = [w['text'] for w in row]
        row_text = ''.join(texts)

        # ヘッダー系スキップ
        if any(t in SKIP_TEXTS for t in texts) and not any(is_number(t) for t in texts):
            continue
        if '令和' in row_text or '№' in row_text:
            continue

        # 品目名と産地の検出
        new_item = None
        new_origin = None

        for i, t in enumerate(texts):
            if t in ORIGINS:
                new_origin = t
                # 左隣に品目名があるか確認
                if i > 0 and texts[i - 1] not in ORIGINS and not is_number(texts[i - 1]):
                    candidate = texts[i - 1]
                    candidate = re.sub(r'\s+', '', candidate)
                    candidate = NAME_MAP.get(candidate, candidate)
                    if candidate:
                        new_item = candidate
                break

        if new_item:
            current_item = new_item
        if new_origin:
            current_origin = new_origin

        # 数値行の処理
        num_words = [w for w in row if is_number(w['text'])]
        if not num_words:
            continue

        if pending_row is not None:
            # 今の行が金額行
            kin_words = num_words
            qty_words = pending_row

            # 月ごとに数量・金額を取得
            qty_by_month = {}
            kin_by_month = {}

            for w in qty_words:
                m = assign_to_month(w['x0'], month_ranges)
                if m:
                    qty_by_month[m] = parse_int(w['text'])

            for w in kin_words:
                m = assign_to_month(w['x0'], month_ranges)
                if m:
                    kin_by_month[m] = parse_int(w['text'])

            if current_item and current_origin:
                for month in range(1, 13):
                    qty = qty_by_month.get(month)
                    kin = kin_by_month.get(month)
                    if qty is not None or kin is not None:
                        records.append({
                            '品目': current_item,
                            '産地': current_origin,
                            '年': YEAR,
                            '月': month,
                            '数量_kg': qty,
                            '金額_円': kin,
                        })

            pending_row = None

        elif current_item and current_origin and num_words:
            # 数量行として保持
            pending_row = num_words

    return records


def main():
    print("PDFパース中...")
    all_records = []

    with pdfplumber.open(PDF_PATH) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            words = page.extract_words()
            month_ranges = get_month_x_ranges(words)

            if not month_ranges:
                print(f"  ページ{page_num}: 月ヘッダーが見つかりません")
                continue

            records = parse_page(page, month_ranges)
            all_records.extend(records)
            print(f"  ページ{page_num}: {len(records)}レコード")

    print(f"\n総レコード数: {len(all_records)}")

    # 検証: あじ合計
    aji = [r for r in all_records if r['品目'] == 'あじ' and r['産地'] == '合計']
    print("\nあじ合計（数量）:")
    for r in sorted(aji, key=lambda x: x['月']):
        print(f"  {r['月']}月: {r['数量_kg']}kg, {r['金額_円']}円")

    # 検証: さわら産地別
    sawara = [r for r in all_records if r['品目'] == 'さわら']
    print("\nさわら産地別（数量）:")
    for r in sorted(sawara, key=lambda x: (x['産地'], x['月'])):
        print(f"  {r['産地']} {r['月']}月: {r['数量_kg']}kg")

    # CSV出力
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['品目', '産地', '年', '月', '数量_kg', '金額_円'])
        writer.writeheader()
        writer.writerows(all_records)

    print(f"\nCSV出力完了: {OUTPUT_PATH}")

    # 品目一覧
    items = sorted(set(r['品目'] for r in all_records))
    print(f"\n品目数: {len(items)}")
    print("品目:", items)


if __name__ == '__main__':
    main()
