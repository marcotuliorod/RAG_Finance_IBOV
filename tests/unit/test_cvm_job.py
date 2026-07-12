import uuid
from unittest.mock import MagicMock, patch

import httpx

from rag_b3.ingestion.cvm_rss.job import run_cvm_rss_ingestion
from tests.conftest import load_text_fixture


class _PatchedJob:
    def __init__(self, feeds: dict, fetch_side_effect):
        self.tracker_instance = MagicMock()
        self.tracker_instance.start.return_value = uuid.uuid4()
        self.audit_instance = MagicMock()
        self._patcher = patch.multiple(
            "rag_b3.ingestion.cvm_rss.job",
            FEEDS=feeds,
            JobRunTracker=MagicMock(return_value=self.tracker_instance),
            AuditLogger=MagicMock(return_value=self.audit_instance),
            _fetch_with_retry=MagicMock(side_effect=fetch_side_effect),
        )

    def __enter__(self):
        self._patcher.start()
        return self

    def __exit__(self, *exc_info):
        self._patcher.stop()


def test_all_feeds_ok_counts_new_items():
    feeds = {"decisoes": "https://example.invalid/decisoes.xml"}
    content = load_text_fixture("cvm_feed_sample_decisoes.xml")

    with _PatchedJob(feeds, [content]), patch(
        "rag_b3.ingestion.cvm_rss.job.upsert_feed_item", return_value=True
    ):
        summary = run_cvm_rss_ingestion(conn=MagicMock())

    assert summary["feeds_ok"] == 1
    assert summary["feeds_failed"] == 0
    assert summary["items_new"] == 2
    assert summary["items_duplicate"] == 0


def test_repeated_poll_counts_as_duplicate_not_new():
    feeds = {"decisoes": "https://example.invalid/decisoes.xml"}
    content = load_text_fixture("cvm_feed_sample_decisoes.xml")

    with _PatchedJob(feeds, [content]), patch(
        "rag_b3.ingestion.cvm_rss.job.upsert_feed_item", return_value=False
    ):
        summary = run_cvm_rss_ingestion(conn=MagicMock())

    assert summary["items_new"] == 0
    assert summary["items_duplicate"] == 2


def test_one_feed_failing_does_not_stop_the_others():
    feeds = {
        "decisoes": "https://example.invalid/decisoes.xml",
        "legislacao": "https://example.invalid/legislacao.xml",
    }
    content = load_text_fixture("cvm_feed_sample_decisoes.xml")

    with _PatchedJob(
        feeds, [httpx.ConnectError("timeout simulado"), content]
    ) as job, patch("rag_b3.ingestion.cvm_rss.job.upsert_feed_item", return_value=True):
        summary = run_cvm_rss_ingestion(conn=MagicMock())

    assert summary["feeds_failed"] == 1
    assert summary["feeds_ok"] == 1
    assert summary["items_new"] == 2
    finish_args = job.tracker_instance.finish.call_args.args
    assert finish_args[2] == "partial_success"
