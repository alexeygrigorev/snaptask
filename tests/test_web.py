import functools
import http.server
import threading
from pathlib import Path
import pytest
from urllib.parse import urlparse

pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright
import json, base64

photo = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aY1sAAAAASUVORK5CYII="
)
state = {
    "tasks": {},
    "creates": 0,
    "reserves": {},
    "fail": True,
    "tokens": [],
    "hooks": [],
}


def mock(route):
    r = route.request
    path = urlparse(r.url).path
    body = json.loads(r.post_data or "{}") if not path.startswith("/put/") else {}

    def send(data, status=200):
        route.fulfill(
            status=status, content_type="application/json", body=json.dumps(data)
        )

    if path == "/api/me":
        return send({"id": "test-user", "name": "Alex"})
    if path == "/api/tokens":
        if r.method == "POST":
            state["tokens"].append({"id": "tok1", "name": body["name"]})
            return send({"token": "st_test_secret", **state["tokens"][-1]})
        return send({"tokens": state["tokens"]})
    if path == "/api/webhooks":
        if r.method == "POST":
            state["hooks"].append({"id": "hook1", "url": body["url"]})
            return send({"secret": "wh_test_secret", **state["hooks"][-1]})
        return send({"webhooks": state["hooks"]})
    if path == "/api/tasks":
        if r.method == "POST":
            key = r.headers["idempotency-key"]
            if key not in state["tasks"]:
                state["creates"] += 1
                state["tasks"][key] = {"id": "task1", "files": [], **body}
            return send(state["tasks"][key])
        return send({"tasks": list(state["tasks"].values())})
    if path == "/api/tasks/task1/uploads":
        key = r.headers["idempotency-key"]
        state["reserves"].setdefault(
            key, {"id": "file" + str(len(state["reserves"]) + 1), **body}
        )
        item = state["reserves"][key]
        return send(
            {
                "file_id": item["id"],
                "upload_url": r.url.split("/api/")[0] + "/put/" + item["id"],
                "completed": item.get("complete", False),
            }
        )
    if path.startswith("/put/"):
        if path.endswith("file2") and state["fail"]:
            state["fail"] = False
            return route.fulfill(status=503, body="retry")
        return route.fulfill(status=200, body="")
    if path.endswith("/complete"):
        fid = path.split("/")[-2]
        item = next(i for i in state["reserves"].values() if i["id"] == fid)
        if not item.get("complete"):
            item["complete"] = True
            next(iter(state["tasks"].values()))["files"].append(item)
        return send({"ok": True})
    if path == "/api/tasks/task1" and r.method == "PATCH":
        next(iter(state["tasks"].values()))["status"] = "todo"
        return send({"ok": True})
    if "/files/" in path:
        return send({"download_url": r.url.split("/api/")[0] + "/mockphoto"})
    if path == "/mockphoto":
        return route.fulfill(status=200, content_type="image/png", body=photo)
    return send({"error": "unknown " + path}, 404)


@pytest.fixture
def base_url():
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(
        QuietHandler, directory=str(Path(__file__).resolve().parents[1] / "web")
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:" + str(server.server_port) + "/"
    server.shutdown()
    server.server_close()


def test_capture_batch_persistence_and_retry(base_url, tmp_path):
    state.update(tasks={}, creates=0, reserves={}, fail=True, tokens=[], hooks=[])
    with sync_playwright() as p:
        if not Path(p.chromium.executable_path).exists():
            pytest.skip("Install Playwright Chromium to run web tests")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000}, service_workers="block"
        )
        page = context.new_page()
        page.route("**/api/**", mock)
        page.route("**/put/**", mock)
        page.route("**/mockphoto", mock)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base_url)
        page.wait_for_selector("#capture-workspace:not([hidden])")
        page.screenshot(path=str(tmp_path / "snaptask-desktop.png"), full_page=True)
        page.click("#start-capture")
        page.set_input_files(
            "#camera-input",
            {"name": "whiteboard.png", "mimeType": "image/png", "buffer": photo},
        )
        page.wait_for_selector(".batch-photo")
        page.click("#add-photo")
        page.set_input_files(
            "#camera-input",
            {"name": "notes.png", "mimeType": "image/png", "buffer": photo},
        )
        page.wait_for_function("document.querySelectorAll('.batch-photo').length === 2")
        assert state["creates"] == 0, "task created before Ready"
        page.fill("#batch-title", "Make a plan from these notes")
        page.fill("#batch-notes", "Combine both photos into one plan.")
        page.reload()
        page.wait_for_function("document.querySelectorAll('.batch-photo').length === 2")
        assert page.input_value("#batch-title") == "Make a plan from these notes"
        page.click("#ready-batch")
        page.wait_for_function(
            "document.querySelector('#ready-batch').textContent.includes('Retry') && !document.querySelector('#ready-batch').disabled"
        )
        assert state["creates"] == 1
        assert next(iter(state["tasks"].values()))["status"] == "uploading"
        page.reload()
        page.wait_for_function(
            "document.querySelector('#ready-batch').textContent.includes('Retry')"
        )
        page.click("#ready-batch")
        page.wait_for_selector(".task-card")
        assert state["creates"] == 1
        assert len(state["reserves"]) == 2
        assert len(next(iter(state["tasks"].values()))["files"]) == 2
        assert next(iter(state["tasks"].values()))["status"] == "todo"
        assert page.is_hidden("#batch")
        assert not page.is_disabled("#start-capture")
        page.screenshot(path=str(tmp_path / "snaptask-complete.png"), full_page=True)
        page.click("#connections-toggle")
        page.fill("#token-name", "test agent")
        page.click("#token-form button")
        page.wait_for_selector("#token-secret:not([hidden])")
        assert "st_test_secret" in page.inner_text("#token-secret")
        page.fill("#webhook-url", "https://example.com/hooks")
        page.click("#webhook-form button")
        page.wait_for_selector("#webhook-secret:not([hidden])")
        assert "wh_test_secret" in page.inner_text("#webhook-secret")
        page.screenshot(path=str(tmp_path / "snaptask-connections.png"), full_page=True)
        assert not errors, errors
        mobile = browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True,
            service_workers="block",
        )
        mp = mobile.new_page()
        mp.route("**/api/**", mock)
        mp.route("**/mockphoto", mock)
        mp.goto(base_url)
        mp.wait_for_selector("#capture-workspace:not([hidden])")
        mp.click("#start-capture")
        mp.set_input_files(
            "#camera-input",
            {"name": "phone-photo.png", "mimeType": "image/png", "buffer": photo},
        )
        mp.wait_for_selector(".batch-photo")
        mp.screenshot(path=str(tmp_path / "snaptask-mobile.png"), full_page=True)
        assert mp.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        ), "mobile horizontal overflow"
        print(
            "PASS: no premature tasks, two-photo grouping, persistent drafts after reload, failed upload retry without duplicate task/files, token/webhook creation, mobile layout, no browser errors"
        )
        browser.close()
