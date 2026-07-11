# -*- coding: utf-8 -*-
"""
v2.9 §4.2.2: 送りがなを持つ訓読み(書きタイプ・単一{{}})の問題について、
{{}}の直後にある送りがな文字列を{{}}内に取り込み、reading も送りがな込みにする。
  例: tpl:"{{強}}いかぜ", reading:"つよ"
    → tpl:"{{強い}}かぜ", reading:"つよい"

判定方法: kanji-data.js の訓読み表記「つよ-い」のハイフンで
  「幹（つよ）」と「送りがな（い）」を取り出し、
  対象の書きタイプ問題の reading が幹と一致し、
  tplの{{}}直後の文字列がその送りがなで始まっていれば一致とみなす。

このスクリプトは既定でレポートのみ（ファイルは書き換えない）。
--apply を付けると一致した分だけ sentence-data.js を書き換える。
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_grade import load_kanji_data, strip_comments

BASE = Path(__file__).resolve().parent.parent
KANJI_DATA = load_kanji_data()

# kanji -> [(stem, okuri), ...]  （ハイフンを含む訓読みのみ）
KUN_OKURI = {}
for kanji, grade, ons, kuns, words in KANJI_DATA:
    pairs = []
    for kun in kuns:
        if '-' in kun:
            stem, okuri = kun.split('-', 1)
            pairs.append((stem, okuri))
    if pairs:
        KUN_OKURI[kanji] = pairs

LINE_RE = re.compile(
    r'^"([^"]+)":\[\{tpl:"([^"]*)",reading:"([^"]*)",type:"書き"\}\],?$'
)

def main():
    apply_changes = '--apply' in sys.argv
    src = (BASE / 'sentence-data.js').read_text(encoding='utf-8')
    lines = src.splitlines(keepends=True)

    matched, unmatched_candidates, skipped_multi = [], [], []
    new_lines = []

    for line in lines:
        m = LINE_RE.match(line.rstrip('\n'))
        if not m:
            new_lines.append(line)
            continue
        kanji, tpl, reading = m.group(1), m.group(2), m.group(3)

        # {{}}が複数(既に分割済み)のものは対象外（今回のスクリプトは単一{{}}のみ扱う）
        braces = re.findall(r'\{\{(.*?)\}\}', tpl)
        if len(braces) != 1:
            skipped_multi.append((kanji, tpl))
            new_lines.append(line)
            continue

        target = braces[0]
        # {{target}}の直後の文字列を取得
        idx = tpl.index('{{' + target + '}}') + len('{{' + target + '}}')
        after = tpl[idx:]

        found = None
        for stem, okuri in KUN_OKURI.get(kanji, []):
            if reading == stem and after.startswith(okuri) and okuri:
                found = (stem, okuri)
                break

        if found:
            stem, okuri = found
            new_target = target + okuri
            new_tpl = tpl[:idx - len('}}')] + okuri + '}}' + tpl[idx:][len(okuri):]
            new_reading = reading + okuri
            new_line = '"%s":[{tpl:"%s",reading:"%s",type:"書き"}],\n' % (kanji, new_tpl, new_reading)
            matched.append((kanji, tpl, reading, new_tpl, new_reading))
            new_lines.append(new_line if apply_changes else line)
        else:
            # 直後がひらがなで始まる(送りがなの可能性がある)のに一致しなかったもの→要確認
            if after[:1] and re.match(r'[ぁ-ん]', after[:1]):
                unmatched_candidates.append((kanji, tpl, reading, after))
            new_lines.append(line)

    print(f"=== 検出結果 ===")
    print(f"一致・変換対象: {len(matched)}件")
    print(f"複数{{}}のためスキップ: {len(skipped_multi)}件")
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
        (BASE / 'sentence-data.js').write_text(''.join(new_lines), encoding='utf-8')
        print(f"\n>>> sentence-data.js に{len(matched)}件を反映しました。")
    else:
        print("\n(レポートのみ。反映するには --apply を付けて再実行)")

if __name__ == '__main__':
    main()
