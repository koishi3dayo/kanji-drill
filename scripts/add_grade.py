# -*- coding: utf-8 -*-
"""
新しい学年の漢字データを追記する。
- NEW_DATA（各要素: (漢字, 学年, [音], [訓], [[熟語,よみ],...], かな文, 漢字文, タイプ)）を受け取り
- kanji-data.js に [漢字,学年,[音],[訓],[[熟語,よみ]...]] を追記
- 全kanji-data（既存＋新規）から熟語辞書を作り、新規の「かな文→漢字文」を
  既習漢字化した {tpl,reading,type} に変換して sentence-data.js に追記
既存の安全な変換ロジック（2文字以上の熟語のみ辞書化・助詞ブロックリスト）を踏襲する。
"""
import json, re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

PARTICLE_BLOCKLIST = {
    'の','に','を','は','が','と','で','も','や','へ','か','な','ね',
    'よ','し','た','て','だ','ば','ん','ら','り','る','れ',
    'から','まで','より','ので','のに','とも','など','けど','こと',
}

def strip_comments(text):
    return '\n'.join(l for l in text.splitlines() if not l.strip().startswith('//'))

def load_kanji_data():
    text = strip_comments((BASE / 'kanji-data.js').read_text(encoding='utf-8'))
    s = text.index('['); e = text.rindex(']') + 1
    return json.loads(text[s:e])

def build_dictionary(kanji_data):
    entries = []
    for row in kanji_data:
        kanji, grade, ons, kuns, words = row
        for word, reading in words:
            if len(word) < 2 or len(reading) < 2: continue
            if reading in PARTICLE_BLOCKLIST: continue
            entries.append((reading, word))
    entries.sort(key=lambda e: -len(e[0]))
    seen = {}
    for reading, word in entries:
        seen.setdefault(reading, word)
    return seen

def apply_dict(text, dic, maxlen):
    out = []; i = 0; n = len(text)
    while i < n:
        matched = False
        for L in range(min(maxlen, n - i), 0, -1):
            piece = text[i:i+L]
            if piece in dic:
                out.append(dic[piece]); i += L; matched = True; break
        if not matched:
            out.append(text[i]); i += 1
    return ''.join(out)

def diff_range(kana, ans):
    p = 0
    while p < len(kana) and p < len(ans) and kana[p] == ans[p]: p += 1
    s = 0
    while s < len(kana)-p and s < len(ans)-p and kana[len(kana)-1-s] == ans[len(ans)-1-s]: s += 1
    return (p, len(kana)-s), (p, len(ans)-s)

def js_kanji_row(kanji, grade, ons, kuns, words):
    def arr(a): return '[' + ','.join(json.dumps(x, ensure_ascii=False) for x in a) + ']'
    w = '[' + ','.join('[' + json.dumps(a, ensure_ascii=False) + ',' + json.dumps(b, ensure_ascii=False) + ']' for a, b in words) + ']'
    return f'  [{json.dumps(kanji, ensure_ascii=False)},{json.dumps(grade, ensure_ascii=False)},{arr(ons)},{arr(kuns)},{w}]'

def run(NEW_DATA, grade_label):
    # 1. kanji-data.js に追記
    kd_path = BASE / 'kanji-data.js'
    kd = kd_path.read_text(encoding='utf-8')
    rows = [js_kanji_row(k, g, ons, kuns, words) for (k, g, ons, kuns, words, *_ ) in NEW_DATA]
    insert = ',\n\n  // ── ' + grade_label + ' ──\n' + ',\n'.join(rows) + '\n'
    idx = kd.rindex('\n];')
    kd = kd[:idx] + insert + kd[idx+1:]
    kd_path.write_text(kd, encoding='utf-8')

    # 2. 辞書を作り直し（新規を含む全kanji-data）
    dic = build_dictionary(load_kanji_data())
    maxlen = max(len(k) for k in dic)

    # 3. sentence-data.js に追記
    sd_path = BASE / 'sentence-data.js'
    sd = sd_path.read_text(encoding='utf-8')
    lines = []
    for (k, g, ons, kuns, words, kana, ans, qtype) in NEW_DATA:
        (ka, kb), (aa, ab) = diff_range(kana, ans)
        target = ans[aa:ab]
        reading = kana[ka:kb]
        before = apply_dict(kana[:ka], dic, maxlen)
        after = apply_dict(kana[kb:], dic, maxlen)
        tpl = f'{before}{{{{{target}}}}}{after}'
        lines.append(f'"{k}":[{{tpl:{json.dumps(tpl, ensure_ascii=False)},reading:{json.dumps(reading, ensure_ascii=False)},type:{json.dumps(qtype, ensure_ascii=False)}}}]')
    insert2 = ',\n// ── ' + grade_label + ' ──\n' + ',\n'.join(lines) + '\n'
    idx2 = sd.rindex('\n};')
    sd = sd[:idx2] + insert2 + sd[idx2+1:]
    sd_path.write_text(sd, encoding='utf-8')
    print(f'{grade_label}: {len(NEW_DATA)}件を追記しました')
