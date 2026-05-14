"""知识点标签规范化。"""


def normalize_knowledge_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in tags:
        s = str(raw).strip()
        if not s or len(s) > 32 or s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= 6:
            break
    return out
