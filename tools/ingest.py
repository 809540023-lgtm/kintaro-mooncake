#!/usr/bin/env python3
"""持續進貨管線：把新的商品照片資料夾轉成 products.json 商品。

用法：
  python3 tools/ingest.py --src "/新的照片資料夾" [--dry-run]

流程：HEIC/JPG → 壓縮 JPG → macOS Vision OCR（價目標籤）→
時間/標籤分組 → 品名/價格/入數擷取 → 併入 products.json。
人工修正知識存在 tools/title-fixes.json 與 tools/brands.json，
每次遇到新品牌或新標題寫法，往這兩個檔加規則即可。
"""
import argparse, json, re, subprocess, sys
from datetime import datetime
from pathlib import Path

import pillow_heif
from PIL import Image
pillow_heif.register_heif_opener()

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT
TOOLS = ROOT / 'tools'
CACHE = TOOLS / '.cache'

# ---------- 基礎擷取 ----------

def num(stem):
    m = re.search(r'IMG_(\d+)', stem)
    return int(m.group(1)) if m else 0

def prices(t):
    out = []
    for m in re.finditer(r'(?:税込)?\s*¥\s*([0-9][0-9,]{2,6})', t or ''):
        v = int(m.group(1).replace(',', ''))
        if 300 <= v <= 20000:
            out.append(v)
    return out

def tax_price(t):
    m = re.search(r'税込\s*¥\s*([0-9][0-9,]{2,6})', t or '')
    return int(m.group(1).replace(',', '')) if m else None

def tag_score(t):
    if not t:
        return 0
    s = 0
    if '特定原材料' in t: s += 2
    if re.search(r'¥\s*[0-9][0-9,]{2,6}', t): s += 2
    if '税込' in t: s += 1
    if re.search(r'[0-9]+\s*(個入|枚入|本入|袋入|粒入)', t): s += 1
    if re.search(r'\b[A-Z]{1,3}[-‑][A-Z0-9]{2,6}', t): s += 1
    if '予約' in t: s += 1
    return s

BAD = re.compile(r'特定原材料|税込|本体|¥|予約|限定|見本|配送|までに|しており|NEW|アレルギー|一部商品|焼き色|仕上がり|場合がござい|お渡し|ご試食|使用！|承ります|検索|価格|円（|円）')

def name_lines(t):
    if not t:
        return []
    out = []
    for l in [x.strip() for x in t.split('\n') if x.strip()][:16]:
        if BAD.search(l) or len(l) < 2 or len(l) > 40:
            continue
        if re.search(r'[ぁ-んァ-ヶ一-龥]{2,}', l) or (len(l) > 8 and l.replace(' ', '').isupper()):
            out.append(l)
    return out

def extract_qty(t):
    m = re.search(r'([0-9]+)\s*(個入|枚入|本入|袋入|粒入)', t or '')
    return f"{m.group(1)}{m.group(2)}" if m else ''

def tokens(nl):
    toks = set()
    for l in nl:
        for m in re.findall(r'[ァ-ヶ一-龥]{3,}', l):
            toks.add(m)
        for m in re.findall(r'[A-Za-z]{4,}', l):
            toks.add(m.lower())
    return toks

# ---------- OCR ----------

def ensure_ocr_bin():
    src, dst = TOOLS / 'ocr.swift', TOOLS / 'ocr'
    if dst.exists():
        return dst
    r = subprocess.run(['swiftc', '-o', str(dst), str(src)], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit('OCR 編譯失敗：' + r.stderr[:500])
    return dst

def run_ocr(binpath, img):
    r = subprocess.run([str(binpath), str(img), 'ja-JP', 'zh-TW', 'en-US'],
                       capture_output=True, text=True, timeout=180)
    return r.stdout.strip()

# ---------- 主流程 ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True, help='新照片資料夾')
    ap.add_argument('--dry-run', action='store_true', help='只分析不寫入')
    args = ap.parse_args()

    src = Path(args.src).expanduser()
    files = sorted([f for f in src.iterdir() if f.suffix.lower() in ('.heic', '.jpg', '.jpeg')],
                   key=lambda f: num(f.stem))
    if not files:
        sys.exit('資料夾裡沒有照片')
    print(f'照片：{len(files)} 張（{src}）')

    brands = json.load(open(TOOLS / 'brands.json'))
    fixes = json.load(open(TOOLS / 'title-fixes.json'))
    ocrbin = ensure_ocr_bin()

    # 轉檔 + OCR（cache 以檔名+大小為 key）
    CACHE.mkdir(exist_ok=True)
    recs, thumbs = [], {}
    for f in files:
        key = f.stem + '-' + str(f.stat().st_size)
        cj = CACHE / (key + '.json')
        if cj.exists():
            data = json.load(open(cj))
        else:
            tmp = CACHE / (key + '.jpg')
            im = Image.open(f).convert('RGB')
            im.thumbnail((1400, 1400))
            im.save(tmp, quality=82)
            data = {'txt': run_ocr(ocrbin, tmp), 'w': im.size[0], 'h': im.size[1]}
            json.dump(data, open(cj, 'w'), ensure_ascii=False)
        try:
            im = Image.open(f)
            exif = im.getexif()
            dt = exif.get(36867) or exif.get(306) or ''
            im.close()
        except Exception:
            dt = ''
        t = datetime.strptime(dt, '%Y:%m:%d %H:%M:%S') if dt.startswith('20') else datetime(2026, 1, 1)
        recs.append({'stem': f.stem, 't': t, 'txt': data.get('txt', '')})
    recs.sort(key=lambda r: r['t'])

    # 分組：價目標籤開新商品，同價格/同名稱/相鄰重拍標籤視為同一商品
    groups, cur = [], {'tag': None, 'prices': set(), 'photos': []}
    def flush():
        if cur['tag'] or cur['photos']:
            groups.append(cur)
    def same_price(a, b):
        return bool(a & set(b))
    for r in recs:
        sc = tag_score(r['txt'])
        if sc >= 3:
            ps = prices(r['txt'])
            if cur['tag'] is not None:
                prev_is_tag = cur['photos'] and tag_score(cur['photos'][-1]['txt']) >= 3
                ta, tb = tokens(name_lines(cur['tag']['txt'])), tokens(name_lines(r['txt']))
                overlap = bool(ta & tb) or any((x in y or y in x) for x in ta for y in tb if min(len(x), len(y)) >= 3)
                if (prev_is_tag or same_price(cur['prices'], ps) or overlap) and len(cur['photos']) < 7:
                    cur['prices'] |= set(ps)
                    cur['photos'].append(r)
                    continue
            flush()
            cur = {'tag': r, 'prices': set(ps), 'photos': []}
        else:
            cur['photos'].append(r)
    flush()
    groups = [g for g in groups if g['photos'] or g['tag']]

    # 手動修正（上一批累積的知識）
    manual = fixes.get('manual', {})
    out_groups, used = [], set()
    for g in groups:
        key = g['tag']['stem'] if g['tag'] else None
        if key in manual:
            title, price, qty, brand, photo_stems = manual[key]
            out_groups.append({'title': title, 'price': price, 'qty': qty, 'brand': brand,
                               'tag': g['tag'], 'photos': [by_stem(s, recs) for s in photo_stems]})
            used.add(key)
            for s in photo_stems:
                used.add(s)
        else:
            gs = {g['tag']['stem'] if g['tag'] else None} | {p['stem'] for p in g['photos']}
            if gs & used:
                continue
            out_groups.append(g)
    for stem, v in manual.items():
        if stem not in used and by_stem(stem, recs):
            title, price, qty, brand, photo_stems = v
            out_groups.append({'title': title, 'price': price, 'qty': qty, 'brand': brand,
                               'tag': by_stem(stem, recs), 'photos': [by_stem(s, recs) for s in photo_stems]})

    # 編號接續現有商品
    pj = REPO / 'products.json'
    data = json.load(open(pj))
    maxn = 0
    for p in data:
        for i in p['images']:
            m = re.match(r'images/p(\d+)-', i)
            if m:
                maxn = max(maxn, int(m.group(1)))
    imgdir = REPO / 'images'
    stem2file = {f.stem: f for f in files}

    print(f'\n偵測到 {len(out_groups)} 個新商品：')
    added = []
    for g in out_groups:
        maxn += 1
        tag = g.get('tag')
        if 'title' in g:
            name, priceJPY, qty = g['title'], g['price'], g['qty']
            brand = g['brand']
        else:
            pl = sorted(g['prices'])
            priceJPY = tax_price(tag['txt']) if tag else None
            if not (priceJPY and priceJPY in pl):
                priceJPY = 0
                for p in pl:
                    if any(abs(q - round(p / 1.08)) <= 2 for q in pl if q != p):
                        priceJPY = p
                        break
                if not priceJPY:
                    ok = [p for p in pl if p <= 15000]
                    priceJPY = max(ok) if ok else 0
            nl = name_lines(tag['txt']) if tag else []
            tb = [l for l in nl if re.search(r'[ァ-ヶ一-龥]', l) and not re.match(r'^[0-9]+個', l)][:1]
            name = ' '.join(tb) if tb else ''
            qty = extract_qty(tag['txt']) if tag else ''
            brand = brand_of(name, tag['txt'] if tag else '', brands)
        name = cleanup(name, fixes)
        if not name:
            name = f'（待確認）商品 {maxn:02d}'
        pf = fixes.get('priceFixes', {})
        if not priceJPY and name in pf:
            priceJPY = pf[name]
        order = list(g['photos']) + ([tag] if tag else [])
        files_out = []
        for k, p in enumerate(order, 1):
            srcf = stem2file.get(p['stem'])
            if not srcf:
                continue
            dst = imgdir / f'p{maxn:02d}-{k}.jpg'
            im = Image.open(srcf).convert('RGB')
            im.thumbnail((1200, 1200))
            im.save(dst, quality=78)
            files_out.append(f'images/{dst.name}')
        entry = {
            'title': name, 'desc': '',
            'price': (f'日本售價 JP¥{priceJPY:,}（含稅）' if priceJPY else '（價格待確認）'),
            'qty': qty or '1 入', 'priceJPY': priceJPY, 'weight_g': 0,
            'officialUrl': brands['urls'].get(brand, ''),
            'images': files_out,
            'labelImg': files_out[-1] if tag else ''
        }
        added.append(entry)
        print(f"  p{maxn:02d} [{'⚠價格待補' if not priceJPY else 'JP¥' + format(priceJPY, ',')}] {name} | {qty or '1 入'} | {len(files_out)} 張")

    if args.dry_run:
        print('\n[dry-run] 未寫入 products.json')
        return
    # 相鄰同名商品自動合併（重拍標籤造成的重複）
    merged = []
    for e in added:
        if merged and merged[-1]['title'] == e['title']:
            prev = merged[-1]
            if not prev['priceJPY'] and e['priceJPY']:
                prev['priceJPY'] = e['priceJPY']
                prev['price'] = e.get('price', prev.get('price', ''))
            for img in e['images']:
                if img not in prev['images']:
                    prev['images'].append(img)
        else:
            merged.append(e)
    added = merged
    data.extend(added)
    json.dump(data, open(pj, 'w'), ensure_ascii=False, indent=2)
    print(f'\n✓ 已加入 {len(added)} 個商品到 products.json（共 {len(data)-1}+YOKUMOKU）')
    print('下一步：commit + push 即自動更新網站。')


def by_stem(stem, recs):
    for r in recs:
        if r['stem'] == stem:
            return r
    return None

def cleanup(name, fixes):
    e = fixes.get('exact', {})
    name = name.strip()
    return e.get(name, name)

def brand_of(name, tag_txt, brands):
    t = name + ' ' + (tag_txt or '')
    for kw, b in brands['rules']:
        if kw in t:
            return b
    return None

if __name__ == '__main__':
    main()