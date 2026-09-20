import asyncio

from app import conversation, customer
from app.types import IncomingMessage


def _msg(text: str, phone: str = "6200000000000") -> IncomingMessage:
    return IncomingMessage(
        message_id="v4-test",
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


def _analysis(**overrides):
    base = {
        "intent": "GENERAL_QUESTION",
        "control": "NONE",
        "speech_acts": [],
        "service_requested": False,
        "answers_current_slot": False,
        "machine_count": None,
        "machines": [],
        "fields": {"name": None, "machine_description": None, "problem": None, "landmark": None},
        "questions": [],
        "corrections": [],
        "normalized_text": "",
        "language_style": "INDONESIA_CASUAL",
        "confidence": 0.95,
        "requires_clarification": False,
    }
    base.update(overrides)
    return base


def test_normalize_indonesian_typo_and_javanese():
    value = conversation.normalize_chat_text("mkanike iso teko sesuk? msin jhkit sy srng lonct")
    assert "mekanik" in value
    assert "bisa" in value
    assert "datang" in value
    assert "besok" in value
    assert "mesin jahit" in value
    assert "sering loncat" in value


def test_detect_multiple_side_topics_in_one_message():
    topics = conversation.detect_side_topics("Mekanik bisa datang sore? terus ada garansinya tidak?")
    assert "schedule" in topics
    assert "warranty" in topics


def test_wants_service_indonesian_and_javanese():
    assert conversation.wants_service("Bisa bantu perbaiki mas?")
    assert conversation.wants_service("Tulung ndandani mesinku mas")
    assert conversation.wants_service("Aku arep servis")
    assert not conversation.wants_service("Mesin ini bisa diperbaiki tidak?")


def test_explicit_correction_signal():
    assert conversation.explicit_correction_signal("Tadi salah mas, bukan Juki, Pegasus obras")
    assert conversation.explicit_correction_signal("Yang tadi ternyata dua unit")
    assert not conversation.explicit_correction_signal("Mesin Juki sering loncat")


def test_apply_machine_count_correction_trims_items():
    payload = {
        "machine_count": 3,
        "items": [
            {"machine": "A", "problem": "x"},
            {"machine": "B", "problem": "y"},
            {"machine": "C", "problem": "z"},
        ],
    }
    analysis = _analysis(
        machine_count=2,
        speech_acts=["CORRECTION"],
        corrections=[{"field": "machine_count", "value": "2", "target_index": None}],
    )
    updated, notes = conversation.apply_corrections_to_payload(payload, analysis, "Tadi salah, ternyata 2 unit")
    assert updated["machine_count"] == 2
    assert len(updated["items"]) == 2
    assert notes


def test_apply_machine_correction_replaces_existing_machine():
    payload = {
        "machine_count": 1,
        "items": [{"machine": "Juki Jarum 1", "problem": "sering loncat"}],
    }
    analysis = _analysis(
        speech_acts=["CORRECTION"],
        corrections=[{"field": "machine", "value": "Pegasus Obras", "target_index": 1}],
    )
    updated, notes = conversation.apply_corrections_to_payload(payload, analysis, "Tadi salah, bukan Juki, Pegasus obras")
    assert updated["items"][0]["machine"] == "Pegasus Obras"
    assert updated["items"][0]["problem"] == "sering loncat"
    assert notes


def test_apply_problem_correction_keeps_machine():
    payload = {
        "machine_count": 1,
        "items": [{"machine": "Juki", "problem": "sering loncat"}],
    }
    analysis = _analysis(
        speech_acts=["CORRECTION"],
        corrections=[{"field": "problem", "value": "benang sering putus", "target_index": 1}],
    )
    updated, _ = conversation.apply_corrections_to_payload(payload, analysis, "Koreksi mas, bukan loncat, benangnya sering putus")
    assert updated["items"][0] == {"machine": "Juki", "problem": "benang sering putus"}


def test_conversation_summary_contains_facts_and_goal():
    payload = {
        "machine_count": 1,
        "items": [{"machine": "Juki", "problem": "sering loncat"}],
        "location": {"lat": -7.0, "lon": 110.0},
    }
    summary = conversation.build_conversation_summary(payload, "cust_media")
    assert "jumlah mesin 1" in summary
    assert "Juki: sering loncat" in summary
    assert "lokasi sudah diterima" in summary
    assert "cust_media" in summary


def test_resume_prompt_javanese_style_is_polite_and_keeps_goal():
    prompt = conversation.friendly_resume_prompt(
        "cust_machine_problem",
        {"current_machine": "Juki Jarum 1"},
        "JAWA_NGOKO",
    )
    assert prompt.startswith("Nggih")
    assert "apa keluhan" in prompt.lower()
    assert "Juki Jarum 1" in prompt


def test_side_questions_multiple_during_count_are_all_answered(monkeypatch):
    payload = {
        "customer_id": "c",
        "items": [],
        "prefill_machines": [{"machine": "Juki", "problem": "loncat"}],
    }

    async def fake_get_state(phone):
        return {"state": "cust_machine_count", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return _analysis(
            questions=[
                {"topic": "SCHEDULE", "text": "bisa datang sore?"},
                {"topic": "WARRANTY", "text": "ada garansi?"},
            ]
        )

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "quick_customer_signals", lambda text, state="": {"control": "NONE", "machine_count": None})

    reply = asyncio.run(customer.handle_customer_state(_msg("Mekanik bisa datang sore? terus ada garansinya tidak?")))
    assert "belum bisa saya janjikan" in reply.lower()
    assert "garansi" in reply.lower()
    assert "berapa unit mesin" in reply.lower()


def test_problem_price_schedule_one_message_records_problem_and_answers_both(monkeypatch):
    payload = {
        "customer_id": "c",
        "machine_count": 1,
        "machine_index": 1,
        "items": [],
        "current_machine": "Juki Jarum 1",
    }
    saved = {}

    async def fake_get_state(phone):
        return {"state": "cust_machine_problem", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return _analysis(
            intent="PRICE_QUESTION",
            machines=[{"machine": "", "problem": "sering loncat"}],
            fields={"name": None, "machine_description": None, "problem": "sering loncat", "landmark": None},
            questions=[
                {"topic": "PRICE", "text": "biayanya berapa"},
                {"topic": "SCHEDULE", "text": "bisa datang sore"},
            ],
        )

    async def fake_set_state(phone, state, new_payload):
        saved["state"] = state
        saved["payload"] = dict(new_payload)

    async def fake_price_answer(text, context_items=None):
        return "Biaya mengikuti hasil diagnosis."

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "set_state", fake_set_state)
    monkeypatch.setattr(customer, "price_answer", fake_price_answer)

    reply = asyncio.run(customer.handle_customer_state(_msg("Sering loncat mas, biayanya berapa dan mekaniknya bisa datang sore?")))
    assert saved["state"] == "cust_location"
    assert saved["payload"]["items"][0]["problem"] == "sering loncat"
    assert "biaya mengikuti" in reply.lower()
    assert "belum bisa saya janjikan" in reply.lower()
    assert "share location" in reply.lower()


def test_machine_correction_during_problem_uses_replacement(monkeypatch):
    payload = {
        "customer_id": "c",
        "machine_count": 1,
        "machine_index": 1,
        "items": [],
        "current_machine": "Juki Jarum 1",
    }
    saved = {}

    async def fake_get_state(phone):
        return {"state": "cust_machine_problem", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return _analysis(
            speech_acts=["CORRECTION"],
            machines=[{"machine": "Pegasus Obras", "problem": "suara kasar"}],
            fields={"name": None, "machine_description": "Pegasus Obras", "problem": "suara kasar", "landmark": None},
            corrections=[{"field": "machine", "value": "Pegasus Obras", "target_index": 1}],
        )

    async def fake_set_state(phone, state, new_payload):
        saved["state"] = state
        saved["payload"] = dict(new_payload)

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "set_state", fake_set_state)

    reply = asyncio.run(customer.handle_customer_state(_msg("Tadi salah mas, bukan Juki. Pegasus obras, suaranya kasar.")))
    assert saved["state"] == "cust_location"
    assert saved["payload"]["items"][0]["machine"] == "Pegasus Obras"
    assert saved["payload"]["items"][0]["problem"] == "suara kasar"
    assert "share location" in reply.lower()


def test_ai_service_requested_flag_can_start_top_level_intake(monkeypatch):
    async def fake_state(phone):
        return None

    async def fake_active(phone):
        return None

    async def fake_understand(text, state="", context=None):
        return _analysis(
            intent="GENERAL_QUESTION",
            service_requested=True,
            machines=[{"machine": "Juki", "problem": "sering loncat"}],
        )

    async def fake_start(msg, classified):
        assert classified["service_requested"] is True
        return "INTAKE DIMULAI"

    monkeypatch.setattr(customer, "get_state", fake_state)
    monkeypatch.setattr(customer, "active_order_for_customer", fake_active)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "_start_intake", fake_start)

    reply = asyncio.run(customer.handle_customer_message(_msg("Mas, iki tulung ditangani ya")))
    assert reply == "INTAKE DIMULAI"


def test_state_context_sent_to_nlu_contains_conversation_summary(monkeypatch):
    payload = {
        "customer_id": "c",
        "machine_count": 1,
        "items": [{"machine": "Juki", "problem": "loncat"}],
    }
    captured = {}

    async def fake_get_state(phone):
        return {"state": "cust_location", "payload": payload}

    async def fake_understand(text, state="", context=None):
        captured["context"] = context
        return _analysis()

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)

    asyncio.run(customer.handle_customer_state(_msg("Alamat kantor sampean mana?")))
    assert "conversation_summary" in captured["context"]
    assert "Juki" in captured["context"]["conversation_summary"]


def test_unknown_question_during_flow_does_not_erase_state(monkeypatch):
    payload = {
        "customer_id": "c",
        "items": [],
        "prefill_machines": [{"machine": "Juki", "problem": "loncat"}],
    }

    async def fake_get_state(phone):
        return {"state": "cust_machine_count", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return _analysis(questions=[{"topic": "OTHER", "text": text}])

    async def fake_general(text):
        return "Jawaban umum yang aman."

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "conversational_customer_reply", fake_general)
    monkeypatch.setattr(customer, "quick_customer_signals", lambda text, state="": {"control": "NONE", "machine_count": None})

    reply = asyncio.run(customer.handle_customer_state(_msg("Kalau hari hujan gimana mas?")))
    assert "Jawaban umum" in reply
    assert "berapa unit mesin" in reply.lower()


def test_count_correction_while_waiting_location_returns_to_missing_machine(monkeypatch):
    payload = {
        "customer_id": "c",
        "machine_count": 1,
        "items": [{"machine": "Juki", "problem": "loncat"}],
    }
    saved = {}

    async def fake_get_state(phone):
        return {"state": "cust_location", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return _analysis(
            machine_count=2,
            speech_acts=["CORRECTION"],
            corrections=[{"field": "machine_count", "value": "2", "target_index": None}],
        )

    async def fake_set_state(phone, state, new_payload):
        saved["state"] = state
        saved["payload"] = dict(new_payload)

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "set_state", fake_set_state)

    reply = asyncio.run(customer.handle_customer_state(_msg("Tadi salah mas, ternyata 2 unit")))
    assert saved["state"] == "cust_machine_desc"
    assert saved["payload"]["machine_count"] == 2
    assert "mesin ke-2" in reply.lower()


def test_problem_correction_while_waiting_location_keeps_location_goal(monkeypatch):
    payload = {
        "customer_id": "c",
        "machine_count": 1,
        "items": [{"machine": "Juki", "problem": "loncat"}],
    }
    saved = {}

    async def fake_get_state(phone):
        return {"state": "cust_location", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return _analysis(
            speech_acts=["CORRECTION"],
            corrections=[{"field": "problem", "value": "benang sering putus", "target_index": 1}],
        )

    async def fake_set_state(phone, state, new_payload):
        saved["state"] = state
        saved["payload"] = dict(new_payload)

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "set_state", fake_set_state)

    reply = asyncio.run(customer.handle_customer_state(_msg("Koreksi mas, bukan loncat. Benangnya sering putus")))
    assert saved["state"] == "cust_location"
    assert saved["payload"]["items"][0]["problem"] == "benang sering putus"
    assert "share location" in reply.lower()
    assert "menerima keterangan lokasi" not in reply.lower()


def test_yes_price_and_schedule_answers_both_then_moves_to_media(monkeypatch):
    payload = {
        "customer_id": "c",
        "machine_count": 1,
        "items": [{"machine": "Juki", "problem": "loncat"}],
        "location": {"lat": -7.0, "lon": 110.0, "name": "X", "address": "Y", "source": "WA"},
    }
    saved = {}

    async def fake_get_state(phone):
        return {"state": "cust_location_confirm", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return _analysis(
            intent="PRICE_QUESTION",
            control="YES",
            questions=[
                {"topic": "PRICE", "text": "biayanya berapa"},
                {"topic": "SCHEDULE", "text": "bisa sore"},
            ],
        )

    async def fake_set_state(phone, state, new_payload):
        saved["state"] = state
        saved["payload"] = dict(new_payload)

    async def fake_price_answer(text, context_items=None):
        return "Biaya mengikuti diagnosis."

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "set_state", fake_set_state)
    monkeypatch.setattr(customer, "price_answer", fake_price_answer)
    monkeypatch.setattr(customer, "quick_customer_signals", lambda text, state="": {"control": "YES", "machine_count": None})

    reply = asyncio.run(customer.handle_customer_state(_msg("Iya benar, biayanya berapa dan bisa datang sore?")))
    assert saved["state"] == "cust_media"
    assert "biaya mengikuti" in reply.lower()
    assert "belum bisa saya janjikan" in reply.lower()
    assert "foto/video" in reply.lower()
