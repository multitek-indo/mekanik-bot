import asyncio

from app import matching


class _FakeConnection:
    def __init__(self, order):
        self.order = order
        self.executed = []

    async def fetchrow(self, query, *args):
        return self.order

    async def execute(self, query, *args):
        self.executed.append((query, args))
        return "OK"


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return _Acquire(self.connection)


def test_no_technician_notify_customer_false_does_not_send_customer_message(
    monkeypatch,
):
    order = {
        "id": "order-id",
        "order_no": "MTK-TEST-1001",
        "assigned_technician_id": None,
    }
    fake_conn = _FakeConnection(order)

    monkeypatch.setattr(
        matching,
        "pool",
        lambda: _FakePool(fake_conn),
    )

    async def fake_candidate_list(value):
        return []

    status_changes = []

    async def fake_change_status(*args):
        status_changes.append(args)

    sent = []

    async def fake_send_text(phone, message):
        sent.append((phone, message))

    async def should_not_call_find_order(order_no):
        raise AssertionError(
            "find_order tidak boleh dipanggil ketika notify_customer=False"
        )

    monkeypatch.setattr(
        matching,
        "candidate_list",
        fake_candidate_list,
    )
    monkeypatch.setattr(
        matching,
        "change_status",
        fake_change_status,
    )
    monkeypatch.setattr(
        matching,
        "send_text",
        fake_send_text,
    )
    monkeypatch.setattr(
        matching,
        "find_order",
        should_not_call_find_order,
    )

    result = asyncio.run(
        matching.start_offer_batch(
            "order-id",
            notify_customer=False,
        )
    )

    assert result is False
    assert status_changes
    assert any(
        phone == matching.settings.owner_wa_number
        for phone, _ in sent
    )
    assert all(
        "Saat ini belum ada mekanik" not in message
        for _, message in sent
    )


def test_offer_batch_still_forwards_customer_image_and_video(
    monkeypatch,
):
    order = {
        "id": "order-id",
        "order_no": "MTK-TEST-1002",
        "assigned_technician_id": None,
    }
    fake_conn = _FakeConnection(order)

    monkeypatch.setattr(
        matching,
        "pool",
        lambda: _FakePool(fake_conn),
    )

    candidate = {
        "tech": {
            "id": "tech-id",
            "wa_number": "6200000000001",
        },
        "distance": 2.5,
        "coverage": 1.0,
        "average_skill": 5.0,
        "levels": {},
        "required": [],
        "location_source": "base",
    }

    async def fake_candidate_list(value):
        return [candidate]

    async def fake_order_items(order_id):
        return [
            {
                "item_no": 1,
                "machine_text": "Juki jarum satu",
                "complaint": "error 03",
            }
        ]

    async def fake_change_status(*args):
        return None

    async def fake_refs(order_id):
        return [
            {
                "media_type": "image",
                "local_path": "/tmp/test.jpg",
                "item_no": 1,
                "machine_text": "Juki jarum satu",
            },
            {
                "media_type": "video",
                "local_path": "/tmp/test.mp4",
                "item_no": 1,
                "machine_text": "Juki jarum satu",
            },
        ]

    sent_text = []
    sent_images = []
    sent_files = []

    async def fake_send_text(phone, message):
        sent_text.append((phone, message))

    async def fake_send_image(phone, path, caption=""):
        sent_images.append((phone, path, caption))
        return True

    async def fake_send_file(phone, path, caption=""):
        sent_files.append((phone, path, caption))
        return True

    monkeypatch.setattr(
        matching,
        "candidate_list",
        fake_candidate_list,
    )
    monkeypatch.setattr(
        matching,
        "order_items",
        fake_order_items,
    )
    monkeypatch.setattr(
        matching,
        "change_status",
        fake_change_status,
    )
    monkeypatch.setattr(
        matching,
        "_customer_reference_media",
        fake_refs,
    )
    monkeypatch.setattr(
        matching,
        "send_text",
        fake_send_text,
    )
    monkeypatch.setattr(
        matching,
        "send_image",
        fake_send_image,
    )
    monkeypatch.setattr(
        matching,
        "send_file",
        fake_send_file,
    )

    result = asyncio.run(
        matching.start_offer_batch(
            "order-id",
            notify_customer=False,
        )
    )

    assert result is True
    assert len(sent_text) == 1
    assert len(sent_images) == 1
    assert len(sent_files) == 1
    assert "Juki jarum satu" in sent_images[0][2]
    assert "Juki jarum satu" in sent_files[0][2]
