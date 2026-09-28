"""航空配餐业务规则：状态流转、字段校验、签收回填与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "catering"
REQUIRED_FIELDS = ["配餐单号", "关联航班", "餐食份数"]
OPTIONAL_FIELDS = ["餐食类别", "配餐车辆"]
# 列表/明细对外暴露的列：内部 status 统一通过「配餐状态」展示，避免两张皮
DISPLAY_FIELDS = ["配餐单号", "关联航班", "餐食份数", "餐食类别", "配餐车辆", "送达时刻", "接收人员", "配餐状态"]
STATUS_ORDER = ["待配送", "配送中", "已签收", "已取消"]
ACTION_RULES = {"安排配送": "配送中", "确认签收": "已签收", "取消配送": "已取消"}
# 每个动作允许的前置状态：状态只能沿链路向前走，重复/越序操作一律拒绝
ACTION_SOURCE_STATUSES = {
    "安排配送": {"待配送"},
    "确认签收": {"配送中"},
    "取消配送": {"待配送", "配送中"},
}


def _parse_portion(value: Any) -> int | None:
    """餐食份数只接受正整数；空值、小数、带文字的登记值都视为非法。"""
    text = str(value if value is not None else "").strip()
    if not text or not text.isdigit():
        return None
    portion = int(text)
    return portion if portion > 0 else None


class CateringService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = self._filter(keyword=keyword, status=status)
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._present(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return self._present(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        portion = _parse_portion(values.get("餐食份数"))
        if portion is None:
            return None, "餐食份数必须是不小于 1 的整数，请核对登记值后再提交"
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["餐食份数"] = portion
        for field in OPTIONAL_FIELDS:
            text = str(values.get(field) or "").strip()
            if text:
                entry[field] = text
        entry["送达时刻"] = ""
        entry["接收人员"] = ""
        entry["status"] = STATUS_ORDER[0]
        entry["配餐状态"] = entry["status"]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._present(entry), ""

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        values = values or {}
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"配餐单 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于航空配餐可执行范围"

        current = str(entry.get("status") or "")
        allowed = ACTION_SOURCE_STATUSES[action]
        if current not in allowed:
            hint = "、".join(allowed)
            return None, f"配餐单当前为「{current}」，不能{action}；仅「{hint}」状态允许该操作"

        if action == "确认签收":
            return self._confirm_sign(entry, values)

        target = ACTION_RULES[action]
        entry["status"] = target
        entry["配餐状态"] = target
        entry["pending"] = target in {"待配送", "配送中"}
        entry["abnormal"] = False
        return self._present(entry), f"配餐单已{action}"

    def _confirm_sign(
        self,
        entry: dict[str, Any],
        values: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        receiver = str(values.get("接收人员") or "").strip()
        if not receiver:
            return None, "签收失败：接收人员不能为空，请填写实际接收人后再确认签收"

        registered = _parse_portion(entry.get("餐食份数"))
        if registered is None:
            return None, "签收失败：该配餐单登记的餐食份数不是有效正整数，无法核对，请联系调度更正"

        raw_received = values.get("签收份数")
        if raw_received is None or not str(raw_received).strip():
            received = registered
        else:
            received = _parse_portion(raw_received)
            if received is None:
                return None, f"签收失败：签收份数「{raw_received}」不是有效正整数，请重新填写"
            if received > registered:
                return None, f"签收失败：签收份数 {received} 超出登记份数 {registered}，请按实际送达数量核对"

        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry["status"] = "已签收"
        entry["配餐状态"] = "已签收"
        entry["接收人员"] = receiver
        entry["送达时刻"] = stamp
        entry["餐食份数"] = registered
        entry["pending"] = False
        entry["abnormal"] = False
        return self._present(entry), f"签收成功：{entry.get('配餐单号', '')} 由 {receiver} 于 {stamp} 签收"

    def stats(self) -> dict[str, Any]:
        """运营卡片与类别合计口径：列表刷新后随之重算，保证两处数字一致。"""
        rows = store.rows(MODULE)
        category_portions: dict[str, int] = {}
        for row in rows:
            category = str(row.get("餐食类别") or "").strip() or "未分类"
            category_portions[category] = category_portions.get(category, 0) + (
                _parse_portion(row.get("餐食份数")) or 0
            )
        return {
            "待配送配餐": sum(1 for row in rows if row.get("status") == "待配送"),
            "配餐份数合计": sum(_parse_portion(row.get("餐食份数")) or 0 for row in rows),
            "取消单数": sum(1 for row in rows if row.get("status") == "已取消"),
            "类别份数": [
                {"餐食类别": category, "餐食份数": portion}
                for category, portion in category_portions.items()
            ],
        }

    def _filter(self, *, keyword: str | None, status: str | None) -> list[dict[str, Any]]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("配餐单号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return rows

    def _present(self, entry: dict[str, Any]) -> dict[str, Any]:
        """对外视图：配餐状态与内部 status 对齐，尚未填写的字段给空串而不是旧占位值。"""
        view: dict[str, Any] = {"id": entry["id"]}
        for field in DISPLAY_FIELDS:
            value = entry.get(field)
            view[field] = "" if value is None else value
        view["配餐状态"] = entry["status"]
        return view
