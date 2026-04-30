# sf-user-object-access

Salesforce ユーザーごとにアクセス可能なオブジェクトと CRUD 権限を CSV 出力する Python CLI ツールです。

## 機能

- **オブジェクト種別の選択**: `--object-type` オプションでカスタム・標準・両方を切り替え
- **CRUD 権限の可視化**: 各オブジェクトのアクセス権限を `Account[CRU]`、`Bukken__c[CRUD]` 形式で出力
- **権限の完全解決**: プロファイル・権限セット・権限セットグループ（コンポーネント PS に展開）を合算
- **LPS チェック**: デフォルト（custom モード）では 10 カスタムオブジェクト超過ユーザーをサマリー表示

## 動作要件

- Python 3.10 以上
- [Salesforce CLI (`sf`)](https://developer.salesforce.com/tools/salesforcecli) がインストール済みであること
- 対象 org が `sf org login` で認証済みであること
- 実行ユーザーが対象 org でオブジェクト権限の読み取り権限を持つこと

## インストール

### pipx を使う方法（推奨）

[pipx](https://pipx.pypa.io/) は CLI ツール専用の隔離環境を自動管理するツールです。
Salesforce プロジェクトを汚さずグローバルで使えるため、通常の利用にはこちらを推奨します。

**macOS**

```bash
# pipx 自体のインストール（未インストールの場合）
brew install pipx
pipx ensurepath

# sf-user-object-access をインストール
pipx install git+https://github.com/jsugawara-keizu/sf-user-object-access.git
```

**Windows (PowerShell)**

```powershell
# pipx 自体のインストール（未インストールの場合）
pip install pipx
pipx ensurepath
# ターミナルを再起動して PATH を反映

# sf-user-object-access をインストール
pipx install git+https://github.com/jsugawara-keizu/sf-user-object-access.git
```

インストール後はどのディレクトリからでも実行できます。

### pip / uv を使う方法

```bash
pip install git+https://github.com/jsugawara-keizu/sf-user-object-access.git
# または
uv tool install git+https://github.com/jsugawara-keizu/sf-user-object-access.git
```

## 使い方

```bash
sf-user-object-access --org <alias>
```

### オプション

| オプション | デフォルト | 説明 |
|---|---|---|
| `--org` | （必須） | 対象 org の alias または username |
| `--out` | `user_object_access.csv` | 出力 CSV ファイルパス |
| `--object-type` | `custom` | 対象オブジェクト種別（後述） |

### `--object-type` の値

| 値 | 説明 |
|---|---|
| `custom` | 自社開発カスタムオブジェクトのみ（namespace なし `__c`）。CSV カラム名は `CustomObjectCount` / `CustomObjects`（後方互換） |
| `standard` | 標準オブジェクトのみ（`Account`、`Contact` など）。CSV カラム名は `ObjectCount` / `Objects` |
| `managed` | 管理パッケージオブジェクトのみ（namespace あり `__c`、例: `NS__Obj__c`）。CSV カラム名は `ObjectCount` / `Objects` |
| `all` | standard + custom + managed の全種別。CSV カラム名は `ObjectCount` / `Objects` |

### 使用例

```bash
# カスタムオブジェクトのみ（LPS 制限チェック用）
sf-user-object-access --org sampleorg

# 標準オブジェクトへのアクセス確認
sf-user-object-access --org sampleorg --object-type standard --out standard_access.csv

# 管理パッケージオブジェクトのみ
sf-user-object-access --org sampleorg --object-type managed --out managed_access.csv

# すべてのオブジェクトを出力
sf-user-object-access --org sampleorg --object-type all --out full_access.csv

# 出力先を指定
sf-user-object-access --org sampleorg --out org-state/user_permissions/user_custom_object_access.csv
```

## 出力 CSV の形式

| カラム | 説明 |
|---|---|
| `Username` | ユーザー名 |
| `Name` | 氏名 |
| `Profile` | プロファイル名 |
| `Role` | ロール名 |
| `PermissionSetGroups` | 割り当てられた権限セットグループ（`;` 区切り） |
| `PermissionSets` | 割り当てられた権限セット（`;` 区切り） |
| `CustomObjectCount` / `ObjectCount` | アクセス可能なオブジェクト数 |
| `CustomObjects` / `Objects` | オブジェクトと CRUD 権限の一覧（`;` 区切り） |

### オブジェクト表示形式

```
Bukken__c[CRUD];Account[CRU];Contact[CR]
```

CRUD 文字の意味:

| 文字 | 権限 |
|---|---|
| `C` | Create（作成） |
| `R` | Read（参照） |
| `U` | Edit（編集） |
| `D` | Delete（削除） |
| `V` | View All（すべて参照） |
| `M` | Modify All（すべて変更） |

複数の権限セット・権限セットグループにまたがる権限は OR で合算されます。

## 開発

```bash
# 依存関係のインストール
pip install -e ".[dev]"

# テスト実行
pytest

# Lint
ruff check src tests

# 型チェック
mypy src
```

## ライセンス

MIT License — 詳細は [LICENSE](LICENSE) を参照してください。
