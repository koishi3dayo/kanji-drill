# -*- coding: utf-8 -*-
"""
v2.9.1: sentence-data.js に適用した「送りがな込み下線」変換(merge_okurigana.py)を、
sentence-data-alt.js（復習モード代替問題、"漢字":{tpl:...} 形式・配列でラップしない）にも適用する。

ロジックはmerge_okurigana.pyと同じ。ALTは仕様上つねに単漢字1問なので複数{{}}は想定しない。
既定でレポートのみ。--apply でファイルを書き換える。
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_grade import load_kanji_data

BASE = Path(__file__).resolve().parent.parent
KANJI_DATA = load_kanji_data()

KUN_OKURI = {}
for kanji, grade, ons, kuns, words in KANJI_DATA:
    pairs = [tuple(kun.split('-', 1)) for kun in kuns if '-' in kun]
    if pairs:
        KUN_OKURI[kanji] = pairs

LINE_RE = re.compile(
    r'^"([^"]+)":\{tpl:"([^"]*)",reading:"([^"]*)",type:"書き"\},?$'
)

def main():
    apply_changes = '--apply' in sys.argv
    src = (BASE / 'sentence-data-alt.js').read_text(encoding='utf-8')
    lines = src.splitlines(keepends=True)

    matched, unmatched_candidates = [], []
    new_lines = []

    for line in lines:
        stripped = line.rstrip('\n')
        m = LINE_RE.match(stripped)
        if not m:
            new_lines.append(line)
            continue
        kanji, tpl, reading = m.group(1), m.group(2), m.group(3)
        trailing_comma = stripped.endswith(',')

        braces = re.findall(r'\{\{(.*?)\}\}', tpl)
        if len(braces) != 1:
            new_lines.append(line)
            continue

        target = braces[0]
        idx = tpl.index('{{' + target + '}}') + len('{{' + target + '}}')
        after = tpl[idx:]

        found = None
        for stem, okuri in KUN_OKURI.get(kanji, []):
            if reading == stem and after.startswith(okuri) and okuri:
                found = (stem, okuri)
                break

        if found:
            stem, okuri = found
            new_tpl = tpl[:idx - len('}}')] + okuri + '}}' + tpl[idx:][len(okuri):]
            new_reading = reading + okuri
            comma = ',' if trailing_comma else ''
            new_line = '"%s":{tpl:"%s",reading:"%s",type:"書き"}%s\n' % (kanji, new_tpl, new_reading, comma)
            matched.append((kanji, tpl, reading, new_tpl, new_reading))
            new_lines.append(new_line if apply_changes else line)
        else:
            if after[:1] and re.match(r'[ぁ-ん]', after[:1]):
                unmatched_candidates.append((kanji, tpl, reading, after))
            new_lines.append(line)

    print(f"=== sentence-data-alt.js 検出結果 ===")
    print(f"一致・変換対象: {len(matched)}件")
    print(f"直後がひらがなだが自動一致しなかった(要確認): {len(unmatched_candidates)}件")
    print()
    print("--- 変換対象(全件) ---")
    for kanji, tpl, reading, new_tpl, new_reading in matched:
        print(f"{kanji}: {tpl}(reading:{reading}) -> {new_tpl}(reading:{new_reading})")
    print()
    print("--- 要確認(自動一致しなかった)一覧 ---")
    for kanji, tpl, reading, after in unmatched_candidates:
        kuns = KUN_OKURI.get(kanji, [])
        print(f"{kanji}: tpl={tpl} reading={reading} 直後='{after}' 登録訓読み(送りがな有)={kuns}")

    if apply_changes:
        (BASE / 'sentence-data-alt.js').write_text(''.join(new_lines), encoding='utf-8')
        print(f"\n>>> sentence-data-alt.js に{len(matched)}件を反映しました。")
    else:
        print("\n(レポートのみ。反映するには --apply を付けて再実行)")

if __name__ == '__main__':
    main()
