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


def test_price_question_detector():
    assert customer._looks_like_price_question("Biayanya berapa ya kira kira")
    assert customer._looks_like_price_question("Untuk biaya servisnya berapa?")
    assert not customer._looks_like_price_question("mesin saya error 03")


def test_customer_status_no_technician_is_human_friendly(monkeypatch):
    async def fake_find_order(order_no):
        return {
            "id": "order-id",
            "order_no": order_no,
            "status": "NO_TECHNICIAN",
            "technician_name": None,
        }

    async def fake_order_items(order_id):
        return [
            {
                "machine_text": "Juki jarum satu",
                "complaint": "error 03",
            }
        ]

    monkeypatch.setattr(customer, "find_order", fake_find_order)
    monkeypatch.setattr(customer, "order_items", fake_order_items)

    reply = asyncio.run(
        customer.customer_status_summary("MTK-TEST-0001")
    )

    assert "belum ada mekanik" in reply.lower()
    assert "Juki jarum satu" in reply
    assert "NO_TECHNICIAN" not in reply
    assert "UNPAID" not in reply
    assert "DECLARED" not in reply


def test_price_question_during_media_flow_keeps_conversation(monkeypatch):
    payload = {
        "customer_id": "customer-id",
        "items": [
            {
                "machine": "Juki jarum satu",
                "problem": "error 03",
            }
        ],
        "media_item_no": 1,
        "customer_media": [],
    }

    async def fake_get_state(phone):
        return {
            "state": "cust_media",
            "payload": payload,
        }

    async def fake_price_answer(text, context_items=None):
        assert context_items
        assert context_items[0]["machine"] == "Juki jarum satu"
        return "JAWABAN HARGA"

    async def fake_understand(text, state="", context=None):
        return {
            "intent": "PRICE_QUESTION",
            "control": "NONE",
            "speech_acts": ["QUESTION"],
            "service_requested": False,
            "answers_current_slot": False,
            "machine_count": None,
            "machines": [],
            "fields": {
                "name": None,
                "machine_description": None,
                "problem": None,
                "landmark": None,
            },
            "questions": [
                {
                    "topic": "PRICE",
                    "text": text,
                }
            ],
            "corrections": [],
            "normalized_text": text,
            "language_style": "INDONESIA_CASUAL",
            "confidence": 1.0,
            "requires_clarification": False,
            "provider": "local",
        }

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "price_answer", fake_price_answer)
    monkeypatch.setattr(
        customer,
        "understand_customer_message",
        fake_understand,
    )

    reply = asyncio.run(
        customer.handle_customer_state(
            _msg("Biayanya berapa ya kira kira")
        )
    )

    low = reply.lower()
    assert "JAWABAN HARGA" in reply
    assert "foto" in low
    assert "video" in low
    assert "Juki jarum satu" in reply


def test_landmark_cukup_creates_order_and_suppresses_matching_direct_customer_message(
    monkeypatch,
):
    phone = "6200000000000"
    payload = {
        "customer_id": "customer-id",
        "items": [
            {
                "machine": "Juki jarum satu",
                "problem": "error 03",
            }
        ],
        "location": {
            "lat": -7.0,
            "lon": 110.0,
            "name": "Lokasi Test",
            "address": "Alamat Test",
            "source": "WHATSAPP_SHARE_LOCATION",
        },
        "customer_media": [],
    }

    async def fake_get_state(value):
        return {
            "state": "cust_landmark",
            "payload": payload,
        }

    async def fake_get_or_create_customer(value, name=None):
        return {
            "id": "customer-id",
            "name": "Customer Test",
        }

    async def fake_create_order(customer_id, location, landmark, items):
        assert landmark == ""
        return {
            "id": "order-id",
            "order_no": "MTK-TEST-0002",
        }

    async def fake_persist_customer_media(order_id, actor_phone, state_payload):
        return None

    async def fake_clear_state(value):
        return None

    matching_calls = []

    async def fake_start_offer_batch(
        order_id,
        notify_customer=True,
    ):
        matching_calls.append(
            {
                "order_id": order_id,
                "notify_customer": notify_customer,
            }
        )
        return False

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(
        customer,
        "get_or_create_customer",
        fake_get_or_create_customer,
    )
    monkeypatch.setattr(customer, "create_order", fake_create_order)
    monkeypatch.setattr(
        customer,
        "_persist_customer_media",
        fake_persist_customer_media,
    )
    monkeypatch.setattr(customer, "clear_state", fake_clear_state)
    monkeypatch.setattr(
        customer,
        "start_offer_batch",
        fake_start_offer_batch,
    )

    reply = asyncio.run(
        customer.handle_customer_state(
            _msg("Cukup", phone=phone)
        )
    )

    assert matching_calls == [
        {
            "order_id": "order-id",
            "notify_customer": False,
        }
    ]
    assert "MTK-TEST-0002" in reply
    assert "belum ada mekanik" in reply.lower()
