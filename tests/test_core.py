"""core モジュールのユニットテスト（subprocess 呼び出しなし）。"""

import pytest

from sf_user_object_access.core import (
    flatten,
    format_crud,
    format_object_with_crud,
    is_custom_object,
    is_managed_object,
    is_standard_object,
    make_object_filter,
    merge_crud,
    record_to_crud_set,
)


# ─── is_custom_object ─────────────────────────────────────────────────────────

class TestIsCustomObject:
    def test_simple_custom(self):
        assert is_custom_object("Bukken__c") is True

    def test_namespaced_managed_package(self):
        assert is_custom_object("CBI_PKG__Config__c") is False

    def test_standard_object(self):
        assert is_custom_object("Account") is False

    def test_custom_field_not_object(self):
        # __c で終わるが __ が1組だけのフィールド名 (実際には SobjectType には来ない想定)
        assert is_custom_object("MyField__c") is True

    def test_relationship_field(self):
        # 管理パッケージのリレーション項目風
        assert is_custom_object("NS__Obj__c") is False


# ─── is_standard_object ───────────────────────────────────────────────────────

class TestIsStandardObject:
    def test_account(self):
        assert is_standard_object("Account") is True

    def test_contact(self):
        assert is_standard_object("Contact") is True

    def test_custom_object(self):
        assert is_standard_object("Bukken__c") is False

    def test_namespaced(self):
        assert is_standard_object("CBI_PKG__Config__c") is False

    def test_object_with_single_underscore(self):
        # 単一アンダースコアは標準オブジェクト扱い (__  は2連なので含まない)
        assert is_standard_object("My_Object") is True


# ─── is_managed_object ────────────────────────────────────────────────────────

class TestIsManagedObject:
    def test_namespaced_custom(self):
        assert is_managed_object("NS__Obj__c") is True

    def test_multi_segment_namespace(self):
        assert is_managed_object("CBI_PKG__Config__c") is True

    def test_first_party_custom(self):
        assert is_managed_object("Bukken__c") is False

    def test_standard(self):
        assert is_managed_object("Account") is False


# ─── make_object_filter ───────────────────────────────────────────────────────

class TestMakeObjectFilter:
    def test_custom_filter(self):
        f = make_object_filter("custom")
        assert f("Bukken__c") is True
        assert f("Account") is False
        assert f("NS__Obj__c") is False

    def test_standard_filter(self):
        f = make_object_filter("standard")
        assert f("Account") is True
        assert f("Bukken__c") is False

    def test_managed_filter(self):
        f = make_object_filter("managed")
        assert f("NS__Obj__c") is True
        assert f("CBI_PKG__Config__c") is True
        assert f("Bukken__c") is False
        assert f("Account") is False

    def test_all_filter(self):
        f = make_object_filter("all")
        assert f("Account") is True
        assert f("Bukken__c") is True
        assert f("NS__Obj__c") is True  # managed も含む


# ─── record_to_crud_set ───────────────────────────────────────────────────────

class TestRecordToCrudSet:
    def test_full_crud(self):
        r = {
            "PermissionsCreate": True,
            "PermissionsRead": True,
            "PermissionsEdit": True,
            "PermissionsDelete": True,
        }
        assert record_to_crud_set(r) == {"C", "R", "U", "D"}

    def test_full_crudvm(self):
        r = {
            "PermissionsCreate": True,
            "PermissionsRead": True,
            "PermissionsEdit": True,
            "PermissionsDelete": True,
            "PermissionsViewAllRecords": True,
            "PermissionsModifyAllRecords": True,
        }
        assert record_to_crud_set(r) == {"C", "R", "U", "D", "V", "M"}

    def test_view_all_only(self):
        r = {"PermissionsViewAllRecords": True, "PermissionsModifyAllRecords": False}
        assert record_to_crud_set(r) == {"V"}

    def test_read_only(self):
        r = {
            "PermissionsCreate": False,
            "PermissionsRead": True,
            "PermissionsEdit": False,
            "PermissionsDelete": False,
        }
        assert record_to_crud_set(r) == {"R"}

    def test_create_and_read(self):
        r = {
            "PermissionsCreate": True,
            "PermissionsRead": True,
            "PermissionsEdit": False,
            "PermissionsDelete": False,
        }
        assert record_to_crud_set(r) == {"C", "R"}

    def test_missing_flags_treated_as_false(self):
        assert record_to_crud_set({}) == set()


# ─── merge_crud ───────────────────────────────────────────────────────────────

class TestMergeCrud:
    def test_union(self):
        assert merge_crud({"C", "R"}, {"R", "U"}) == {"C", "R", "U"}

    def test_empty_sets(self):
        assert merge_crud(set(), set()) == set()

    def test_one_empty(self):
        assert merge_crud({"D"}, set()) == {"D"}


# ─── format_crud ─────────────────────────────────────────────────────────────

class TestFormatCrud:
    def test_full_crud(self):
        assert format_crud({"C", "R", "U", "D"}) == "CRUD"

    def test_full_crudvm(self):
        assert format_crud({"C", "R", "U", "D", "V", "M"}) == "CRUDVM"

    def test_view_all(self):
        assert format_crud({"R", "V"}) == "RV"

    def test_modify_all(self):
        assert format_crud({"C", "R", "U", "D", "M"}) == "CRUDM"

    def test_read_only(self):
        assert format_crud({"R"}) == "R"

    def test_create_read_update(self):
        assert format_crud({"U", "C", "R"}) == "CRU"

    def test_order_is_fixed(self):
        assert format_crud({"D", "C"}) == "CD"

    def test_empty(self):
        assert format_crud(set()) == ""


# ─── format_object_with_crud ─────────────────────────────────────────────────

class TestFormatObjectWithCrud:
    def test_full(self):
        assert format_object_with_crud("Bukken__c", {"C", "R", "U", "D"}) == "Bukken__c[CRUD]"

    def test_read_only(self):
        assert format_object_with_crud("Account", {"R"}) == "Account[R]"

    def test_create_read(self):
        assert format_object_with_crud("Contact", {"C", "R"}) == "Contact[CR]"


# ─── flatten ─────────────────────────────────────────────────────────────────

class TestFlatten:
    def test_simple(self):
        r = {"Id": "001", "Name": "foo"}
        assert flatten(r) == {"Id": "001", "Name": "foo"}

    def test_nested(self):
        r = {
            "AssigneeId": "005",
            "Assignee": {
                "attributes": {"type": "User"},
                "Username": "user@example.com",
                "Profile": {
                    "attributes": {"type": "Profile"},
                    "Name": "System Administrator",
                },
            },
        }
        result = flatten(r)
        assert result["AssigneeId"] == "005"
        assert result["Assignee.Username"] == "user@example.com"
        assert result["Assignee.Profile.Name"] == "System Administrator"

    def test_attributes_excluded(self):
        r = {"attributes": {"type": "PermissionSetAssignment"}, "Id": "0Pa000"}
        result = flatten(r)
        assert "attributes" not in result
        assert result["Id"] == "0Pa000"

# ─── format_crud (expand 出力確認) ───────────────────────────────────────────

class TestFormatCrudExpand:
    def test_crudvm_order(self):
        assert format_crud({"M", "V", "D", "U", "R", "C"}) == "CRUDVM"

    def test_permissions_only_vm(self):
        assert format_crud({"V", "M"}) == "VM"

    def test_empty_means_no_access(self):
        # ピボット列でアクセスなしは空文字
        assert format_crud(set()) == ""
