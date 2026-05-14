"""知识点标签规范化与口径统一。"""

# 细粒度 / 子技能标签 -> 统一上位标签（同一考查单元内优先用右侧名称）
_TAG_UNIFY: dict[str, str] = {
    "小数加法": "小数四则运算",
    "小数减法": "小数四则运算",
    "小数乘法": "小数四则运算",
    "小数除法": "小数四则运算",
    "小数加减法": "小数四则运算",
    "小数乘除法": "小数四则运算",
    "小数混合运算": "小数四则运算",
    "分数加法": "分数四则运算",
    "分数减法": "分数四则运算",
    "分数乘法": "分数四则运算",
    "分数除法": "分数四则运算",
    "分数加减法": "分数四则运算",
    "分数乘除法": "分数四则运算",
    "分数混合运算": "分数四则运算",
    "整数加法": "整数四则运算",
    "整数减法": "整数四则运算",
    "整数乘法": "整数四则运算",
    "整数除法": "整数四则运算",
    "整数四则混合运算": "整数四则运算",
    "有理数加法": "有理数运算",
    "有理数减法": "有理数运算",
    "有理数乘法": "有理数运算",
    "有理数除法": "有理数运算",
    "有理数混合运算": "有理数运算",
}


def unify_knowledge_tag(tag: str) -> str:
    s = tag.strip()
    if not s:
        return s
    return _TAG_UNIFY.get(s, s)


def unify_knowledge_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    return [unify_knowledge_tag(str(t)) for t in tags]


def normalize_knowledge_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in unify_knowledge_tags(tags):
        s = str(raw).strip()
        if not s or len(s) > 32 or s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= 6:
            break
    return out
