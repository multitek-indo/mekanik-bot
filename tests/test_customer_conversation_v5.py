import asyncio
import pytest

from app import ai, customer
from app.types import IncomingMessage


def _msg(text: str, phone: str = "6200000000000") -> IncomingMessage:
    return IncomingMessage(
        message_id="v5-test",
        phone=phone,
        sender_name="Test",
        text=text,
        location=None,
        image=None,
        video=None,
        document=None,
        media_type=None,
        media_path=None,
        raw_payload={},
    )


@pytest.mark.parametrize(
    "text,expected_machine,expected_problem",
    [
        ("Juki jarum 1 sering loncat kalau buat jahit", "Juki jarum 1", "sering loncat"),
        ("JUKI DDL-8700 error 03", "JUKI DDL-8700", "error 03"),
        ("obras Pegasus suaranya kasar", "obras Pegasus", "suaranya kasar"),
        ("mesin saya Brother ora gelem mlaku", "Brother", "ora gelem mlaku"),
        ("aku punyamesn Juki jarum 1 rusak sering loncat", "Juki jarum 1", "rusak sering loncat"),
        ("Siruba obras macet", "Siruba obras", "macet"),
        ("Typical GC6-7D bunyi kasar", "Typical GC6-7D", "bunyi kasar"),
        ("Jack A4 mati total", "Jack A4", "mati total"),
        ("Juki jahitane sering loncat", "Juki", "jahitane sering loncat"),
        ("Pegasus benange sering pedot", "Pegasus", "benange sering pedot"),
        ("Juki pedalnya gak respon", "Juki", "pedalnya gak respon"),
    ],
)
def test_local_semantic_machine_problem_split(text, expected_machine, expected_problem):
    got = customer._local_machine_problem_fallback(text, expected_machine=True)
    assert expected_machine.lower() in got["machine"].lower()
    assert expected_problem.lower() in got["problem"].lower()


@pytest.mark.parametrize(
    "text",
    [
        "Juki",
        "Pegasus obras",
        "Brother 7200",
        "Juki DDL-8700",
        "jarum 1 Juki",
        "Typical GC6-7D",
    ],
)
def test_short_machine_answer_is_accepted(text):
    got = customer._local_machine_problem_fallback(text, expected_machine=True)
    assert got["machine"]
    assert not got["problem"]


@pytest.mark.parametrize(
    "text",
    [
        "mekaniknya bisa datang sore?",
        "sampean rumahnya mana?",
        "berapa biayanya?",
        "ada garansi tidak?",
        "pembayarannya gimana?",
    ],
)
def test_side_questions_are_not_misread_as_machine(text):
    got = customer._local_machine_problem_fallback(text, expected_machine=True)
    assert got["machine"] == ""


def test_machine_answer_uses_pending_problem():
    got = customer._local_machine_problem_fallback(
        "Juki",
        expected_machine=True,
        pending_problem="sering loncat saat menjahit",
    )
    assert got == {
        "machine": "Juki",
        "problem": "sering loncat saat menjahit",
    }


def test_start_intake_recovers_typo_machine_and_problem(monkeypatch):
    saved = {}

    async def fake_customer(phone, name=None):
        return {"id": "cust-1", "name": "Budi"}

    async def fake_set_state(phone, state, payload):
        saved["state"] = state
        saved["payload"] = dict(payload)

    monkeypatch.setattr(customer, "get_or_create_customer", fake_customer)
    monkeypatch.setattr(customer, "set_state", fake_set_state)

    reply = asyncio.run(
        customer._start_intake(
            _msg("Aku punyamesn Juki jarum 1 rusak sering loncat"),
            {
                "intent": "SERVICE_REQUEST",
                "machine_count": None,
                "machines": [],
            },
        )
    )

    assert saved["state"] == "cust_machine_count"
    prefill = saved["payload"]["prefill_machines"][0]
    assert "juki jarum 1" in prefill["machine"].lower()
    assert "sering loncat" in prefill["problem"].lower()
    assert "satu unit" in reply.lower()


def test_count_after_complete_prefill_skips_duplicate_machine_questions(monkeypatch):
    payload = {
        "customer_id": "cust-1",
        "items": [],
        "prefill_machines": [
            {"machine": "Juki jarum 1", "problem": "sering loncat"}
        ],
    }
    saved = {}

    async def fake_get_state(phone):
        return {"state": "cust_machine_count", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return {
            "intent": "SERVICE_REQUEST",
            "control": "NONE",
            "machine_count": 1,
            "machines": [],
            "fields": {"name": None, "machine_description": None, "problem": None, "landmark": None},
            "questions": [],
            "corrections": [],
            "speech_acts": ["ANSWER"],
            "service_requested": True,
            "answers_current_slot": True,
            "normalized_text": "satu",
            "language_style": "INDONESIA_CASUAL",
            "confidence": 1.0,
            "provider": "local",
        }

    async def fake_set_state(phone, state, new_payload):
        saved["state"] = state
        saved["payload"] = dict(new_payload)

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "quick_customer_signals", lambda text, state="": {"control": "NONE", "machine_count": 1})
    monkeypatch.setattr(customer, "set_state", fake_set_state)

    reply = asyncio.run(customer.handle_customer_state(_msg("Satu mas")))
    assert saved["state"] == "cust_location"
    assert saved["payload"]["items"] == [
        {"machine": "Juki jarum 1", "problem": "sering loncat"}
    ]
    assert "share location" in reply.lower()
    assert "jenis/merk/model" not in reply.lower()


def test_full_machine_problem_reply_in_machine_desc_moves_forward(monkeypatch):
    payload = {
        "customer_id": "cust-1",
        "machine_count": 1,
        "machine_index": 1,
        "items": [],
    }
    saved = {}

    async def fake_get_state(phone):
        return {"state": "cust_machine_desc", "payload": payload}

    async def fake_understand(text, state="", context=None):
        # Simulate the exact failure mode seen in production: AI understands
        # only the problem and misses the machine.
        return {
            "intent": "SERVICE_REQUEST",
            "control": "NONE",
            "machine_count": None,
            "machines": [{"machine": "", "problem": "sering loncat kalau buat jahit"}],
            "fields": {"name": None, "machine_description": None, "problem": "sering loncat kalau buat jahit", "landmark": None},
            "questions": [],
            "corrections": [],
            "speech_acts": ["INFORMATION"],
            "service_requested": True,
            "answers_current_slot": False,
            "normalized_text": text,
            "language_style": "INDONESIA_CASUAL",
            "confidence": 0.9,
            "provider": "local",
        }

    async def fake_set_state(phone, state, new_payload):
        saved["state"] = state
        saved["payload"] = dict(new_payload)

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "set_state", fake_set_state)

    reply = asyncio.run(
        customer.handle_customer_state(_msg("Juki jarum 1 sering loncat kalau buat jahit"))
    )
    assert saved["state"] == "cust_location"
    assert saved["payload"]["items"][0]["machine"].lower() == "juki jarum 1"
    assert "sering loncat" in saved["payload"]["items"][0]["problem"].lower()
    assert "share location" in reply.lower()


def test_short_machine_after_problem_is_not_rejected(monkeypatch):
    payload = {
        "customer_id": "cust-1",
        "machine_count": 1,
        "machine_index": 1,
        "items": [],
        "pending_problem": "sering loncat kalau buat jahit",
    }
    saved = {}

    async def fake_get_state(phone):
        return {"state": "cust_machine_desc", "payload": payload}

    async def fake_understand(text, state="", context=None):
        # Simulate an LLM miss on a one-word brand.
        return {
            "intent": "GENERAL_QUESTION",
            "control": "NONE",
            "machine_count": None,
            "machines": [],
            "fields": {"name": None, "machine_description": None, "problem": None, "landmark": None},
            "questions": [],
            "corrections": [],
            "speech_acts": ["INFORMATION"],
            "service_requested": False,
            "answers_current_slot": False,
            "normalized_text": text,
            "language_style": "INDONESIA_CASUAL",
            "confidence": 0.7,
            "provider": "local",
        }

    async def fake_set_state(phone, state, new_payload):
        saved["state"] = state
        saved["payload"] = dict(new_payload)

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "set_state", fake_set_state)

    reply = asyncio.run(customer.handle_customer_state(_msg("Juki")))
    assert saved["state"] == "cust_location"
    assert saved["payload"]["items"][0] == {
        "machine": "Juki",
        "problem": "sering loncat kalau buat jahit",
    }
    assert "share location" in reply.lower()


@pytest.mark.parametrize(
    "text",
    [
        "sering loncat mas",
        "pedale ra respon",
        "benange pedot",
        "ora gelem mlaku",
        "mati total",
        "error 03",
        "suarane kasar",
        "macet kalau dipakai",
    ],
)
def test_problem_fallback_accepts_short_indonesian_javanese(text):
    got = customer._local_machine_problem_fallback(text, expected_problem=True)
    assert got["problem"]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("satu mas", 1),
        ("mung siji", 1),
        ("kalih unit", 2),
        ("loro mesin", 2),
        ("3 unit", 3),
    ],
)
def test_quick_count_still_understands_indonesian_javanese(text, expected):
    got = ai.quick_customer_signals(text, "cust_machine_count")
    assert got["machine_count"] == expected


def test_targeted_slot_repair_recovers_machine_and_problem(monkeypatch):
    calls = []

    async def fake_chat(provider, messages, temperature, max_tokens):
        calls.append(provider)
        return '{"answers_current_slot":true,"machine_count":null,"machine_description":"Juki jarum 1","problem":"sering loncat kalau buat jahit","name":null,"landmark":null,"confidence":0.99}'

    monkeypatch.setattr(ai, "_chat", fake_chat)
    monkeypatch.setattr(ai, "_provider_order", lambda: ["fake"])

    base = {
        "intent": "SERVICE_REQUEST",
        "control": "NONE",
        "speech_acts": ["INFORMATION"],
        "service_requested": True,
        "answers_current_slot": False,
        "machine_count": None,
        "machines": [{"machine": "", "problem": "sering loncat kalau buat jahit"}],
        "fields": {"name": None, "machine_description": None, "problem": "sering loncat kalau buat jahit", "landmark": None},
        "questions": [],
        "corrections": [],
        "confidence": 0.8,
        "provider": "fake-first",
    }
    got = asyncio.run(
        ai._targeted_slot_repair(
            "Juki jarum 1 sering loncat kalau buat jahit",
            "cust_machine_desc",
            {},
            base,
        )
    )
    assert got["fields"]["machine_description"] == "Juki jarum 1"
    assert got["machines"][0]["machine"] == "Juki jarum 1"
    assert got["answers_current_slot"] is True
    assert got["slot_repair_used"] is True
    assert calls == ["fake"]


def test_targeted_slot_repair_does_not_invent_count(monkeypatch):
    async def fake_chat(provider, messages, temperature, max_tokens):
        return '{"answers_current_slot":true,"machine_count":1,"machine_description":"Juki","problem":null,"name":null,"landmark":null,"confidence":0.99}'

    monkeypatch.setattr(ai, "_chat", fake_chat)
    monkeypatch.setattr(ai, "_provider_order", lambda: ["fake"])

    base = {
        "intent": "SERVICE_REQUEST",
        "control": "NONE",
        "speech_acts": ["INFORMATION"],
        "service_requested": True,
        "answers_current_slot": False,
        "machine_count": None,
        "machines": [],
        "fields": {"name": None, "machine_description": None, "problem": None, "landmark": None},
        "questions": [],
        "corrections": [],
        "confidence": 0.8,
        "provider": "fake-first",
    }
    got = asyncio.run(ai._targeted_slot_repair("Juki", "cust_machine_desc", {}, base))
    assert got["machine_count"] is None
    assert got["fields"]["machine_description"] == "Juki"
