# -*- coding: utf-8 -*-
"""
sentence-data.js を「対象漢字以外は既習漢字に変換したテンプレート形式」へ変換する。

手順:
 1. kanji-data.js から 漢字→(訓読み, 音読み, 熟語) の辞書を作る
 2. 辞書から「読み → 漢字表記」の置換テーブルを作る（長い読みを優先）
 3. sentence-data.js の各短文について、対象漢字の差分範囲をマスクしたうえで
    残りの平仮名部分を辞書で漢字に置換する
 4. {{対象漢字}} マーカー付きテンプレートとして出力する
"""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

def strip_js_comments(text):
    lines = text.splitlines()
    out = []
    for line in lines:
        if line.strip().startswith('//'):
            continue
        out.append(line)
    return '\n'.join(out)

def load_kanji_data():
    text = (BASE / 'kanji-data.js').read_text(encoding='utf-8')
    text = strip_js_comments(text)
    start = text.index('[')
    end = text.rindex(']') + 1
    return json.loads(text[start:end])

def load_sentence_data():
    text = (BASE / 'sentence-data.js').read_text(encoding='utf-8')
    text = strip_js_comments(text)
    start = text.index('{')
    end = text.rindex('}') + 1
    return json.loads(text[start:end])

def diff_range(kana, ans):
    p = 0
    while p < len(kana) and p < len(ans) and kana[p] == ans[p]:
        p += 1
    s = 0
    while s < len(kana) - p and s < len(ans) - p and kana[len(kana) - 1 - s] == ans[len(ans) - 1 - s]:
        s += 1
    return (p, len(kana) - s), (p, len(ans) - s)

# 助詞・機能語など、絶対に漢字化してはいけない読み（安全側のブロックリスト）
PARTICLE_BLOCKLIST = {
    'の', 'に', 'を', 'は', 'が', 'と', 'で', 'も', 'や', 'へ', 'か', 'な', 'ね',
    'よ', 'し', 'た', 'て', 'だ', 'ば', 'ん', 'ら', 'り', 'る', 'れ',
    'から', 'まで', 'より', 'ので', 'のに', 'とも', 'など', 'けど', 'こと',
}

def build_dictionary(kanji_data):
    """reading(かな) -> kanji_text の置換テーブルを作る。
    誤変換防止のため、2文字以上の熟語のみを対象にする（単漢字の訓読みは
    助詞・他の単語と同音衝突しやすいため対象外とする）。"""
    entries = []  # (reading, kanji_text, priority)
    for row in kanji_data:
        kanji, grade, ons, kuns, words = row[0], row[1], row[2], row[3], row[4]
        # 熟語（2文字以上の単語）のみを対象にする
        for word, reading in words:
            if len(word) < 2 or len(reading) < 2:
                continue
            if reading in PARTICLE_BLOCKLIST:
                continue
            entries.append((reading, word, 3))
    # 長い読み優先
    entries.sort(key=lambda e: (-len(e[0]), -e[2]))
    seen = {}
    for reading, kanji_text, priority in entries:
        if reading not in seen:
            seen[reading] = kanji_text
    return seen

def apply_dictionary(text, dictionary, max_len):
    """text 中の平仮名を、辞書にマッチする範囲だけ漢字表記に置換する(最長一致・非重複)。"""
    result = []
    i = 0
    n = len(text)
    while i < n:
        matched = False
        upper = min(max_len, n - i)
        for length in range(upper, 0, -1):
            piece = text[i:i+length]
            if piece == '\x00':
                continue
            if piece in dictionary:
                result.append(dictionary[piece])
                i += length
                matched = True
                break
        if not matched:
            result.append(text[i])
            i += 1
    return ''.join(result)

def main():
    kanji_data = load_kanji_data()
    sentence_data = load_sentence_data()
    dictionary = build_dictionary(kanji_data)
    max_len = max(len(k) for k in dictionary.keys())

    out = {}
    stats = {'total': 0, 'kanji_added': 0}
    for target_kanji, sents in sentence_data.items():
        new_list = []
        for kana, ans, qtype in sents:
            stats['total'] += 1
            (ka, kb), (aa, ab) = diff_range(kana, ans)
            target_reading = kana[ka:kb]
            target_text = ans[aa:ab]

            before = kana[:ka]
            after = kana[kb:]
            before_conv = apply_dictionary(before, dictionary, max_len)
            after_conv = apply_dictionary(after, dictionary, max_len)

            if before_conv != before or after_conv != after:
                stats['kanji_added'] += 1

            tpl = f"{before_conv}{{{{{target_text}}}}}{after_conv}"
            new_list.append({
                'tpl': tpl,
                'reading': target_reading,
                'type': qtype
            })
        out[target_kanji] = new_list

    print(f"総文数: {stats['total']}  既習漢字を追加できた文: {stats['kanji_added']}")

    # JS ファイルとして書き出す
    lines = []
    lines.append('// 出題用テンプレートデータ（自動生成 + 要レビュー）')
    lines.append('// tpl 中の {{漢字}} が出題対象。reading はその読み（かな）で問題文に表示される。')
    lines.append('// 出題文 = tpl の {{...}} を reading に置換 / 答え文 = tpl の {{ }} を外すだけ')
    lines.append('const SENTENCE_DATA = {')
    keys = list(out.keys())
    for idx, k in enumerate(keys):
        arr = out[k]
        items = ', '.join(
            '{tpl:%s,reading:%s,type:%s}' % (
                json.dumps(e['tpl'], ensure_ascii=False),
                json.dumps(e['reading'], ensure_ascii=False),
                json.dumps(e['type'], ensure_ascii=False),
            ) for e in arr
        )
        comma = ',' if idx < len(keys) - 1 else ''
        lines.append(f'"{k}":[{items}]{comma}')
    lines.append('};')

    (BASE / 'sentence-data.js').write_text('\n'.join(lines), encoding='utf-8')
    print("sentence-data.js を書き換えました。")

if __name__ == '__main__':
    main()
