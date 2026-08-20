"""End-to-end smoke test against a *running* backend (real HTTP + real Socket.IO).

Unlike the pytest suite (which drives the ASGI app in-process via httpx's ASGITransport and an
in-memory SQLite), this script talks to a live server over the network: real uvicorn, real
on-disk SQLite, real JWT, real Socket.IO frames — the same surface the React frontend hits.

Two modes:

* **Self-contained (default):** seeds a throwaway SQLite DB, boots
  ``uvicorn mparlament.main:create_asgi_app`` on a spare port, runs every check, then tears the
  server + temp DB down. Nothing touches your dev ``mparlament.db`` or port 4000.

      python scripts/smoke_test.py

* **Against an already-running server:** point it at a URL and it skips boot/seed/teardown.
  Assumes the DB is seeded (``python scripts/seed.py``).

      python scripts/smoke_test.py --url http://localhost:4000

Flags: ``--port`` (self-boot port, default 4010), ``--no-realtime`` (REST only), ``--keep-db``.
Exit code = number of failed checks (0 = all green), so it is usable in CI.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import importlib.util
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

# The Windows console defaults to a legacy codepage (cp1250) that can't encode the Polish error
# strings echoed on failure; force UTF-8 so the report never crashes mid-run.
for _stream in (sys.stdout, sys.stderr):
    with contextlib.suppress(Exception):
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# Seeded dev credentials (scripts/seed.py → auth_identity seed).
ADMIN = {"username": "TEST123", "password": "test123"}
MEMBER = {"username": "MEMBER1", "password": "member1"}


# --- tiny result tracker ---------------------------------------------------


class Report:
    """Counts pass/fail/skip and prints a line per check."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def ok(self, name: str, detail: str = "") -> None:
        self.passed += 1
        print(f"  [PASS] {name}" + (f"  ({detail})" if detail else ""))

    def fail(self, name: str, detail: str) -> None:
        self.failed += 1
        print(f"  [FAIL] {name}  -> {detail}")

    def skip(self, name: str, detail: str) -> None:
        self.skipped += 1
        print(f"  [SKIP] {name}  ({detail})")


async def check(report: Report, name: str, fn):
    """Run an async check ``fn``; record pass on return, fail on any exception.

    ``fn`` may return a value (e.g. a token) for later steps; on failure ``None`` is returned so
    dependent steps degrade instead of crashing the whole run.
    """
    try:
        result = await fn()
    except Exception as exc:  # noqa: BLE001 - a smoke test reports, never propagates
        report.fail(name, f"{type(exc).__name__}: {exc}")
        return None
    else:
        report.ok(name)
        return result


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# --- REST checks -----------------------------------------------------------


async def login(http: httpx.AsyncClient, creds: dict) -> str:
    resp = await http.post("/api/auth/login", json=creds)
    expect(resp.status_code == 200, f"login {creds['username']} -> HTTP {resp.status_code}")
    body = resp.json()
    expect("token" in body and "user" in body, "login response missing token/user")
    return body["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def rest_checks(report: Report, http: httpx.AsyncClient) -> dict:
    """Exercise the REST surface. Returns state (tokens, created voting id) for realtime checks."""
    state: dict = {}

    print("\nREST — auth & identity")

    async def _health():
        resp = await http.get("/api/health")
        expect(resp.status_code == 200 and resp.json() == {"status": "ok"}, str(resp.text))

    await check(report, "GET /api/health", _health)

    admin_token = await check(report, "POST /api/auth/login (admin)", lambda: login(http, ADMIN))
    member_token = await check(
        report, "POST /api/auth/login (member)", lambda: login(http, MEMBER)
    )
    state["admin"] = admin_token
    state["member"] = member_token
    if not admin_token or not member_token:
        return state  # nothing else will work without identities

    async def _me():
        resp = await http.get("/api/auth/me", headers=_auth(admin_token))
        expect(resp.status_code == 200, f"HTTP {resp.status_code}")
        body = resp.json()
        expect(body.get("role") == "admin", f"role != admin: {body.get('role')}")
        expect("password" not in body, "password leaked in /me")

    await check(report, "GET /api/auth/me", _me)

    async def _current_user():
        # Personalizes to the caller (C2 identity chain); with a token it returns {user}.
        resp = await http.get("/api/current-user", headers=_auth(admin_token))
        expect(resp.status_code == 200, f"HTTP {resp.status_code}")
        expect("user" in resp.json(), "response not wrapped in {user}")

    await check(report, "GET /api/current-user (wrapped in {user})", _current_user)

    print("\nREST — read surface")

    async def _bare_array(path: str, token: str | None = None):
        headers = _auth(token) if token else {}
        resp = await http.get(path, headers=headers)
        expect(resp.status_code == 200, f"HTTP {resp.status_code}")
        expect(isinstance(resp.json(), list), "expected a bare array")

    await check(report, "GET /api/sessions (array)", lambda: _bare_array("/api/sessions"))
    await check(
        report, "GET /api/votings (array)", lambda: _bare_array("/api/votings", admin_token)
    )
    await check(
        report, "GET /api/amendments (array)", lambda: _bare_array("/api/amendments", admin_token)
    )
    await check(report, "GET /api/clubs (array)", lambda: _bare_array("/api/clubs", admin_token))
    await check(report, "GET /api/groups (array)", lambda: _bare_array("/api/groups", admin_token))
    await check(
        report, "GET /api/members (array)", lambda: _bare_array("/api/members", admin_token)
    )

    async def _users_no_password():
        resp = await http.get("/api/users", headers=_auth(admin_token))
        expect(resp.status_code == 200, f"HTTP {resp.status_code}")
        users = resp.json()
        expect(isinstance(users, list) and users, "expected non-empty array")
        expect(all("password" not in u for u in users), "password leaked in /users")

    await check(report, "GET /api/users (no password)", _users_no_password)

    async def _resolutions_wrapped():
        resp = await http.get("/api/resolutions")
        expect(resp.status_code == 200, f"HTTP {resp.status_code}")
        expect("resolutions" in resp.json(), "missing 'resolutions' key")

    await check(report, "GET /api/resolutions ({resolutions})", _resolutions_wrapped)

    async def _parliamentarians_partitioned():
        resp = await http.get("/api/parliamentarians", headers=_auth(admin_token))
        expect(resp.status_code == 200, f"HTTP {resp.status_code}")
        body = resp.json()
        expect(
            "parliamentarians" in body and "unaffiliated" in body,
            "missing partitioned keys",
        )

    await check(report, "GET /api/parliamentarians (partitioned)", _parliamentarians_partitioned)

    print("\nREST — voting lifecycle (create → detail → vote → tally)")

    async def _create_voting():
        resp = await http.post(
            "/api/votings",
            headers=_auth(admin_token),
            json={
                "title": "Smoke-test voting",
                "category": "law",
                "recipientsType": "all",
                "startTime": "2026-09-19T15:00",
            },
        )
        expect(resp.status_code in (200, 201), f"HTTP {resp.status_code}: {resp.text}")
        vid = resp.json().get("id")
        expect(isinstance(vid, int), f"created voting has no int id: {resp.json()}")
        return vid

    voting_id = await check(report, "POST /api/votings (admin creates)", _create_voting)
    state["voting_id"] = voting_id
    if not voting_id:
        return state

    async def _detail_lists():
        resp = await http.get(f"/api/votings/{voting_id}", headers=_auth(admin_token))
        expect(resp.status_code == 200, f"HTTP {resp.status_code}")
        body = resp.json()
        for key in ("eligibleUsers", "votedUsers", "notVotedUsers", "votesFor", "votedCount"):
            expect(key in body, f"detail missing {key}")
        expect(body["totalEligible"] == len(body["eligibleUsers"]), "totalEligible mismatch")

    await check(report, "GET /api/votings/:id (computed lists)", _detail_lists)

    async def _cast_and_tally():
        before = (
            await http.get(f"/api/votings/{voting_id}", headers=_auth(member_token))
        ).json()
        resp = await http.post(
            f"/api/votings/{voting_id}/vote",
            headers=_auth(member_token),
            json={"vote": "for"},
        )
        expect(resp.status_code == 200, f"vote HTTP {resp.status_code}: {resp.text}")
        expect(resp.json().get("vote") == "for", "vote not echoed")
        after = (
            await http.get(f"/api/votings/{voting_id}", headers=_auth(member_token))
        ).json()
        expect(after["votesFor"] == before["votesFor"] + 1, "votesFor did not increment")
        expect(after["hasVoted"] is True, "hasVoted not set for voter")
        expect(after["myVote"] == "for", "myVote not set")

    await check(report, "POST /api/votings/:id/vote (member) + tally", _cast_and_tally)

    async def _double_vote_conflict():
        resp = await http.post(
            f"/api/votings/{voting_id}/vote",
            headers=_auth(member_token),
            json={"vote": "against"},
        )
        expect(resp.status_code == 400, f"expected 400, got {resp.status_code}")
        expect(resp.json().get("message") == "Użytkownik już oddał głos", "wrong message")

    await check(report, "POST vote twice -> 400 conflict", _double_vote_conflict)

    async def _member_cannot_create():
        resp = await http.post(
            "/api/votings",
            headers=_auth(member_token),
            json={"title": "nope", "recipientsType": "all"},
        )
        expect(resp.status_code == 403, f"expected 403, got {resp.status_code}")

    await check(report, "POST /api/votings (member) -> 403", _member_cannot_create)

    return state


# --- realtime checks (Socket.IO) -------------------------------------------


async def realtime_checks(report: Report, base_url: str, state: dict) -> None:
    print("\nRealtime — Socket.IO events")

    if importlib.util.find_spec("aiohttp") is None:
        report.skip(
            "Socket.IO client",
            "aiohttp not installed — run: pip install aiohttp (dev dep)",
        )
        return

    import socketio  # noqa: PLC0415 - imported lazily so REST-only runs need no aiohttp

    admin_token = state.get("admin")
    voting_id = state.get("voting_id")
    if not admin_token or not voting_id:
        report.skip("Socket.IO events", "REST prerequisites failed; skipping realtime")
        return

    sio = socketio.AsyncClient(logger=False, engineio_logger=False)
    events: dict[str, asyncio.Event] = {
        "vote": asyncio.Event(),
        "zo": asyncio.Event(),
        "schedule": asyncio.Event(),
        "speaker": asyncio.Event(),
    }
    payloads: dict[str, object] = {}

    def _handler(key: str):
        async def _on(data):
            payloads[key] = data
            events[key].set()

        return _on

    sio.on(f"voteUpdate:{voting_id}", _handler("vote"))
    sio.on("zoContentUpdated", _handler("zo"))
    sio.on("scheduleUpdated", _handler("schedule"))
    sio.on("speakerUpdated", _handler("speaker"))

    async def _connect():
        # Match the FE transport (websocket-only). Same socketio_path default (/socket.io).
        await sio.connect(base_url, transports=["websocket"], wait_timeout=10)
        expect(sio.connected, "client did not reach connected state")
        return True  # distinguish success from the None a no-return check yields

    connected = await check(report, "connect to Socket.IO", _connect)
    if not connected:
        with contextlib.suppress(Exception):
            await sio.disconnect()
        return

    http = httpx.AsyncClient(base_url=base_url, timeout=10)
    try:
        # voteUpdate:<id> — a fresh vote must push a live tally to subscribers.
        async def _vote_update():
            # MEMBER1 already voted in the REST phase; admin is eligible ("all") and hasn't voted.
            resp = await http.post(
                f"/api/votings/{voting_id}/vote",
                headers=_auth(admin_token),
                json={"vote": "against"},
            )
            expect(resp.status_code == 200, f"vote HTTP {resp.status_code}: {resp.text}")
            await asyncio.wait_for(events["vote"].wait(), timeout=5)
            data = payloads["vote"]
            for key in ("votedCount", "votesFor", "votesAgainst", "abstained"):
                expect(key in data, f"voteUpdate payload missing {key}")
            expect(data["votesAgainst"] >= 1, "votesAgainst not reflected")

        await check(report, "voteUpdate:<id> on cast vote", _vote_update)

        # zoContentUpdated round-trip C->S->all (+ persistence).
        async def _zo_round_trip():
            text = f"Realtime ZO {int(time.time())}"
            await sio.emit("zoContentUpdated", text)
            await asyncio.wait_for(events["zo"].wait(), timeout=5)
            expect(payloads["zo"] == text, f"rebroadcast payload mismatch: {payloads['zo']!r}")
            # And it persisted for the REST polling fallback.
            resp = await http.get("/api/session/current", headers=_auth(admin_token))
            expect(resp.status_code == 200, f"session HTTP {resp.status_code}")
            expect(resp.json().get("zoContent") == text, "zoContent not persisted")

        await check(report, "zoContentUpdated round-trip + persist", _zo_round_trip)

        # scheduleUpdated on session PUT.
        async def _schedule_update():
            schedule = [{"time": "10:00", "title": "Otwarcie", "status": "active"}]
            resp = await http.put(
                "/api/session/current",
                headers=_auth(admin_token),
                json={"schedule": schedule},
            )
            expect(resp.status_code == 200, f"PUT HTTP {resp.status_code}: {resp.text}")
            await asyncio.wait_for(events["schedule"].wait(), timeout=5)
            expect(payloads["schedule"] == schedule, "scheduleUpdated payload mismatch")

        await check(report, "scheduleUpdated on PUT /session/current", _schedule_update)

        # speakerUpdated on session PUT.
        async def _speaker_update():
            speaker = {"name": "Jan Kowalski", "club": "KO", "role": "poseł", "time": "10:05"}
            resp = await http.put(
                "/api/session/current",
                headers=_auth(admin_token),
                json={"currentSpeaker": speaker},
            )
            expect(resp.status_code == 200, f"PUT HTTP {resp.status_code}: {resp.text}")
            await asyncio.wait_for(events["speaker"].wait(), timeout=5)
            expect(payloads["speaker"] == speaker, "speakerUpdated payload mismatch")

        await check(report, "speakerUpdated on PUT /session/current", _speaker_update)
    finally:
        await http.aclose()
        with contextlib.suppress(Exception):
            await sio.disconnect()


# --- server boot / teardown ------------------------------------------------


def _free_port() -> int:
    """Ask the OS for an unused localhost port (avoids collisions with a stale/dev server)."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _sqlite_url(db_path: Path) -> str:
    return "sqlite+aiosqlite:///" + str(db_path).replace("\\", "/")


def _child_env(db_url: str) -> dict:
    env = os.environ.copy()
    env["MPARLAMENT_DATABASE_URL"] = db_url
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + existing if existing else "")
    return env


async def _wait_healthy(base_url: str, proc: subprocess.Popen, timeout: float = 25.0) -> None:
    deadline = time.time() + timeout
    async with httpx.AsyncClient(base_url=base_url, timeout=2) as http:
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"server exited early (code {proc.returncode})")
            try:
                resp = await http.get("/api/health")
                if resp.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.4)
    raise RuntimeError(f"server did not become healthy within {timeout}s")


@contextlib.asynccontextmanager
async def booted_server(port: int, keep_db: bool):
    """Seed a throwaway DB, boot the combined ASGI app, yield its base URL, then clean up."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="mparlament-smoke-"))
    db_path = tmp_dir / "smoke.db"
    db_url = _sqlite_url(db_path)
    env = _child_env(db_url)
    base_url = f"http://127.0.0.1:{port}"

    print(f"Seeding throwaway DB: {db_path}")
    seed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "seed.py")],
        env=env,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if seed.returncode != 0:
        raise RuntimeError(f"seed failed:\n{seed.stdout}\n{seed.stderr}")

    print(f"Booting server on {base_url} (uvicorn create_asgi_app --factory) ...")
    log = open(tmp_dir / "server.log", "w", encoding="utf-8")  # noqa: SIM115
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "mparlament.main:create_asgi_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        env=env,
        cwd=str(ROOT),
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        await _wait_healthy(base_url, proc)
        print("Server is healthy.\n")
        yield base_url
    finally:
        proc.terminate()
        with contextlib.suppress(Exception):
            proc.wait(timeout=10)
        log.close()
        if keep_db:
            print(f"\nKept DB + log at: {tmp_dir}")
        else:
            # SQLite may briefly hold the file on Windows; retry a few times.
            for _ in range(10):
                try:
                    for f in tmp_dir.iterdir():
                        f.unlink()
                    tmp_dir.rmdir()
                    break
                except OSError:
                    time.sleep(0.3)


# --- entrypoint ------------------------------------------------------------


async def run(base_url: str, do_realtime: bool) -> int:
    report = Report()
    print(f"Target: {base_url}")
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as http:
        state = await rest_checks(report, http)
    if do_realtime:
        await realtime_checks(report, base_url, state)

    print("\n" + "=" * 60)
    print(f"  PASSED: {report.passed}   FAILED: {report.failed}   SKIPPED: {report.skipped}")
    print("=" * 60)
    return report.failed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=None,
        help="Test an already-running server (skips boot/seed). E.g. http://localhost:4000",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for the self-booted server (default: an OS-assigned free port)",
    )
    parser.add_argument("--no-realtime", action="store_true", help="Skip Socket.IO checks")
    parser.add_argument(
        "--keep-db", action="store_true", help="Keep the throwaway DB + server log (self-boot)"
    )
    args = parser.parse_args()
    do_realtime = not args.no_realtime

    if args.url:
        base = args.url.rstrip("/")
        parsed = urlparse(base)
        if not parsed.scheme or not parsed.netloc:
            parser.error(f"--url must be a full URL, got {args.url!r}")
        failures = asyncio.run(run(base, do_realtime))
    else:

        port = args.port or _free_port()

        async def _self_boot() -> int:
            async with booted_server(port, args.keep_db) as base:
                return await run(base, do_realtime)

        failures = asyncio.run(_self_boot())

    sys.exit(failures)


if __name__ == "__main__":
    main()
