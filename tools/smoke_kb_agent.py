"""冒烟：知识库 API + Agent 会话/问答（不走真实豆包，验证链路与降级）。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app

init_db()
client = TestClient(app)

import random
suffix = f"{random.randint(1000, 9999)}"

# 登录拿 token（口令从环境变量 ADMIN_PASSWORD 读取，仓库不留明文）
import os
_admin_pwd = os.environ.get("ADMIN_PASSWORD")
assert _admin_pwd, "请设置环境变量 ADMIN_PASSWORD（管理员登录口令）"
r = client.post("/api/auth/login", json={"username": "admin", "password": _admin_pwd})
assert r.status_code == 200, r.text
admin_token = r.json()["data"]["access_token"]
H = {"Authorization": f"Bearer {admin_token}"}

# 1) 建节点 + 单元
r = client.post("/api/knowledge/nodes", headers=H, json={
    "code": f"smoke-{suffix}", "name_zh": "冒烟戏台", "name_en": "Smoke Stage"})
print("node:", r.status_code, r.json()["data"]["id"])
node_id = r.json()["data"]["id"]
r = client.post("/api/knowledge/units", headers=H, json={
    "node_id": node_id, "title": "变脸起源",
    "content_zh": "变脸是川剧表演的特技，相传起源于古代人类面对猛兽以脸谱恐吓野兽的生存本能。",
    "keywords": "变脸,绝技"})
print("unit:", r.status_code, r.json()["data"]["id"], "has_vector:", r.json()["data"]["has_vector"])
unit_id = r.json()["data"]["id"]

# 2) 试查（无 Key 时降级 BM25-only）
r = client.get("/api/knowledge/search", headers=H, params={"q": "变脸是怎么来的"})
print("search:", r.status_code, [x["title"] for x in r.json()["data"]])

# 3) 译文 upsert
r = client.put(f"/api/knowledge/units/{unit_id}/translations", headers=H, json={
    "unit_id": unit_id, "lang": "en",
    "content": "Face-changing is a stunt of Sichuan opera.", "review_status": "checked"})
print("translation:", r.status_code)

# 4) 实体 + 关系
r = client.post("/api/knowledge/entities", headers=H, json={"name": f"白素贞{suffix}", "type": "person"})
print("entity:", r.status_code)
r = client.put(f"/api/knowledge/units/{unit_id}/entity-links", headers=H, json={"unit_id": unit_id, "entity_ids": [1]})
print("links:", r.status_code)

# 5) 验收问集 + 报告
r = client.post("/api/knowledge/eval-questions", headers=H, json={"question": "变脸起源于什么", "expect_unit_id": unit_id})
print("eval-q:", r.status_code)
r = client.get("/api/knowledge/eval-report", headers=H)
print("eval-report:", r.status_code, r.json()["data"]["hit_rate"])

# 6) Agent 会话 + 问答（未配 Key 应降级）
r = client.post("/api/agent/sessions", json={"lang": "zh-CN", "node_code": "smoke-stage"})
print("agent session:", r.status_code, r.json()["data"]["token"][:8])
tok = r.json()["data"]["token"]
r = client.post("/api/agent/chat", json={"token": tok, "text": "变脸是怎么来的？"})
print("agent chat:", r.status_code, "degraded:", r.json()["data"]["degraded"], "|", r.json()["data"]["text"][:30])
r = client.get("/api/agent/history", params={"token": tok})
print("agent history:", r.status_code, len(r.json()["data"]), "条")
