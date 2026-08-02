# -*- coding: utf-8 -*-
"""
sentence-data.js / sentence-data-alt.js の検証ハーネス。
これまで手作業・使い捨てスクリプトで繰り返し行ってきたチェックを1本にまとめたもの。

実行:
    python scripts/check_data.py

チェック内容:
  1. 構文の健全性（波括弧の対応、行フォーマット）
  2. {{}}の数とreadingの数が一致しているか
  3. 過去に見つかった誤変換ワードの再発（回帰チェック）
  4. 熟語辞書内の同音異義語衝突（読みが同じ熟語が複数登録されている）
  5. 単漢字（送りがな付き訓読み）どうしの同音異義語衝突 ← 今回「似る/煮る」で発覚した新種
  6. 復習モードで未習漢字を含む出題が出ないか
  7. 「熟語+かな1〜2文字+熟語」の挟み込みパターン（誤変換の典型形）

このスクリプトは診断のみ。ファイルは一切書き換えない。
"""
import re, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_grade import load_kanji_data, strip_comments

BASE = Path(__file__).resolve().parent.parent
KANJI_DATA = load_kanji_data()
KANJI_GRADE = {e[0]: e[1] for e in KANJI_DATA}
GRADE_ORDER = ['2', '3', '4', '5', '6', 'J1', 'J2', 'J3']

ok_count = 0
ng_count = 0
review_count = 0


def report(title, ok, detail=""):
    """自動でPASS/FAILを判定できる項目用。ok=Falseは終了コードに反映される。"""
    global ok_count, ng_count
    mark = "OK" if ok else "NG"
    if ok:
        ok_count += 1
    else:
        ng_count += 1
    print(f"[{mark}] {title}")
    if detail:
        print(detail)


def report_review(title, items, detail=""):
    """機械では正誤を断定できず、常に人の目視確認が必要な項目用。
    候補が0件でなくても異常ではないため終了コード(NG)には数えない。"""
    global review_count
    review_count += len(items) if hasattr(items, '__len__') else (1 if items else 0)
    n = len(items) if hasattr(items, '__len__') else items
    print(f"[REVIEW] {title} ({n}件)")
    if detail:
        print(detail)


# ── データ読み込み ──
def parse(fname, alt=False):
    text = strip_comments((BASE / fname).read_text(encoding='utf-8'))
    body = text[text.index('{'):text.rindex('}') + 1]
    if alt:
        RE = re.compile(r'"([^"]+)":\{tpl:"((?:[^"\\]|\\.)*)",reading:(\[[^\]]*\]|"[^"]*"),type:"([^"]+)"\}')
    else:
        RE = re.compile(r'"([^"]+)":\[\{tpl:"((?:[^"\\]|\\.)*)",reading:(\[[^\]]*\]|"[^"]*"),type:"([^"]+)"\}\]')
    out = {}
    for m in RE.finditer(body):
        kanji, tpl, reading_raw, typ = m.groups()
        out[kanji] = {'tpl': tpl, 'reading': json.loads(reading_raw), 'type': typ}
    return out

SENTENCE_DATA = parse('sentence-data.js')
SENTENCE_DATA_ALT = parse('sentence-data-alt.js', alt=True)

print("=" * 70)
print(f"読み込み: sentence-data.js={len(SENTENCE_DATA)}件 / alt={len(SENTENCE_DATA_ALT)}件")
print("=" * 70)


# ── 1. 構文の健全性 ──
def check_structure():
    text = (BASE / 'sentence-data.js').read_text(encoding='utf-8')
    brace_diff = text.count('{') - text.count('}')
    report("波括弧の対応 (sentence-data.js)", brace_diff == 0, f"  差分: {brace_diff}")

    lines = [l for l in text.splitlines() if l.strip().startswith('"')]
    pat = re.compile(r'^"[^"]+":\[\{tpl:"[^"]*",reading:(\"[^"]*\"|\[\"[^"]*\",\"[^"]*\"\]),type:"(書き|熟語)"\}\],?$')
    bad = [l for l in lines if not pat.match(l)]
    report(f"行フォーマット一致 ({len(lines)}行)", len(bad) == 0,
           "\n".join(f"  NG: {l}" for l in bad[:10]))

check_structure()


# ── 2. {{}}の数とreadingの数 ──
def check_target_count():
    mismatch = []
    for src_name, data in [('sentence-data.js', SENTENCE_DATA), ('sentence-data-alt.js', SENTENCE_DATA_ALT)]:
        for kanji, e in data.items():
            n_targets = len(re.findall(r'\{\{(.*?)\}\}', e['tpl']))
            n_readings = len(e['reading']) if isinstance(e['reading'], list) else 1
            if n_targets != n_readings:
                mismatch.append((src_name, kanji, n_targets, n_readings))
    report("{{}}数とreading数の一致", len(mismatch) == 0,
           "\n".join(f"  NG: {s} {k}: targets={t} readings={r}" for s, k, t, r in mismatch))

check_target_count()


# ── 3. 既知の誤変換ワードの回帰チェック ──
# ここに入れるのは「文脈によらず常に誤り」と確定している語のみ。
# 「画家」「坑道」のように正当な熟語として存在しうる語は、単純な文字列検索だと
# 誤検知（正しい用例まで拾ってしまう）するため入れない（→項目5のような文脈依存チェックに任せる）。
KNOWN_BAD_WORDS = ['未知', '仮名', '意味', '事故く', '医院かい', '唱歌い']

def check_known_bad_words():
    hits = []
    for src_name in ['sentence-data.js', 'sentence-data-alt.js']:
        # 行番号は元ファイルそのままで数える（strip_comments後だとコメント行の分ズレるため）
        text = (BASE / src_name).read_text(encoding='utf-8')
        for word in KNOWN_BAD_WORDS:
            for m in re.finditer(re.escape(word), text):
                line_no = text.count('\n', 0, m.start()) + 1
                hits.append((src_name, word, line_no))
    report("既知の誤変換ワードの再発なし", len(hits) == 0,
           "\n".join(f"  NG: {s}:{l} に「{w}」" for s, w, l in hits))

check_known_bad_words()


# ── 4. 熟語辞書内の同音異義語衝突 ──
def build_jukugo_dict():
    by_reading = {}
    for kanji, grade, ons, kuns, words in KANJI_DATA:
        for word, reading in words:
            if len(word) >= 2:
                by_reading.setdefault(reading, set()).add(word)
    return {r: sorted(ws) for r, ws in by_reading.items() if len(ws) >= 2}

def check_jukugo_collisions():
    collisions = build_jukugo_dict()
    both_used = []
    for reading, words in collisions.items():
        used_in = {}
        for src_name, data in [('main', SENTENCE_DATA), ('alt', SENTENCE_DATA_ALT)]:
            text = strip_comments((BASE / ('sentence-data.js' if src_name == 'main' else 'sentence-data-alt.js')).read_text(encoding='utf-8'))
            for w in words:
                if w in text:
                    used_in.setdefault(w, []).append(src_name)
        if len(used_in) >= 2:
            both_used.append((reading, used_in))
    report_review(f"熟語辞書の同音異義語衝突候補 ({len(collisions)}組) のうち両方が実際に使われているもの",
           both_used,
           "\n".join(f"  要目視確認: 読み[{r}] {list(u.keys())}" for r, u in both_used) +
           ("\n  ※常に一定数出るのが正常。データ追加のたびに新しい候補が出たら目視確認する。" if both_used else ""))

check_jukugo_collisions()


# ── 5. 単漢字（送りがな付き訓読み）どうしの同音異義語衝突 ──
def check_single_kanji_okuri_collisions():
    by_stem_okuri = {}
    for kanji, grade, ons, kuns, words in KANJI_DATA:
        for kun in kuns:
            if '-' in kun:
                stem, okuri = kun.split('-', 1)
                by_stem_okuri.setdefault((stem, okuri), []).append(kanji)

    collisions = {k: v for k, v in by_stem_okuri.items() if len(v) >= 2}
    both_used = []
    main_text = strip_comments((BASE / 'sentence-data.js').read_text(encoding='utf-8'))
    alt_text = strip_comments((BASE / 'sentence-data-alt.js').read_text(encoding='utf-8'))
    for (stem, okuri), kanjis in collisions.items():
        word = stem  # 表示用
        used_in = {}
        for k in kanjis:
            form = k + okuri  # 例: "似"+"る" = "似る"
            hits_main = len(re.findall(re.escape(form), main_text))
            hits_alt = len(re.findall(re.escape(form), alt_text))
            if hits_main or hits_alt:
                used_in[form] = (hits_main, hits_alt)
        if len(used_in) >= 2:
            both_used.append((stem, okuri, kanjis, used_in))

    report_review(f"単漢字どうしの同音異義語衝突候補 ({len(collisions)}組) のうち両方が実際に使われているもの",
           both_used,
           "\n".join(
               f"  要目視確認: 読み[{s}{o}] 候補漢字{ks} → 使用状況:" +
               "".join(f"\n      {form}: main={m}件 alt={a}件" for form, (m, a) in u.items())
               for s, o, ks, u in both_used
           ) + ("\n  ※常に一定数出るのが正常。データ追加のたびに新しい候補が出たら目視確認する。" if both_used else ""))

check_single_kanji_okuri_collisions()


# ── 6. 復習モードで未習漢字を含む出題が出ないか ──
def check_review_mode():
    ALLP = []
    for e in KANJI_DATA:
        kanji, grade = e[0], e[1]
        d = SENTENCE_DATA.get(kanji)
        if d:
            ALLP.append({'kanji': kanji, 'grade': grade, 'tpl': d['tpl']})

    def all_target_chars(tpl):
        return [ch for m in re.finditer(r'\{\{(.*?)\}\}', tpl) for ch in m.group(1) if re.match(r'[一-鿿]', ch)]

    class Store:
        def __init__(self, grade, lbg):
            self.grade = grade
            self.lbg = lbg
        def is_char_learned(self, ch):
            g = KANJI_GRADE.get(ch)
            if not g:
                return True
            cur, ci = GRADE_ORDER.index(self.grade), GRADE_ORDER.index(g)
            if ci < cur:
                return True
            if ci == cur:
                return ch in self.lbg.get(g, [])
            return False

    def is_problem_learned(store, tpl):
        matches = re.findall(r'\{\{(.*?)\}\}', tpl)
        if not matches:
            return False
        return all(store.is_char_learned(ch) for content in matches for ch in content if re.match(r'[一-鿿]', ch))

    def get_review_candidate(store, p):
        if is_problem_learned(store, p['tpl']):
            return p['tpl']
        alt = SENTENCE_DATA_ALT.get(p['kanji'])
        if alt and is_problem_learned(store, alt['tpl']):
            return alt['tpl']
        return None

    violations = []
    for grade in GRADE_ORDER:
        idx = GRADE_ORDER.index(grade)
        lbg = {GRADE_ORDER[i]: [e[0] for e in KANJI_DATA if e[1] == GRADE_ORDER[i]] for i in range(idx + 1)}
        store = Store(grade, lbg)
        for p in ALLP:
            cand = get_review_candidate(store, p)
            if cand is None:
                continue
            bad = [c for c in all_target_chars(cand) if not store.is_char_learned(c)]
            if bad:
                violations.append((grade, p['kanji'], cand, bad))

    report(f"復習モードで未習漢字を含む出題なし", len(violations) == 0,
           "\n".join(f"  NG: {g} {k} -> {c} 未習:{b}" for g, k, c, b in violations[:10]))

check_review_mode()


# ── 7. 「熟語+かな1〜2文字+熟語」の挟み込みパターン ──
def check_sandwich_pattern():
    hits = []
    for src_name in ['sentence-data.js', 'sentence-data-alt.js']:
        text = strip_comments((BASE / src_name).read_text(encoding='utf-8'))
        for line in text.splitlines():
            if not line.strip().startswith('"'):
                continue
            outside = re.sub(r'\{\{.*?\}\}', '', line)
            for m in re.finditer(r'[一-鿿]{2,}[ぁ-ん]{1,2}[一-鿿]{2,}', outside):
                hits.append((src_name, line.split(':')[0], m.group(0)))
    report_review("「熟語+かな+熟語」挟み込みパターン",
           hits,
           "\n".join(f"  確認: {s} {k}: ...{h}..." for s, k, h in hits) +
           (f"\n  → 文脈が自然なら問題なし。" if hits else "  該当なし。"))

check_sandwich_pattern()


print("\n" + "=" * 70)
print(f"結果: OK {ok_count}件 / NG {ng_count}件 / REVIEW(要目視確認・異常ではない) {review_count}件")
print("=" * 70)
sys.exit(1 if ng_count else 0)
