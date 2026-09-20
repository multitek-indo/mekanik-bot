import asyncio

from app import customer
from app.types import IncomingMessage


def _msg(text: str, phone: str = "6200000000000") -> IncomingMessage:
    return IncomingMessage(
        message_id="test-message",
        phone=phone,
        sender_name="Test Customer",
        text=text,
        location=None,
        image=None,
        video=None,
        document=None,
        media_type=None,
        media_path=None,
        raw_payload={},
    )


class _FakeConnection:
    def __init__(self, row=None):
        self.row = row

    async def fetchrow(self, query, *args):
        return self.row

    async def execute(self, query, *args):
        return "OK"


class _Acquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _Acquire(self.conn)


def test_price_followup_detector_is_specific():
    assert customer._looks_like_price_question("Kalau yang ringan berapa?")
    assert customer._looks_like_price_question("Booking masuk jasa tidak?")
    assert customer._looks_like_price_question("Spare part sudah termasuk belum?")
    assert not customer._looks_like_price_question("Ada berapa mesin?")


def test_price_followup_light_returns_only_requested_tier(monkeypatch):
    row = {
        "skill_name": "Mesin Jarum 1",
        "inspection_fee": 50000,
        "light_fee": 150000,
        "medium_fee": 250000,
        "heavy_fee": 400000,
    }

    monkeypatch.setattr(customer, "detect_skill_code", lambda text: "SINGLE_NEEDLE")
    monkeypatch.setattr(customer, "pool", lambda: _FakePool(_FakeConnection(row)))

    reply = asyncio.run(
        customer.price_answer(
            "Kalau yang ringan berapa?",
            [{"machine": "Juki jarum 1", "problem": "error 03"}],
        )
    )

    assert "ringan" in reply.lower()
    assert "150" in reply
    assert "Tarif booking saat ini" not in reply
    assert "spare part" in reply.lower()


def test_schedule_question_during_problem_does_not_become_problem(monkeypatch):
    payload = {
        "customer_id": "customer-id",
        "machine_count": 1,
        "machine_index": 1,
        "items": [],
        "current_machine": "Juki DDL-8700",
    }

    async def fake_get_state(phone):
        return {"state": "cust_machine_problem", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return {
            "intent": "GENERAL_QUESTION",
            "control": "NONE",
            "machine_count": None,
            "machines": [],
            "fields": {
                "name": None,
                "machine_description": None,
                "problem": None,
                "landmark": None,
            },
            "normalized_text": text,
            "requires_clarification": False,
        }

    async def should_not_finish(*args, **kwargs):
        raise AssertionError("Pertanyaan jadwal tidak boleh disimpan sebagai keluhan mesin")

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "_finish_machine_item", should_not_finish)

    reply = asyncio.run(
        customer.handle_customer_state(
            _msg("Mekaniknya bisa datang sore?")
        )
    )

    assert "belum bisa saya janjikan" in reply.lower()
    assert "apa keluhan" in reply.lower()
    assert "Juki DDL-8700" in reply


def test_price_detail_during_problem_preserves_problem_state(monkeypatch):
    payload = {
        "customer_id": "customer-id",
        "machine_count": 1,
        "machine_index": 1,
        "items": [],
        "current_machine": "Juki jarum 1",
    }

    async def fake_get_state(phone):
        return {"state": "cust_machine_problem", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return {
            "intent": "PRICE_QUESTION",
            "control": "NONE",
            "machine_count": None,
            "machines": [],
            "fields": {
                "name": None,
                "machine_description": None,
                "problem": None,
                "landmark": None,
            },
            "normalized_text": text,
            "requires_clarification": False,
        }

    async def fake_price_answer(text, context_items=None):
        assert context_items
        assert any(
            item.get("machine") == "Juki jarum 1"
            for item in context_items
        )
        return "Kategori ringan Rp150.000"

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "price_answer", fake_price_answer)

    reply = asyncio.run(
        customer.handle_customer_state(
            _msg("Kalau yang ringan berapa?")
        )
    )

    assert "Rp150.000" in reply
    assert "apa keluhan" in reply.lower()
    assert "Juki jarum 1" in reply


def test_schedule_question_during_landmark_does_not_create_order(monkeypatch):
    payload = {
        "customer_id": "customer-id",
        "items": [
            {"machine": "Juki jarum 1", "problem": "error 03"}
        ],
        "location": {
            "lat": -7.0,
            "lon": 110.0,
            "name": "Lokasi Test",
            "address": "Alamat Test",
            "source": "WHATSAPP_SHARE_LOCATION",
        },
    }

    async def fake_get_state(phone):
        return {"state": "cust_landmark", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return {
            "intent": "GENERAL_QUESTION",
            "control": "NONE",
            "machine_count": None,
            "machines": [],
            "fields": {
                "name": None,
                "machine_description": None,
                "problem": None,
                "landmark": None,
            },
            "normalized_text": text,
            "requires_clarification": False,
        }

    async def should_not_create(*args, **kwargs):
        raise AssertionError("Pertanyaan jadwal tidak boleh dianggap sebagai landmark")

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "create_order", should_not_create)

    reply = asyncio.run(
        customer.handle_customer_state(
            _msg("Kalau besok bisa datang sore?")
        )
    )

    assert "belum bisa saya janjikan" in reply.lower()
    assert "patokan" in reply.lower()


def test_warranty_question_during_media_is_answered_and_media_flow_remains(monkeypatch):
    payload = {
        "customer_id": "customer-id",
        "items": [
            {"machine": "Juki jarum 1", "problem": "error 03"}
        ],
        "media_item_no": 1,
        "customer_media": [],
    }

    async def fake_get_state(phone):
        return {"state": "cust_media", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return {
            "intent": "GENERAL_QUESTION",
            "control": "NONE",
            "machine_count": None,
            "machines": [],
            "fields": {
                "name": None,
                "machine_description": None,
                "problem": None,
                "landmark": None,
            },
            "normalized_text": text,
            "requires_clarification": False,
        }

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)

    reply = asyncio.run(
        customer.handle_customer_state(
            _msg("Ada garansi tidak?")
        )
    )

    assert "garansi" in reply.lower()
    assert "foto/video" in reply.lower()
    assert "Juki jarum 1" in reply


def test_count_plus_problem_in_one_message_is_not_lost(monkeypatch):
    payload = {
        "customer_id": "customer-id",
        "items": [],
        "prefill_machines": [
            {"machine": "mesin jahit", "problem": ""}
        ],
    }
    saved = {}

    async def fake_get_state(phone):
        return {"state": "cust_machine_count", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return {
            "intent": "GENERAL_QUESTION",
            "control": "NONE",
            "machine_count": 1,
            "machines": [],
            "fields": {
                "name": None,
                "machine_description": None,
                "problem": None,
                "landmark": None,
            },
            "normalized_text": text,
            "requires_clarification": False,
        }

    async def fake_set_state(phone, state, new_payload):
        saved["state"] = state
        saved["payload"] = dict(new_payload)

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(
        customer,
        "quick_customer_signals",
        lambda text, state="": {"control": "NONE", "machine_count": 1},
    )
    monkeypatch.setattr(customer, "set_state", fake_set_state)

    reply = asyncio.run(
        customer.handle_customer_state(
            _msg("Satu mas mesinnya sering loncatan")
        )
    )

    assert saved["state"] == "cust_location"
    assert saved["payload"]["items"][0]["machine"] == "mesin jahit"
    assert saved["payload"]["items"][0]["problem"] == "sering loncatan"
    assert "share location" in reply.lower()


def test_short_problem_statement_is_not_sent_to_general_chat(monkeypatch):
    payload = {
        "customer_id": "customer-id",
        "machine_count": 1,
        "machine_index": 1,
        "items": [],
        "current_machine": "mesin jahit",
    }
    captured = {}

    async def fake_get_state(phone):
        return {"state": "cust_machine_problem", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return {
            "intent": "GENERAL_QUESTION",
            "control": "NONE",
            "machine_count": None,
            "machines": [],
            "fields": {
                "name": None,
                "machine_description": None,
                "problem": None,
                "landmark": None,
            },
            "normalized_text": text,
            "requires_clarification": False,
        }

    async def fake_finish(phone, state_payload, machine, problem):
        captured["machine"] = machine
        captured["problem"] = problem
        return "NEXT"

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(
        customer,
        "quick_customer_signals",
        lambda text, state="": {"control": "NONE", "machine_count": None},
    )
    monkeypatch.setattr(customer, "_finish_machine_item", fake_finish)

    reply = asyncio.run(
        customer.handle_customer_state(
            _msg("Sering loncat mas")
        )
    )

    assert reply == "NEXT"
    assert captured["machine"] == "mesin jahit"
    assert captured["problem"] == "Sering loncat mas"


def test_javanese_typo_normalizer_handles_common_chat_forms():
    normalized = customer._normalize_customer_text(
        "Sampean omahe neng endi? Brp biya servis e mas?"
    )

    assert "anda" in normalized
    assert "rumah" in normalized
    assert "mana" in normalized
    assert "berapa" in normalized
    assert "biaya" in normalized


def test_javanese_side_question_topics_are_understood():
    assert customer._side_question_topic("Sampean omahe neng endi?") == "company_identity"
    assert customer._side_question_topic("Mkanik iso teko sore ra?") == "schedule"
    assert customer._side_question_topic("Ono garansine ora?") == "warranty"


def test_company_identity_question_during_count_is_answered_and_count_state_remains(monkeypatch):
    payload = {
        "customer_id": "customer-id",
        "items": [],
        "prefill_machines": [
            {"machine": "Juki Jarum 1", "problem": "sering loncat"}
        ],
    }

    async def fake_get_state(phone):
        return {"state": "cust_machine_count", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return {
            "intent": "GENERAL_QUESTION",
            "control": "NONE",
            "machine_count": None,
            "machines": [],
            "fields": {
                "name": None,
                "machine_description": None,
                "problem": None,
                "landmark": None,
            },
            "normalized_text": text,
            "requires_clarification": False,
        }

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(
        customer,
        "quick_customer_signals",
        lambda text, state="": {"control": "NONE", "machine_count": None},
    )

    reply = asyncio.run(
        customer.handle_customer_state(
            _msg("Sampean rumahnya mana?")
        )
    )

    assert "admin virtual multitek service" in reply.lower()
    assert "berapa unit mesin" in reply.lower()
    assert "ceritakan kebutuhan" not in reply.lower()


def test_mixed_problem_and_schedule_records_problem_then_answers_schedule(monkeypatch):
    payload = {
        "customer_id": "customer-id",
        "machine_count": 1,
        "machine_index": 1,
        "items": [],
        "current_machine": "Juki Jarum 1",
    }
    captured = {}

    async def fake_get_state(phone):
        return {"state": "cust_machine_problem", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return {
            "intent": "GENERAL_QUESTION",
            "control": "NONE",
            "machine_count": None,
            "machines": [],
            "fields": {
                "name": None,
                "machine_description": None,
                "problem": None,
                "landmark": None,
            },
            "normalized_text": text,
            "requires_clarification": False,
        }

    async def fake_finish(phone, state_payload, machine, problem):
        state_payload["items"] = [{"machine": machine, "problem": problem}]
        state_payload.pop("current_machine", None)
        captured["machine"] = machine
        captured["problem"] = problem
        return "Sekarang kirim Share Location lokasi mesin."

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "_finish_machine_item", fake_finish)
    monkeypatch.setattr(
        customer,
        "quick_customer_signals",
        lambda text, state="": {"control": "NONE", "machine_count": None},
    )

    reply = asyncio.run(
        customer.handle_customer_state(
            _msg("Sering loncat mas, mekanike iso teko sore?")
        )
    )

    assert captured["machine"] == "Juki Jarum 1"
    assert "loncat" in captured["problem"].lower()
    assert "bisa saya bantu carikan jadwal" in reply.lower()
    assert "share location" in reply.lower()


def test_count_problem_and_schedule_in_one_message_keeps_all_useful_information(monkeypatch):
    payload = {
        "customer_id": "customer-id",
        "items": [],
        "prefill_machines": [
            {"machine": "Juki Jarum 1", "problem": ""}
        ],
    }
    saved = {}

    async def fake_get_state(phone):
        return {"state": "cust_machine_count", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return {
            "intent": "GENERAL_QUESTION",
            "control": "NONE",
            "machine_count": 1,
            "machines": [],
            "fields": {
                "name": None,
                "machine_description": None,
                "problem": None,
                "landmark": None,
            },
            "normalized_text": text,
            "requires_clarification": False,
        }

    async def fake_set_state(phone, state, new_payload):
        saved["state"] = state
        saved["payload"] = dict(new_payload)

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "set_state", fake_set_state)
    monkeypatch.setattr(
        customer,
        "quick_customer_signals",
        lambda text, state="": {"control": "NONE", "machine_count": 1},
    )

    reply = asyncio.run(
        customer.handle_customer_state(
            _msg("Siji mas, mesine sering loncat. Mekanike iso teko sore?")
        )
    )

    assert saved["state"] == "cust_location"
    assert saved["payload"]["items"][0]["machine"] == "Juki Jarum 1"
    assert "loncat" in saved["payload"]["items"][0]["problem"].lower()
    assert "bisa saya bantu carikan jadwal" in reply.lower()
    assert "share location" in reply.lower()


def test_machine_description_plus_schedule_keeps_machine_then_resumes_problem(monkeypatch):
    payload = {
        "customer_id": "customer-id",
        "machine_count": 1,
        "machine_index": 1,
        "items": [],
    }
    saved = {}

    async def fake_get_state(phone):
        return {"state": "cust_machine_desc", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return {
            "intent": "GENERAL_QUESTION",
            "control": "NONE",
            "machine_count": None,
            "machines": [{"machine": "Juki Jarum 1", "problem": ""}],
            "fields": {
                "name": None,
                "machine_description": "Juki Jarum 1",
                "problem": None,
                "landmark": None,
            },
            "normalized_text": text,
            "requires_clarification": False,
        }

    async def fake_set_state(phone, state, new_payload):
        saved["state"] = state
        saved["payload"] = dict(new_payload)

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "set_state", fake_set_state)
    monkeypatch.setattr(
        customer,
        "quick_customer_signals",
        lambda text, state="": {"control": "NONE", "machine_count": None},
    )

    reply = asyncio.run(
        customer.handle_customer_state(
            _msg("Juki jarum 1 mas, mekanike iso teko sore?")
        )
    )

    assert saved["state"] == "cust_machine_problem"
    assert saved["payload"]["current_machine"] == "Juki Jarum 1"
    assert "bisa saya bantu carikan jadwal" in reply.lower()
    assert "gejala" in reply.lower()
    assert "Juki Jarum 1" in reply


def test_name_state_does_not_store_machine_problem_as_customer_name(monkeypatch):
    payload = {"customer_id": "customer-id", "items": []}
    saved = {}

    async def fake_get_state(phone):
        return {"state": "cust_name", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return {
            "intent": "SERVICE_REQUEST",
            "control": "NONE",
            "machine_count": None,
            "machines": [{"machine": "Juki Jarum 1", "problem": "sering loncat"}],
            "fields": {
                "name": None,
                "machine_description": "Juki Jarum 1",
                "problem": "sering loncat",
                "landmark": None,
            },
            "normalized_text": text,
            "requires_clarification": False,
        }

    async def fake_set_state(phone, state, new_payload):
        saved["state"] = state
        saved["payload"] = dict(new_payload)

    class NeverPool:
        def acquire(self):
            raise AssertionError("Nama yang bukan nama tidak boleh ditulis ke database")

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "set_state", fake_set_state)
    monkeypatch.setattr(customer, "pool", lambda: NeverPool())
    monkeypatch.setattr(
        customer,
        "quick_customer_signals",
        lambda text, state="": {"control": "NONE", "machine_count": None},
    )

    reply = asyncio.run(
        customer.handle_customer_state(_msg("Mesinnya Juki sering loncat mas"))
    )

    assert "nama" in reply.lower()
    assert saved["state"] == "cust_name"
    assert saved["payload"]["prefill_machines"][0]["machine"] == "Juki Jarum 1"
    assert saved["payload"]["prefill_machines"][0]["problem"] == "sering loncat"


def test_problem_given_while_waiting_machine_description_is_remembered(monkeypatch):
    payload = {
        "customer_id": "customer-id",
        "machine_count": 1,
        "machine_index": 1,
        "items": [],
    }
    saved = {}

    async def fake_get_state(phone):
        return {"state": "cust_machine_desc", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return {
            "intent": "SERVICE_REQUEST",
            "control": "NONE",
            "machine_count": None,
            "machines": [{"machine": "", "problem": "benangnya sering putus"}],
            "fields": {
                "name": None,
                "machine_description": None,
                "problem": "benangnya sering putus",
                "landmark": None,
            },
            "normalized_text": text,
            "requires_clarification": False,
        }

    async def fake_set_state(phone, state, new_payload):
        saved["state"] = state
        saved["payload"] = dict(new_payload)

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "set_state", fake_set_state)
    monkeypatch.setattr(
        customer,
        "quick_customer_signals",
        lambda text, state="": {"control": "NONE", "machine_count": None},
    )

    reply = asyncio.run(
        customer.handle_customer_state(_msg("Benange sering pedot mas"))
    )

    assert saved["state"] == "cust_machine_desc"
    assert saved["payload"]["pending_problem"] == "benangnya sering putus"
    assert "keluhannya sudah saya catat" in reply.lower()
    assert "merek" in reply.lower()


def test_unrelated_declarative_text_is_not_saved_as_landmark(monkeypatch):
    payload = {
        "customer_id": "customer-id",
        "items": [{"machine": "Juki", "problem": "loncat"}],
        "location": {"lat": -7.0, "lon": 110.0, "name": "X", "address": "Y", "source": "WA"},
    }

    async def fake_get_state(phone):
        return {"state": "cust_landmark", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return {
            "intent": "GENERAL_QUESTION",
            "control": "NONE",
            "machine_count": None,
            "machines": [],
            "fields": {"name": None, "machine_description": None, "problem": None, "landmark": None},
            "normalized_text": text,
            "requires_clarification": False,
        }

    async def should_not_create(*args, **kwargs):
        raise AssertionError("Teks acak tidak boleh menjadi landmark")

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "create_order", should_not_create)
    monkeypatch.setattr(
        customer,
        "quick_customer_signals",
        lambda text, state="": {"control": "NONE", "machine_count": None},
    )

    reply = asyncio.run(
        customer.handle_customer_state(_msg("Nanti aja mas saya masih kerja"))
    )

    assert "belum menangkap patokannya" in reply.lower()


def test_location_yes_plus_price_question_advances_and_answers_price(monkeypatch):
    payload = {
        "customer_id": "customer-id",
        "machine_count": 1,
        "items": [{"machine": "Juki", "problem": "loncat"}],
        "location": {"lat": -7.0, "lon": 110.0, "name": "X", "address": "Y", "source": "WA"},
    }
    saved = {}

    async def fake_get_state(phone):
        return {"state": "cust_location_confirm", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return {
            "intent": "PRICE_QUESTION",
            "control": "YES",
            "machine_count": None,
            "machines": [],
            "fields": {"name": None, "machine_description": None, "problem": None, "landmark": None},
            "normalized_text": text,
            "requires_clarification": False,
        }

    async def fake_set_state(phone, state, new_payload):
        saved["state"] = state
        saved["payload"] = dict(new_payload)

    async def fake_price_answer(text, context_items=None):
        return "Biaya saya jelaskan dari matrix."

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "set_state", fake_set_state)
    monkeypatch.setattr(customer, "price_answer", fake_price_answer)
    monkeypatch.setattr(
        customer,
        "quick_customer_signals",
        lambda text, state="": {"control": "YES", "machine_count": None},
    )

    reply = asyncio.run(
        customer.handle_customer_state(_msg("Iya benar, tapi biayanya berapa?"))
    )

    assert saved["state"] == "cust_media"
    assert "biaya saya jelaskan" in reply.lower()
    assert "foto atau video" in reply.lower()


def test_media_finish_plus_warranty_question_advances_and_answers(monkeypatch):
    payload = {
        "customer_id": "customer-id",
        "items": [{"machine": "Juki", "problem": "loncat"}],
        "media_item_no": 1,
        "customer_media": [],
    }
    saved = {}

    async def fake_get_state(phone):
        return {"state": "cust_media", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return {
            "intent": "GENERAL_QUESTION",
            "control": "NONE",
            "machine_count": None,
            "machines": [],
            "fields": {"name": None, "machine_description": None, "problem": None, "landmark": None},
            "normalized_text": text,
            "requires_clarification": False,
        }

    async def fake_set_state(phone, state, new_payload):
        saved["state"] = state
        saved["payload"] = dict(new_payload)

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "set_state", fake_set_state)
    monkeypatch.setattr(
        customer,
        "quick_customer_signals",
        lambda text, state="": {"control": "NONE", "machine_count": None},
    )

    reply = asyncio.run(
        customer.handle_customer_state(_msg("Selesai, terus ada garansinya ora?"))
    )

    assert saved["state"] == "cust_landmark"
    assert "garansi" in reply.lower()
    assert "patokan" in reply.lower()
