from __future__ import annotations
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from zoneinfo import ZoneInfo
from app.core.config import settings
from app.services.ai_enricher import enrich_all_details
from app.services.notify import notify

# Instancia global (modo background, no bloquea FastAPI)
scheduler = BackgroundScheduler(timezone=ZoneInfo(settings.SCHEDULER_TIMEZONE))

def _log_listener(event):
    if event.exception:
        notify(
            subject=f"ETL job {event.job_id} FAILED",
            text=str(event.exception),
            severity="ERROR",
            payload={"job_id": event.job_id}
        )
        print(f"[APScheduler] Job {event.job_id} ERROR: {event.exception}")
    else:
        notify(
            subject=f"ETL job {event.job_id} OK",
            text="Ejecución correcta.",
            severity="INFO",
            payload={"job_id": event.job_id}
        )
        print(f"[APScheduler] Job {event.job_id} executed OK.")

# registra listener 1 sola vez
scheduler.add_listener(_log_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

def start_scheduler():
    if not scheduler.running:
        scheduler.start()

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()

def schedule_daily_etl():
    """Agenda el job incremental real usando el CRON de settings."""
    from app.services.etl_jobs import etl_daily_job  # import diferido

    trigger = CronTrigger.from_crontab(
        settings.SCHEDULER_CRON,
        timezone=ZoneInfo(settings.SCHEDULER_TIMEZONE),
    )

    job_id = "etl_daily"
    if scheduler.get_job(job_id):
        scheduler.reschedule_job(job_id, trigger=trigger)
    else:
        # max_instances=1 evita superposición si la corrida anterior demora
        # coalesce=True junta “disparos atrasados” en uno
        # misfire_grace_time=300 tolera hasta 5 minutos de atraso al disparar
        scheduler.add_job(
            lambda: etl_daily_job(source="scheduler"),
            trigger,
            id=job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
    j = scheduler.get_job(job_id)
    print(f"[APScheduler] '{job_id}' scheduled: cron='{settings.SCHEDULER_CRON}' tz='{settings.SCHEDULER_TIMEZONE}' next_run={j.next_run_time}")

def schedule_daily_ai(sched):
    # 3:30am
    sched.add_job(
        lambda: _run_ai_enrich(),
        trigger='cron', hour=3, minute=30, timezone="America/Santiago", id="ai_enrich_daily"
    )

def _run_ai_enrich():
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        n = enrich_all_details(db, limit=20000)  # no force, respeta version
        print(f"[APScheduler] AI enrich OK. {n} filas.")
    finally:
        db.close()