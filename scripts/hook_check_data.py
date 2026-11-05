# -*- coding: utf-8 -*-
"""
Claude Code の PostToolUse フック（Write|Edit）用。
sentence-data.js / sentence-data-alt.js が編集されたら、scripts/check_data.py を実行して結果を返す。

stdin : フックのJSON（tool_input.file_path などを含む）
動作  :
  - 対象外のファイル            → 何もしない（exit 0・出力なし）
  - 対象ファイルで検証OK        → {"systemMessage": "…"} を出力（exit 0）。利用者に1行で結果が表示される
  - 対象ファイルで検証NG        → 詳細を stderr に出して exit 2。Claude に差し戻され、直すよう促される

check_data.py は読み取り専用の診断スクリプトで、ファイルは書き換えない。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = {
    (ROOT / 'sentence-data.js').resolve(),
    (ROOT / 'sentence-data-alt.js').resolve(),
}


def edited_path(payload):
    ti = payload.get('tool_input') or {}
    tr = payload.get('tool_response')
    f = ti.get('file_path') or (tr.get('filePath') if isinstance(tr, dict) else '') or ''
    return Path(f).resolve() if f else None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # 想定外の入力では何もしない（編集作業を妨げない）

    path = edited_path(payload)
    if path is None or path not in TARGETS:
        return 0

    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    try:
        r = subprocess.run(
            [sys.executable, str(ROOT / 'scripts' / 'check_data.py')],
            capture_output=True, encoding='utf-8', env=env, timeout=60,
        )
    except subprocess.TimeoutExpired:
        sys.stderr.buffer.write('check_data.py が60秒でタイムアウトしました。\n'.encode('utf-8'))
        return 2

    summary = next((l for l in r.stdout.splitlines() if l.startswith('結果:')), '(結果行なし)')

    if r.returncode == 0:
        msg = f'データ検証OK ({path.name}): {summary}'
        print(json.dumps({'systemMessage': msg}))  # ASCIIエスケープで出力（文字コード依存を避ける）
        return 0

    text = (
        f'データ検証NG: {path.name} の編集後に check_data.py が失敗しました。'
        f'[NG]の項目を直してください。\n\n{r.stdout}\n{r.stderr}'
    )
    sys.stderr.buffer.write(text.encode('utf-8'))
    return 2


if __name__ == '__main__':
    sys.exit(main())
