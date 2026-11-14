"""Sets up a fresh throwaway Home Assistant for trying the card. Run it once, inside WSL:

    /root/mr/.venv/bin/python tests/try/set_up.py

Afterwards there are two accounts, a made-up phone, one routine, and two dashboards with the card:
http://localhost:8123/try-card and http://localhost:8123/try-card-alone.

The password is fixed and public, because the instance holds nothing real. Home Assistant listens
on every address inside WSL. With WSL's usual networking only this computer can reach it. Don't
run it where WSL shares the computer's network address, and stop it when you're done.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import aiohttp

URL = "http://localhost:8123"
CLIENT_ID = f"{URL}/"
PASSWORD = "try-out-only"
ADMIN = "tester"
MEMBER = "member"
GOOGLE_CLOCK = "com.google.android.deskclock"


class Server:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.session = session
        self.headers: dict[str, str] = {}
        self.ws: aiohttp.ClientWebSocketResponse | None = None
        self.next_id = 0

    async def post(self, path: str, **kwargs) -> dict:
        async with self.session.post(f"{URL}{path}", headers=self.headers, **kwargs) as response:
            if response.status >= 400:
                raise RuntimeError(f"{path} answered {response.status}: {await response.text()}")
            if response.content_type != "application/json":
                return {}
            return await response.json()

    async def wait_until_started(self) -> None:
        """The phone app's address answers 404 until Home Assistant has finished starting."""
        for _ in range(90):
            async with self.session.get(f"{URL}/api/mobile_app/registrations") as response:
                if response.status != 404:
                    return
            await asyncio.sleep(2)
        raise RuntimeError("Home Assistant didn't finish starting. Look at its log.")

    async def onboard(self) -> None:
        await self.wait_until_started()
        answer = await self.post(
            "/api/onboarding/users",
            json={"client_id": CLIENT_ID, "name": "Tester", "username": ADMIN, "password": PASSWORD, "language": "en"},
        )
        tokens = await self.post(
            "/auth/token",
            data={"grant_type": "authorization_code", "code": answer["auth_code"], "client_id": CLIENT_ID},
        )
        self.headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        await self.post("/api/onboarding/core_config", json={})
        await self.post("/api/onboarding/analytics", json={})
        await self.post("/api/onboarding/integration", json={"client_id": CLIENT_ID, "redirect_uri": CLIENT_ID})
        self.ws = await self.session.ws_connect(f"{URL}/api/websocket")
        await self.ws.receive_json()
        await self.ws.send_json({"type": "auth", "access_token": tokens["access_token"]})
        await self.ws.receive_json()

    async def ask(self, **message):
        self.next_id += 1
        await self.ws.send_json({"id": self.next_id, **message})
        while True:
            reply = await self.ws.receive_json()
            if reply.get("id") == self.next_id and reply.get("type") == "result":
                if not reply["success"]:
                    raise RuntimeError(f"{message['type']} was refused: {reply['error']}")
                return reply["result"]


async def add_member(server: Server) -> None:
    user = (await server.ask(type="config/auth/create", name="Member", group_ids=["system-users"]))["user"]
    await server.ask(
        type="config/auth_provider/homeassistant/create", user_id=user["id"], username=MEMBER, password=PASSWORD
    )


async def add_phone(server: Server) -> None:
    """A made-up phone, registered the way the Android app registers itself."""
    phone = await server.post(
        "/api/mobile_app/registrations",
        json={
            "app_id": "io.homeassistant.companion.android",
            "app_name": "Home Assistant",
            "app_version": "2026.10.0",
            "device_id": "test-phone",
            "device_name": "Test Phone",
            "manufacturer": "Acme",
            "model": "Test 1",
            "os_name": "Android",
            "os_version": "16",
            "supports_encryption": False,
        },
    )
    webhook = f"/api/webhook/{phone['webhook_id']}"
    alarm = (datetime.now(timezone.utc) + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
    await server.post(
        webhook,
        json={
            "type": "register_sensor",
            "data": {
                "type": "sensor",
                "unique_id": "next_alarm",
                "name": "Next alarm",
                "device_class": "timestamp",
                "state": alarm.isoformat(),
                "attributes": {"Package": GOOGLE_CLOCK},
            },
        },
    )
    await server.post(webhook, json={"type": "update_location", "data": {"location_name": "home"}})


async def add_routine(server: Server) -> str:
    label = await server.ask(type="config/label_registry/create", name="morning routine")
    for script in ("script.good_morning", "script.open_the_blinds"):
        await server.ask(type="config/entity_registry/update", entity_id=script, labels=[label["label_id"]])
    flow = await server.post("/api/config/config_entries/flow", json={"handler": "morning_routine"})
    phones = flow["data_schema"][0]["selector"]["select"]["options"]
    done = await server.post(
        f"/api/config/config_entries/flow/{flow['flow_id']}", json={"device_id": phones[0]["value"]}
    )
    entry_id = done["result"]["entry_id"]
    await server.ask(type="morning_routine/update", entry_id=entry_id, clock=GOOGLE_CLOCK)
    return entry_id


async def add_dashboards(server: Server, entry_id: str) -> None:
    """One dashboard with the card beside Home Assistant's own cards, and one with the card alone.

    The second shows what the card can rely on when nothing else on the page loads controls.
    """
    lights = sorted(state["entity_id"] for state in await server.ask(type="get_states") if state["entity_id"].startswith("light."))
    card = {"type": "custom:morning-routine-card", "routine": entry_id}
    dashboards = {
        "try-card": ("Try the card", [card, {"type": "entities", "title": "Made-up lights", "entities": lights[:3]}]),
        "try-card-alone": ("The card alone", [card]),
    }
    for url_path, (title, cards) in dashboards.items():
        await server.ask(
            type="lovelace/dashboards/create",
            url_path=url_path,
            title=title,
            mode="storage",
            require_admin=False,
            show_in_sidebar=True,
        )
        await server.ask(
            type="lovelace/config/save", url_path=url_path, config={"views": [{"title": title, "cards": cards}]}
        )


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        server = Server(session)
        await server.onboard()
        await add_member(server)
        await add_phone(server)
        entry_id = await add_routine(server)
        await add_dashboards(server, entry_id)
        await server.ws.close()
    print(f"Ready. Open {URL}/try-card and log in as {ADMIN} or {MEMBER}, password {PASSWORD}.")


asyncio.run(main())
