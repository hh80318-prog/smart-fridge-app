#!/usr/bin/env python3
"""
智慧冰箱 App - 主程式
執行方式：python app.py
需要：pip install flask
可選：pip install pywebview  (提供原生視窗，否則用瀏覽器)
"""

import sys
import os
import json
import threading
import webbrowser
import time
import sqlite3
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

# ── 路徑設定 ─────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH  = BASE_DIR / "fridge_data.db"
PORT     = int(os.environ.get("PORT", 7788))

app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")

# ── 資料庫初始化 ─────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            qty TEXT,
            expiry TEXT,
            category TEXT,
            added_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS saved_recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            data TEXT,
            used_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    # 記錄首次啟動時間
    c.execute("INSERT OR IGNORE INTO app_meta (key, value) VALUES ('created_at', ?)",
              (str(int(time.time() * 1000)),))
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ── API 路由 ─────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(BASE_DIR), "index.html")

# 庫存 CRUD
@app.route("/api/inventory", methods=["GET"])
def get_inventory():
    conn = get_db()
    rows = conn.execute("SELECT * FROM inventory ORDER BY expiry ASC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/inventory", methods=["POST"])
def add_inventory():
    items = request.json  # array of items
    if not isinstance(items, list):
        items = [items]
    conn = get_db()
    for item in items:
        conn.execute(
            "INSERT OR REPLACE INTO inventory (id, name, qty, expiry, category, added_at) VALUES (?, ?, ?, ?, ?, ?)",
            (str(item.get("id")), item.get("name"), item.get("qty",""),
             item.get("expiry"), item.get("category","其他"), item.get("addedAt",""))
        )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/inventory/<item_id>", methods=["DELETE"])
def delete_inventory(item_id):
    conn = get_db()
    conn.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/inventory/bulk-delete", methods=["POST"])
def bulk_delete_inventory():
    ids = request.json.get("ids", [])
    conn = get_db()
    conn.executemany("DELETE FROM inventory WHERE id = ?", [(i,) for i in ids])
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# 已儲存食譜
@app.route("/api/saved-recipes", methods=["GET"])
def get_saved_recipes():
    conn = get_db()
    rows = conn.execute("SELECT * FROM saved_recipes ORDER BY id DESC").fetchall()
    conn.close()
    result = []
    for r in rows:
        try:
            d = json.loads(r["data"])
            d["_db_id"] = r["id"]
            d["used_at"] = r["used_at"]
            result.append(d)
        except:
            pass
    return jsonify(result)

@app.route("/api/saved-recipes", methods=["POST"])
def save_recipe():
    recipe = request.json
    used_at = recipe.pop("usedAt", "")
    conn = get_db()
    conn.execute(
        "INSERT INTO saved_recipes (name, data, used_at) VALUES (?, ?, ?)",
        (recipe.get("name",""), json.dumps(recipe, ensure_ascii=False), used_at)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# App meta (created_at for days active)
@app.route("/api/meta", methods=["GET"])
def get_meta():
    conn = get_db()
    rows = conn.execute("SELECT * FROM app_meta").fetchall()
    conn.close()
    return jsonify({r["key"]: r["value"] for r in rows})

# ── 啟動邏輯 ─────────────────────────────────────────────────────────
def open_browser():
    """延遲一秒後開啟瀏覽器"""
    time.sleep(1.2)
    webbrowser.open(f"http://localhost:{PORT}")

def try_pywebview():
    """嘗試用 pywebview 開啟原生視窗"""
    try:
        import webview
        window = webview.create_window(
            title="🧊 智慧冰箱",
            url=f"http://localhost:{PORT}",
            width=480,
            height=860,
            resizable=True,
            min_size=(360, 600),
        )
        # 先啟動 Flask（非阻塞）
        flask_thread = threading.Thread(
            target=lambda: app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False),
            daemon=True
        )
        flask_thread.start()
        time.sleep(0.8)
        webview.start(debug=False)
        return True
    except ImportError:
        return False

def get_local_ip():
    """取得本機區域網路 IP"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def run_with_browser():
    """Fallback：用瀏覽器開啟"""
    local_ip = get_local_ip()
    print("=" * 50)
    print("  🧊 智慧冰箱 App 已啟動！")
    print()
    print(f"  💻 本機：    http://localhost:{PORT}")
    print(f"  📱 手機/平板：http://{local_ip}:{PORT}")
    print()
    print("  手機與電腦需在同一個 WiFi 下")
    print("  按 Ctrl+C 關閉 App")
    print("=" * 50)
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

if __name__ == "__main__":
    init_db()
    print(f"\n🧊 智慧冰箱 App 啟動中... port={PORT}\n")
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
