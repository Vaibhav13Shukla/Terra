"""Unit tests for SQSAnalysisQueue, using a tiny in-memory fake client (not
boto3/moto — boto3 is intentionally not installed in this environment by
design; see backend/requirements.txt and app.services.dynamodb_job_store for
the same pattern). The fake implements exactly the send_message surface the
`_SQSClient` Protocol uses, so this test exercises the real
serialization logic, not just that a mocked method was called.
"""
from __future__ import annotations

import datetime as dt
import json

from app.domain.models import AOI, AnalysisRequest, AnalysisType, DateRange
from app.services.analysis_queue import SQSAnalysisQueue


class FakeSQSClient:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send_message(self, QueueUrl: str, MessageBody: str) -> dict:
        self.sent.append({"QueueUrl": QueueUrl, "MessageBody": MessageBody})
        return {"MessageId": "fake-message-id"}


def _request() -> AnalysisRequest:
    return AnalysisRequest(
        aoi=AOI(
            coordinates=[
                [
                    (-120.60, 36.95),
                    (-120.55, 36.95),
                    (-120.55, 37.00),
                    (-120.60, 37.00),
                    (-120.60, 36.95),
                ]
            ]
        ),
        analysis_type=AnalysisType.NDVI_SNAPSHOT,
        date_range=DateRange(start=dt.date(2025, 8, 1), end=dt.date(2025, 8, 31)),
    )


def test_enqueue_sends_job_id_and_serialized_request():
    client = FakeSQSClient()
    queue = SQSAnalysisQueue(client, "https://sqs.example/queue")
    queue.enqueue("job-1", _request())

    assert len(client.sent) == 1
    assert client.sent[0]["QueueUrl"] == "https://sqs.example/queue"
    body = json.loads(client.sent[0]["MessageBody"])
    assert body["job_id"] == "job-1"
    assert body["request"]["analysis_type"] == "ndvi_snapshot"
    # Round-trips through the domain model unchanged.
    assert AnalysisRequest.model_validate(body["request"]).aoi.bbox() == _request().aoi.bbox()
