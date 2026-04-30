"""CLI エントリポイント。"""

import argparse
import sys
from pathlib import Path

from sf_user_object_access.core import ObjectType, run


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Salesforce ユーザーごとにアクセス可能なオブジェクトと CRUD 権限を CSV 出力する。\n\n"
            "権限の解決対象:\n"
            "  - プロファイル（IsOwnedByProfile=true の PermissionSet）\n"
            "  - 権限セット\n"
            "  - 権限セットグループ（コンポーネント PS に展開して合算）\n\n"
            "出力例: Account[CRU];Bukken__c[CRUD]"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--org",
        required=True,
        help="対象 org の alias または username (例: my.org)",
    )
    p.add_argument(
        "--out",
        default="user_object_access.csv",
        help="出力 CSV パス (デフォルト: user_object_access.csv)",
    )
    p.add_argument(
        "--object-type",
        choices=["custom", "standard", "managed", "all"],
        default="custom",
        dest="object_type",
        help=(
            "対象オブジェクト種別 (デフォルト: custom)\n"
            "  custom   - 自社開発カスタムオブジェクトのみ (namespace なし __c)\n"
            "  standard - 標準オブジェクトのみ\n"
            "  managed  - 管理パッケージオブジェクトのみ (namespace あり __c)\n"
            "  all      - standard + custom + managed の全種別"
        ),
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    object_type: ObjectType = args.object_type  # type: ignore[assignment]
    try:
        run(org=args.org, out_path=Path(args.out), object_type=object_type)
    except RuntimeError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)
