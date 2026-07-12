import logging

from psycopg import Connection

from rag_b3.common.audit import AuditLogger
from rag_b3.common.job_run import JobRunTracker
from rag_b3.common.time_utils import today_sao_paulo
from rag_b3.config.settings import Settings
from rag_b3.config.watchlist import load_watchlist
from rag_b3.ingestion.hg_brasil.budget_manager import (
    BudgetManager,
    PostgresBudgetRepository,
    QuotaExceededError,
)
from rag_b3.ingestion.hg_brasil.client import HgBrasilClient
from rag_b3.ingestion.hg_brasil.errors import (
    HgBrasilAuthError,
    HgBrasilError,
    HgBrasilPlanRestrictedError,
    HgBrasilPossibleQuotaExceeded,
)
from rag_b3.ingestion.hg_brasil.repository import (
    extract_ibovespa_close_and_variation,
    upsert_market_snapshot,
    upsert_stock_quote,
)
from rag_b3.ingestion.yahoo_finance.repository import upsert_daily_close_from_hg_brasil

logger = logging.getLogger(__name__)


def run_hg_brasil_ingestion(settings: Settings, conn: Connection) -> dict:
    """Job diário RF-02: 1 chamada ao endpoint principal (índices/moedas/
    taxas) + 1 chamada por ticker da watchlist. Nunca deve estourar o
    orçamento de requisições/dia — falhas parciais (ticker inválido, cota
    esgotada no meio do loop) são registradas e o job segue adiante com o
    que for possível, nunca falha silenciosamente."""
    tracker = JobRunTracker()
    audit = AuditLogger()
    job_run_id = tracker.start(conn, "hg_brasil")
    conn.commit()

    watchlist = load_watchlist(settings.watchlist_path)
    trade_date = today_sao_paulo()
    summary: dict = {
        "requested": 1 + len(watchlist),
        "succeeded": 0,
        "failed": 0,
        "skipped_quota": [],
        "skipped_plan_restricted": [],
    }

    budget = BudgetManager(PostgresBudgetRepository(conn), settings.hg_brasil_on_insufficient_budget)
    preflight = budget.preflight(summary["requested"])
    if preflight.mode == "abort":
        audit.log(
            conn,
            source="hg_brasil",
            action="preflight",
            status="aborted",
            job_run_id=job_run_id,
            metadata={
                "remaining_before": preflight.remaining_before,
                "estimated_calls": preflight.estimated_calls,
            },
        )
        tracker.finish(conn, job_run_id, "aborted_insufficient_budget", summary)
        conn.commit()
        return summary
    if preflight.mode == "partial":
        audit.log(
            conn,
            source="hg_brasil",
            action="preflight",
            status="partial",
            job_run_id=job_run_id,
            metadata={
                "remaining_before": preflight.remaining_before,
                "estimated_calls": preflight.estimated_calls,
            },
        )
        conn.commit()

    client = HgBrasilClient(settings.hg_brasil_api_key, budget)
    try:
        _fetch_market_snapshot(client, conn, audit, job_run_id, trade_date, summary)
        conn.commit()
    except (HgBrasilAuthError, HgBrasilPossibleQuotaExceeded) as exc:
        audit.log(
            conn,
            source="hg_brasil",
            action="fetch_finance_endpoint",
            status="aborted",
            error_code=exc.code,
            raw_response=exc.raw,
            job_run_id=job_run_id,
        )
        tracker.finish(conn, job_run_id, "failed", summary)
        conn.commit()
        client.close()
        return summary

    for i, ticker in enumerate(watchlist):
        try:
            raw = client.get_stock_price(ticker.symbol)
        except QuotaExceededError:
            skipped = [t.symbol for t in watchlist[i:]]
            summary["skipped_quota"] = skipped
            audit.log(
                conn,
                source="hg_brasil",
                action="budget_exhausted",
                status="budget_exhausted",
                job_run_id=job_run_id,
                metadata={"remaining_before": budget.remaining(), "tickers_skipped": skipped},
            )
            conn.commit()
            break
        except HgBrasilPossibleQuotaExceeded as exc:
            skipped = [t.symbol for t in watchlist[i:]]
            summary["skipped_quota"] = skipped
            audit.log(
                conn,
                source="hg_brasil",
                action="fetch_stock_price",
                request_ref=ticker.symbol,
                status="aborted",
                error_code=exc.code,
                raw_response=exc.raw,
                job_run_id=job_run_id,
                metadata={"tickers_skipped": skipped},
            )
            conn.commit()
            break
        except HgBrasilAuthError:
            # Fatal — a chave passou a ser inválida no meio do job. Aborta.
            summary["skipped_quota"] = [t.symbol for t in watchlist[i:]]
            tracker.finish(conn, job_run_id, "failed", summary)
            conn.commit()
            client.close()
            return summary
        except HgBrasilPlanRestrictedError as exc:
            # Restrição de PLANO (não de ticker específico) — todos os
            # tickers restantes falhariam do mesmo jeito, então parar aqui
            # evita desperdiçar cota em chamadas fadadas ao fracasso.
            skipped = [t.symbol for t in watchlist[i:]]
            summary["skipped_plan_restricted"] = skipped
            audit.log(
                conn,
                source="hg_brasil",
                action="fetch_stock_price",
                request_ref=ticker.symbol,
                status="aborted",
                error_code=exc.code,
                raw_response=exc.raw,
                job_run_id=job_run_id,
                metadata={"reason": exc.message, "tickers_skipped": skipped},
            )
            conn.commit()
            break
        except HgBrasilError as exc:
            summary["failed"] += 1
            audit.log(
                conn,
                source="hg_brasil",
                action="fetch_stock_price",
                request_ref=ticker.symbol,
                status="error",
                error_code=exc.code,
                raw_response=exc.raw,
                job_run_id=job_run_id,
            )
            conn.commit()
            continue

        try:
            upsert_stock_quote(conn, ticker.symbol, trade_date, job_run_id, raw)
            summary["succeeded"] += 1
            audit.log(
                conn,
                source="hg_brasil",
                action="fetch_stock_price",
                request_ref=ticker.symbol,
                status="success",
                raw_response=raw,
                job_run_id=job_run_id,
            )
            conn.commit()
        except Exception:
            logger.exception("Falha ao persistir cotação de %s", ticker.symbol)
            summary["failed"] += 1
            conn.rollback()

    client.close()

    if summary["failed"] == 0 and not summary["skipped_quota"] and not summary["skipped_plan_restricted"]:
        status = "success"
    elif summary["succeeded"] > 0:
        status = "partial_success"
    else:
        status = "failed"
    tracker.finish(conn, job_run_id, status, summary)
    conn.commit()
    return summary


def _fetch_market_snapshot(client, conn, audit, job_run_id, trade_date, summary) -> None:
    raw = client.get_market_snapshot()
    upsert_market_snapshot(conn, trade_date, job_run_id, raw)

    # Mantém ibov_daily_history como fonte única de série histórica do
    # índice (backfill via Yahoo + dia a dia via HG Brasil) — ver
    # yahoo_finance/repository.py.
    close, variation = extract_ibovespa_close_and_variation(raw)
    if close is not None:
        upsert_daily_close_from_hg_brasil(conn, trade_date, close, variation, job_run_id, raw)

    summary["succeeded"] += 1
    audit.log(
        conn,
        source="hg_brasil",
        action="fetch_finance_endpoint",
        status="success",
        raw_response=raw,
        job_run_id=job_run_id,
    )
