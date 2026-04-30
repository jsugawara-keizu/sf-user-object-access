"""コアロジック: Salesforce からデータを取得してユーザー別オブジェクトアクセス情報を集計する。"""

import csv
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Literal


ObjectType = Literal["custom", "standard", "managed", "all"]

# CRUD フラグの順序
_CRUD_FLAGS = [
    ("PermissionsCreate", "C"),
    ("PermissionsRead", "R"),
    ("PermissionsEdit", "U"),
    ("PermissionsDelete", "D"),
    ("PermissionsViewAllRecords", "V"),
    ("PermissionsModifyAllRecords", "M"),
]


# ─── Salesforce helpers ────────────────────────────────────────────────────────

def soql(query: str, org: str) -> list[dict]:
    """sf CLI を呼び出して SOQL クエリを実行し、レコードのリストを返す。"""
    r = subprocess.run(
        ["sf", "data", "query", "--query", query, "--target-org", org, "--json"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        try:
            msg = json.loads(r.stdout).get("message", r.stderr)
        except Exception:
            msg = r.stderr
        raise RuntimeError(msg.strip()[:300])
    data = json.loads(r.stdout)
    return data.get("result", {}).get("records", [])


def flatten(record: dict, prefix: str = "") -> dict:
    """ネストされた Salesforce レコードをフラットな dict に変換する。"""
    out = {}
    for k, v in record.items():
        if k == "attributes":
            continue
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict) and "attributes" in v:
            out.update(flatten(v, prefix=key))
        else:
            out[key] = v
    return out


# ─── Object type filters ───────────────────────────────────────────────────────

def is_custom_object(name: str) -> bool:
    """自社開発カスタムオブジェクトか判定する。
    __c で終わり __ が1組だけ = namespace prefix なし (例: Bukken__c)
    管理パッケージは __ が2組 (例: CBI_PKG__Config__c)
    """
    return name.endswith("__c") and name.count("__") == 1


def is_standard_object(name: str) -> bool:
    """標準オブジェクトか判定する。__c で終わらず __ を含まない。"""
    return not name.endswith("__c") and "__" not in name


def is_managed_object(name: str) -> bool:
    """管理パッケージオブジェクトか判定する。__c で終わり __ が2組以上 (例: NS__Obj__c)。"""
    return name.endswith("__c") and name.count("__") >= 2


def make_object_filter(object_type: ObjectType):
    """object_type に応じたフィルタ関数を返す。"""
    if object_type == "custom":
        return is_custom_object
    if object_type == "standard":
        return is_standard_object
    if object_type == "managed":
        return is_managed_object
    # "all"
    return lambda name: is_custom_object(name) or is_standard_object(name) or is_managed_object(name)


# ─── CRUD helpers ─────────────────────────────────────────────────────────────

def record_to_crud_set(record: dict) -> set[str]:
    """ObjectPermissions レコードから CRUD 文字の set を返す。"""
    result: set[str] = set()
    for field, letter in _CRUD_FLAGS:
        if record.get(field):
            result.add(letter)
    return result


def merge_crud(existing: set[str], new: set[str]) -> set[str]:
    """2つの CRUD set を OR マージする。"""
    return existing | new


def format_crud(crud_set: set[str]) -> str:
    """CRUD set を C→R→U→D 順の文字列に変換する。"""
    return "".join(letter for _, letter in _CRUD_FLAGS if letter in crud_set)


def format_object_with_crud(sobject: str, crud_set: set[str]) -> str:
    """例: Account[CRU]"""
    return f"{sobject}[{format_crud(crud_set)}]"


# ─── Main logic ───────────────────────────────────────────────────────────────

def run(org: str, out_path: Path, object_type: ObjectType = "custom", expand: bool = False) -> None:
    """メイン処理: Salesforce からデータを取得し CSV を出力する。"""

    obj_filter = make_object_filter(object_type)

    # 1. ObjectPermissions を全件取得 → フィルタ済みオブジェクトのみ残す
    #    ps_to_objects: ps_id -> { sobject -> set[CRUD letters] }
    print("ObjectPermissions を取得中...")
    obj_perms = soql(
        "SELECT ParentId, SobjectType, "
        "PermissionsCreate, PermissionsRead, PermissionsEdit, PermissionsDelete, "
        "PermissionsViewAllRecords, PermissionsModifyAllRecords "
        "FROM ObjectPermissions "
        "WHERE PermissionsRead = true OR PermissionsCreate = true "
        "OR PermissionsEdit = true OR PermissionsDelete = true "
        "OR PermissionsViewAllRecords = true OR PermissionsModifyAllRecords = true "
        "LIMIT 50000",
        org,
    )

    # ps_id -> sobject -> set[str (CRUD letters)]
    ps_to_objects: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    for r in obj_perms:
        ps_id = r.get("ParentId")
        sobject = r.get("SobjectType", "")
        if ps_id and obj_filter(sobject):
            crud = record_to_crud_set(r)
            ps_to_objects[ps_id][sobject] = merge_crud(ps_to_objects[ps_id][sobject], crud)

    matched_count = len({o for objs in ps_to_objects.values() for o in objs})
    print(f"  対象オブジェクト（権限付与あり）: {matched_count} 件")

    # 2. 権限セットグループ → コンポーネント PS の展開マップ + グループ名マップ
    print("PermissionSetGroupComponent を取得中...")
    psg_components = soql(
        "SELECT PermissionSetGroupId, PermissionSetId "
        "FROM PermissionSetGroupComponent "
        "LIMIT 50000",
        org,
    )
    psg_to_ps_ids: dict[str, set[str]] = defaultdict(set)
    for r in psg_components:
        psg_id = r.get("PermissionSetGroupId")
        ps_id = r.get("PermissionSetId")
        if psg_id and ps_id:
            psg_to_ps_ids[psg_id].add(ps_id)

    psg_records = soql("SELECT Id, MasterLabel FROM PermissionSetGroup ORDER BY MasterLabel", org)
    psg_id_to_label: dict[str, str] = {r["Id"]: r["MasterLabel"] for r in psg_records}

    # 3. アクティブユーザーの PermissionSetAssignment 取得
    print("PermissionSetAssignment を取得中...")
    assignments = soql(
        "SELECT AssigneeId, Assignee.Username, Assignee.Name, "
        "Assignee.Profile.Name, Assignee.UserRole.Name, "
        "PermissionSetId, PermissionSet.Name, PermissionSet.Label, "
        "PermissionSet.IsOwnedByProfile, PermissionSet.PermissionSetGroupId "
        "FROM PermissionSetAssignment "
        "WHERE Assignee.IsActive = true "
        "ORDER BY Assignee.Username, PermissionSetId",
        org,
    )

    # 4. ユーザーごとに集約
    #    user_objects: assignee_id -> sobject -> set[CRUD letters]  (複数 PS の union)
    user_meta: dict[str, dict] = {}
    user_objects: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    user_psets: dict[str, set[str]] = defaultdict(set)
    user_psgps: dict[str, set[str]] = defaultdict(set)

    def _merge_ps_objects(assignee_id: str, ps_id: str) -> None:
        for sobject, crud in ps_to_objects.get(ps_id, {}).items():
            user_objects[assignee_id][sobject] = merge_crud(
                user_objects[assignee_id][sobject], crud
            )

    for r in assignments:
        flat = flatten(r)
        assignee_id = flat.get("AssigneeId")
        if not assignee_id:
            continue
        if assignee_id not in user_meta:
            user_meta[assignee_id] = {
                "Username": flat.get("Assignee.Username", ""),
                "Name":     flat.get("Assignee.Name", ""),
                "Profile":  flat.get("Assignee.Profile.Name", ""),
                "Role":     flat.get("Assignee.UserRole.Name") or "",
            }

        psg_id = flat.get("PermissionSet.PermissionSetGroupId")
        is_profile_ps = flat.get("PermissionSet.IsOwnedByProfile")
        ps_id = flat.get("PermissionSetId")

        if psg_id:
            label = psg_id_to_label.get(psg_id, psg_id)
            user_psgps[assignee_id].add(label)
            for component_ps_id in psg_to_ps_ids.get(psg_id, set()):
                _merge_ps_objects(assignee_id, component_ps_id)
        elif is_profile_ps:
            if ps_id:
                _merge_ps_objects(assignee_id, ps_id)
        else:
            ps_label = flat.get("PermissionSet.Label") or flat.get("PermissionSet.Name") or ""
            if ps_label:
                user_psets[assignee_id].add(ps_label)
            if ps_id:
                _merge_ps_objects(assignee_id, ps_id)

    # 5. CSV 出力
    _USER_BASE_FIELDS = ["Username", "Name", "Profile", "Role", "PermissionSetGroups", "PermissionSets"]

    def _base(assignee_id: str, meta: dict) -> dict:
        return {
            "Username":            meta["Username"],
            "Name":                meta["Name"],
            "Profile":             meta["Profile"],
            "Role":                meta["Role"],
            "PermissionSetGroups": ";".join(sorted(user_psgps.get(assignee_id, set()))),
            "PermissionSets":      ";".join(sorted(user_psets.get(assignee_id, set()))),
        }

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if expand:
        fieldnames = _USER_BASE_FIELDS + ["Object", "Permissions"]
        rows = []
        for assignee_id, meta in sorted(user_meta.items(), key=lambda x: x[1]["Username"]):
            obj_map = user_objects.get(assignee_id, {})
            for sobject, crud in sorted(obj_map.items()):
                rows.append({**_base(assignee_id, meta), "Object": sobject, "Permissions": format_crud(crud)})
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        user_count = len({r["Username"] for r in rows})
        print(f"\n出力: {out_path}  ({user_count} ユーザー / {len(rows)} 行)")
    else:
        # カラム名: custom モードのみ後方互換の "CustomObject*" を使用
        if object_type == "custom":
            count_col = "CustomObjectCount"
            objects_col = "CustomObjects"
        else:
            count_col = "ObjectCount"
            objects_col = "Objects"

        rows = []
        for assignee_id, meta in sorted(user_meta.items(), key=lambda x: x[1]["Username"]):
            obj_map = user_objects.get(assignee_id, {})
            formatted_objs = [
                format_object_with_crud(sobject, crud)
                for sobject, crud in sorted(obj_map.items())
            ]
            rows.append({
                **_base(assignee_id, meta),
                count_col:   len(formatted_objs),
                objects_col: ";".join(formatted_objs),
            })

        fieldnames = _USER_BASE_FIELDS + [count_col, objects_col]
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

        # 6. サマリー表示
        print(f"\n出力: {out_path}  ({len(rows)} ユーザー)")
        if object_type == "custom":
            over10 = [r for r in rows if r[count_col] > 10]
            print(f"LPS 超過（10超え）: {len(over10)} ユーザー")
            if over10:
                from collections import Counter
                profile_dist = Counter(r["Profile"] for r in over10)
                print("プロファイル別内訳:")
                for profile, count in profile_dist.most_common():
                    print(f"  {count:4d}  {profile}")
