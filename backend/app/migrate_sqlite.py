"""SQLite 轻量迁移：为已有库补充新增列。"""

from sqlalchemy import text


def apply_sqlite_migrations(sync_conn) -> None:
    def cols(table: str) -> set[str]:
        rows = sync_conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return {r[1] for r in rows}

    t = "mistakes"
    if t in _tables(sync_conn):
        c = cols(t)
        if "user_id" not in c:
            sync_conn.execute(text("ALTER TABLE mistakes ADD COLUMN user_id VARCHAR(36)"))
        if "is_mastered" not in c:
            sync_conn.execute(
                text("ALTER TABLE mistakes ADD COLUMN is_mastered BOOLEAN NOT NULL DEFAULT 0")
            )
        if "knowledge_tags" not in c:
            sync_conn.execute(
                text("ALTER TABLE mistakes ADD COLUMN knowledge_tags JSON NOT NULL DEFAULT '[]'")
            )

    t = "ai_provider_configs"
    if t in _tables(sync_conn):
        c = cols(t)
        if "selected_model_vision" not in c:
            sync_conn.execute(text("ALTER TABLE ai_provider_configs ADD COLUMN selected_model_vision VARCHAR(256)"))
        if "selected_model_solve" not in c:
            sync_conn.execute(text("ALTER TABLE ai_provider_configs ADD COLUMN selected_model_solve VARCHAR(256)"))
        if "vision_preset_id" not in c:
            sync_conn.execute(text("ALTER TABLE ai_provider_configs ADD COLUMN vision_preset_id VARCHAR(64)"))
        if "vision_base_url" not in c:
            sync_conn.execute(text("ALTER TABLE ai_provider_configs ADD COLUMN vision_base_url VARCHAR(512)"))
        if "vision_api_key_cipher" not in c:
            sync_conn.execute(text("ALTER TABLE ai_provider_configs ADD COLUMN vision_api_key_cipher BLOB"))
        if "solve_preset_id" not in c:
            sync_conn.execute(text("ALTER TABLE ai_provider_configs ADD COLUMN solve_preset_id VARCHAR(64)"))
        if "solve_base_url" not in c:
            sync_conn.execute(text("ALTER TABLE ai_provider_configs ADD COLUMN solve_base_url VARCHAR(512)"))
        if "solve_api_key_cipher" not in c:
            sync_conn.execute(text("ALTER TABLE ai_provider_configs ADD COLUMN solve_api_key_cipher BLOB"))
        if "user_id" not in c:
            sync_conn.execute(text("ALTER TABLE ai_provider_configs ADD COLUMN user_id VARCHAR(36)"))
            admin_row = sync_conn.execute(
                text("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
            ).fetchone()
            if admin_row:
                sync_conn.execute(
                    text("UPDATE ai_provider_configs SET user_id = :uid WHERE user_id IS NULL"),
                    {"uid": admin_row[0]},
                )

    t = "users"
    if t in _tables(sync_conn):
        uc = cols(t)
        if "full_name" not in uc:
            sync_conn.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR(64)"))
        if "education_stage" not in uc:
            sync_conn.execute(text("ALTER TABLE users ADD COLUMN education_stage VARCHAR(32)"))
        if "enrollment_year" not in uc:
            sync_conn.execute(text("ALTER TABLE users ADD COLUMN enrollment_year INTEGER"))


def _tables(sync_conn) -> set[str]:
    rows = sync_conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
    return {r[0] for r in rows}
