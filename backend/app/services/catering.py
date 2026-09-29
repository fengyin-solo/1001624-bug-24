"""航空配餐业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "catering"
REQUIRED_FIELDS = ["配餐单号", "关联航班", "餐食份数"]
# 列表展示用的业务列；登记时缺省的可选项统一补占位，避免列与列之间串位
DISPLAY_FIELDS = ["配餐单号", "关联航班", "餐食份数", "餐食类别", "配餐车辆", "送达时刻", "接收人员"]
SIGNED_PORTIONS_FIELD = "_签收份数"
EMPTY = "—"

STATUS_ORDER = ["待配送", "配送中", "已签收", "已取消"]
ACTION_RULES = {"安排配送": "配送中", "确认签收": "已签收", "取消配送": "已取消"}
NEGATIVE_ACTIONS = []
# 每条动作允许从哪些状态发起；签收只能发生在配送中，且终态不可再流转
ACTION_FROM: dict[str, set[str]] = {
    "安排配送": {"待配送"},
    "确认签收": {"配送中"},
    "取消配送": {"待配送", "配送中"},
}
# 仍计入运营概览“待处理”的状态
PENDING_STATUSES = {"待配送", "配送中"}


def _to_int(value: Any) -> int | None:
    """把餐食份数解析成正整数；解析不出来就交给上层提示，不做静默兜底。"""
    text = str(value).strip()
    if not text:
        return None
    try:
        number = int(text)
    except ValueError:
        return None
    return number if number > 0 else None


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    """列表输出口径：补齐展示列并让“配餐状态”与真实状态保持一致。"""
    view = dict(row)
    for field in DISPLAY_FIELDS:
        value = view.get(field)
        view[field] = value if value not in (None, "") else EMPTY
    view["配餐状态"] = row.get("status")
    return view


class CateringService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("配餐单号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [_normalize(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return _normalize(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        if _to_int(values.get("餐食份数")) is None:
            return None, ["餐食份数（需为正整数）"]
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: (str(values.get(field)).strip() if values.get(field) is not None else EMPTY)
                      for field in DISPLAY_FIELDS})
        entry["餐食份数"] = _to_int(values.get("餐食份数"))
        entry[SIGNED_PORTIONS_FIELD] = 0
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return _normalize(entry), []

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"配餐单 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于航空配餐可执行范围"
        target = ACTION_RULES[action]
        current = str(entry.get("status"))
        if current not in ACTION_FROM[action]:
            number = entry.get("配餐单号")
            if current == target:
                return None, f"配餐单 {number} 已是「{current}」状态，请勿重复{action}"
            if current == "已签收":
                return None, f"配餐单 {number} 已签收，不能再{action}"
            if current == "已取消":
                return None, f"配餐单 {number} 已取消，不能再{action}"
            return None, f"配餐单 {number} 当前为「{current}」，不能直接{action}，请先安排配送"

        values = values or {}
        if action == "确认签收":
            receiver = str(values.get("接收人员") or "").strip()
            if not receiver:
                return None, "签收失败：接收人员不能为空，请填写实际接收人"
            registered = _to_int(entry.get("餐食份数"))
            signed = _to_int(values.get("签收份数"))
            if signed is None:
                return None, "签收失败：签收份数需为正整数，请核对实际签收数量"
            if registered is not None and signed > registered:
                return None, (
                    f"签收失败：签收份数 {signed} 超出登记份数 {registered}，"
                    "请按登记数量签收或先变更配餐单"
                )
            entry["接收人员"] = receiver
            entry["送达时刻"] = str(values.get("送达时刻") or "").strip() or _now_text()
            entry[SIGNED_PORTIONS_FIELD] = signed

        entry["status"] = target
        entry["pending"] = target in PENDING_STATUSES
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return _normalize(entry), f"配餐单已{action}"
