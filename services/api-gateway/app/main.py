from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text, create_engine, func, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None


logger = logging.getLogger("eventops")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

REQUEST_COUNT = Counter(
    "eventops_http_requests_total",
    "Total HTTP requests handled by EventOps.",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "eventops_http_request_duration_seconds",
    "HTTP request duration in seconds for EventOps.",
    ["method", "path"],
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EVENTOPS_", extra="ignore")

    database_url: str = "sqlite:///./data/eventops.db"
    storage_root: Path = Path("data/storage")
    seed_sample_data: bool = False
    notification_mode: str = "record"
    notification_target: str = "safety-ops"
    api_token: str = ""


class Base(DeclarativeBase):
    pass


class VideoSource(Base):
    __tablename__ = "video_sources"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(20))
    source_name: Mapped[str] = mapped_column(String(255))
    source_uri: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: utcnow())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class InferenceJob(Base):
    __tablename__ = "inference_jobs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(40))
    model_name: Mapped[str] = mapped_column(String(255))
    model_version: Mapped[str] = mapped_column(String(80))
    backend_type: Mapped[str] = mapped_column(String(80))
    threshold: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(30))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: utcnow())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RawDetection(Base):
    __tablename__ = "raw_detections"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[str] = mapped_column(String(40))
    event_id: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(80))
    confidence: Mapped[float] = mapped_column(Float)
    frame_uri: Mapped[str] = mapped_column(Text)
    bbox_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    track_id: Mapped[str] = mapped_column(String(80))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: utcnow())


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(40))
    job_id: Mapped[str] = mapped_column(String(40))
    event_type: Mapped[str] = mapped_column(String(80))
    start_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: utcnow())
    end_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: utcnow())
    confidence: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(20))
    location_label: Mapped[str] = mapped_column(String(120), default="zone-a")
    status: Mapped[str] = mapped_column(String(20), default="new")
    operator_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: utcnow())


class EventEvidence(Base):
    __tablename__ = "event_evidence"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(40))
    frame_uri: Mapped[str] = mapped_column(Text)
    clip_uri: Mapped[str] = mapped_column(Text)
    bbox_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    track_id: Mapped[str] = mapped_column(String(80))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: utcnow())


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    source_uri: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(80), default="v1")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: utcnow())


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(40))
    document_title: Mapped[str] = mapped_column(String(255))
    chunk_text: Mapped[str] = mapped_column(Text)
    embedding_ref: Mapped[str] = mapped_column(String(255), default="lexical")
    page_no: Mapped[int] = mapped_column(Integer, default=1)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON)

class AgentReport(Base):
    __tablename__ = "agent_reports"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(20))
    risk_reason: Mapped[str] = mapped_column(Text)
    recommended_actions_json: Mapped[list[str]] = mapped_column(JSON)
    policy_refs_json: Mapped[list[str]] = mapped_column(JSON)
    model_name: Mapped[str] = mapped_column(String(255))
    prompt_version: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: utcnow())


class AgentTrace(Base):
    __tablename__ = "agent_traces"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(40))
    state_graph_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    tool_calls_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    token_usage_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: utcnow())


class OperatorQuery(Base):
    __tablename__ = "operator_queries"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    event_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    user_text: Mapped[str] = mapped_column(Text)
    answer_text: Mapped[str] = mapped_column(Text)
    citations_json: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: utcnow())


class NotificationRecord(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(40))
    channel_type: Mapped[str] = mapped_column(String(40))
    recipient: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(40))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: utcnow())


class RtspSourceCreate(BaseModel):
    source_name: str
    source_uri: str


class InferenceJobCreate(BaseModel):
    source_id: str
    model_name: str
    model_version: str
    backend_type: str
    threshold: float = 0.5


class ReportGenerateRequest(BaseModel):
    event_id: str


class QARequest(BaseModel):
    event_id: str | None = None
    question: str


class EventReviewUpdate(BaseModel):
    status: str | None = None
    operator_feedback: str | None = None


EVENT_KEYWORDS = {
    "fall": "fall",
    "fire": "fire",
    "intrusion": "intrusion",
    "trespass": "intrusion",
    "dump": "illegal_dumping",
}

FALLBACK_ACTIONS = {
    "fall": [
        "Call the on-site safety manager.",
        "Dispatch the nearest responder to verify the subject condition.",
        "Preserve the evidence clip and frame for review.",
    ],
    "fire": [
        "Trigger the fire escalation protocol.",
        "Dispatch the nearest responder.",
        "Preserve the evidence clip for review.",
    ],
    "intrusion": [
        "Notify the security lead.",
        "Verify the subject location.",
        "Preserve the evidence clip for review.",
    ],
    "illegal_dumping": [
        "Notify the facility operator.",
        "Review the evidence clip.",
    ],
    "anomaly": ["Review the evidence clip and classify the event."],
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def sanitize_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", name.strip())
    return cleaned or "uploaded.bin"


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def chunk_text(text: str, chunk_size: int = 90, overlap: int = 20) -> list[str]:
    words = text.split()
    if not words:
        return []
    stride = max(1, chunk_size - overlap)
    chunks: list[str] = []
    for start in range(0, len(words), stride):
        chunk = " ".join(words[start : start + chunk_size]).strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(words):
            break
    return chunks


def read_upload_text(filename: str, raw_bytes: bytes) -> str:
    suffix = Path(filename or "uploaded.bin").suffix.lower()
    if suffix == ".pdf":
        if PdfReader is None:
            raise HTTPException(status_code=400, detail="PDF support is not installed.")
        reader = PdfReader(BytesIO(raw_bytes))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        return "\n".join(page for page in pages if page)
    return raw_bytes.decode("utf-8", errors="ignore")


def build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def ensure_schema_compatibility(engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "inference_jobs" in table_names:
        columns = {column["name"] for column in inspector.get_columns("inference_jobs")}
        if "threshold" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE inference_jobs ADD COLUMN threshold FLOAT DEFAULT 0.5"))


def ensure_storage_dirs(storage_root: Path) -> None:
    for child in (storage_root, storage_root / "sources", storage_root / "documents"):
        child.mkdir(parents=True, exist_ok=True)


def save_bytes(root: Path, folder: str, entity_id: str, filename: str, content: bytes) -> str:
    safe_name = sanitize_name(filename)
    destination = root / folder / entity_id / safe_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return str(destination)


def infer_event_type(source_name: str) -> str:
    lowered = source_name.lower()
    for keyword, event_type in EVENT_KEYWORDS.items():
        if keyword in lowered:
            return event_type
    return "anomaly"


def infer_risk_level(event_type: str, has_evidence: bool = True) -> str:
    if not has_evidence:
        return "medium"
    if event_type in {"fall", "fire", "intrusion"}:
        return "high"
    if event_type == "illegal_dumping":
        return "medium"
    return "low"


def parse_datetime_filter(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid datetime filter: {value}") from exc

def parse_actions(text: str) -> list[str]:
    actions: list[str] = []
    for line in text.splitlines():
        cleaned = line.strip()
        if re.match(r"^[-*]\s+", cleaned):
            actions.append(re.sub(r"^[-*]\s+", "", cleaned))
        elif re.match(r"^\d+\.\s+", cleaned):
            actions.append(re.sub(r"^\d+\.\s+", "", cleaned))
    return actions[:3]



def normalize_action_line(line: str) -> str:
    cleaned = re.sub(r"^[-*]\s+", "", line.strip())
    cleaned = re.sub(r"^\d+\.\s+", "", cleaned)
    return cleaned.replace("`", "").strip()


def extract_grounded_actions(text: str) -> list[str]:
    section_keywords = ("action", "response", "escalation", "next step", "protocol", "조치", "대응")
    prioritized: list[str] = []
    fallback: list[str] = []
    in_action_section = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        heading = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading:
            heading_text = heading.group(1).lower()
            in_action_section = any(keyword in heading_text for keyword in section_keywords)
            continue

        if not re.match(r"^(?:[-*]\s+|\d+\.\s+)", line):
            continue

        action = normalize_action_line(line)
        if not action:
            continue

        fallback.append(action)
        if in_action_section:
            prioritized.append(action)

    selected = prioritized or fallback
    deduped: list[str] = []
    for action in selected:
        if action not in deduped:
            deduped.append(action)
    return deduped[:3]


def extract_grounded_actions_from_chunks(session: Session, chunks: list[DocumentChunk]) -> list[str]:
    document_ids = list(dict.fromkeys(chunk.document_id for chunk in chunks))
    actions: list[str] = []

    for document_id in document_ids:
        document = session.get(Document, document_id)
        if document is None:
            continue
        source_path = Path(document.source_uri)
        if not source_path.exists():
            continue
        raw_text = read_upload_text(source_path.name, source_path.read_bytes())
        for action in extract_grounded_actions(raw_text):
            if action not in actions:
                actions.append(action)
            if len(actions) == 3:
                return actions

    return actions
def search_chunks(session: Session, query: str, limit: int = 3) -> list[DocumentChunk]:
    chunks = session.execute(select(DocumentChunk)).scalars().all()
    query_tokens = tokenize(query)
    scored: list[tuple[int, DocumentChunk]] = []
    for chunk in chunks:
        score = len(query_tokens & tokenize(chunk.chunk_text))
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda item: (-item[0], item[1].page_no, item[1].id))
    return [chunk for _, chunk in scored[:limit]]


def get_latest_report(session: Session, event_id: str) -> AgentReport | None:
    return session.execute(
        select(AgentReport).where(AgentReport.event_id == event_id).order_by(AgentReport.created_at.desc())
    ).scalars().first()


def get_latest_trace(session: Session, event_id: str) -> AgentTrace | None:
    return session.execute(
        select(AgentTrace).where(AgentTrace.event_id == event_id).order_by(AgentTrace.created_at.desc())
    ).scalars().first()


def get_evidence(session: Session, event_id: str) -> list[EventEvidence]:
    return session.execute(
        select(EventEvidence).where(EventEvidence.event_id == event_id).order_by(EventEvidence.timestamp.asc())
    ).scalars().all()


def get_notifications(session: Session, event_id: str) -> list[NotificationRecord]:
    return session.execute(
        select(NotificationRecord).where(NotificationRecord.event_id == event_id).order_by(NotificationRecord.sent_at.desc())
    ).scalars().all()


def get_raw_detections(session: Session, event_id: str) -> list[RawDetection]:
    return session.execute(
        select(RawDetection).where(RawDetection.event_id == event_id).order_by(RawDetection.detected_at.asc())
    ).scalars().all()


def get_queries(session: Session, event_id: str) -> list[OperatorQuery]:
    return session.execute(
        select(OperatorQuery).where(OperatorQuery.event_id == event_id).order_by(OperatorQuery.created_at.desc())
    ).scalars().all()


def list_sources(session: Session) -> list[VideoSource]:
    return session.execute(select(VideoSource).order_by(VideoSource.created_at.desc())).scalars().all()


def list_documents(session: Session) -> list[Document]:
    return session.execute(select(Document).order_by(Document.uploaded_at.desc())).scalars().all()


def serialize_source(source: VideoSource) -> dict[str, Any]:
    return {
        "source_id": source.id,
        "source_type": source.source_type,
        "source_name": source.source_name,
        "source_uri": source.source_uri,
        "is_active": source.is_active,
        "created_at": source.created_at.isoformat(),
    }


def serialize_job(job: InferenceJob) -> dict[str, Any]:
    return {
        "job_id": job.id,
        "source_id": job.source_id,
        "model_name": job.model_name,
        "model_version": job.model_version,
        "backend_type": job.backend_type,
        "threshold": job.threshold,
        "status": job.status,
        "started_at": job.started_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


def serialize_document(document: Document) -> dict[str, Any]:
    return {
        "document_id": document.id,
        "title": document.title,
        "source_uri": document.source_uri,
        "version": document.version,
        "uploaded_at": document.uploaded_at.isoformat(),
    }


def serialize_event_summary(event: Event) -> dict[str, Any]:
    return {
        "event_id": event.id,
        "source_id": event.source_id,
        "job_id": event.job_id,
        "event_type": event.event_type,
        "risk_level": event.risk_level,
        "confidence": event.confidence,
        "status": event.status,
        "location_label": event.location_label,
        "operator_feedback": event.operator_feedback,
        "created_at": event.created_at.isoformat(),
    }


def serialize_report(report: AgentReport | None) -> dict[str, Any] | None:
    if report is None:
        return None
    return {
        "report_id": report.id,
        "summary": report.summary,
        "risk_level": report.risk_level,
        "risk_reason": report.risk_reason,
        "recommended_actions": report.recommended_actions_json,
        "policy_refs": report.policy_refs_json,
        "model_name": report.model_name,
        "prompt_version": report.prompt_version,
        "created_at": report.created_at.isoformat(),
    }


def serialize_trace(trace: AgentTrace | None) -> dict[str, Any]:
    if trace is None:
        return {"states": [], "tool_calls": [], "token_usage": {}, "latency_ms": 0}
    return {
        "trace_id": trace.id,
        "states": trace.state_graph_json.get("states", []),
        "tool_calls": trace.tool_calls_json,
        "token_usage": trace.token_usage_json,
        "latency_ms": trace.latency_ms,
        "created_at": trace.created_at.isoformat(),
    }


def serialize_detail(session: Session, event: Event) -> dict[str, Any]:
    evidence = get_evidence(session, event.id)
    raw_detections = get_raw_detections(session, event.id)
    report = get_latest_report(session, event.id)
    trace = get_latest_trace(session, event.id)
    notifications = get_notifications(session, event.id)
    queries = get_queries(session, event.id)
    return {
        **serialize_event_summary(event),
        "evidence": [
            {
                "evidence_id": item.id,
                "frame_uri": item.frame_uri,
                "clip_uri": item.clip_uri,
                "bbox": item.bbox_json,
                "track_id": item.track_id,
                "timestamp": item.timestamp.isoformat(),
            }
            for item in evidence
        ],
        "raw_detections": [
            {
                "detection_id": item.id,
                "label": item.label,
                "confidence": item.confidence,
                "frame_uri": item.frame_uri,
                "bbox": item.bbox_json,
                "track_id": item.track_id,
                "detected_at": item.detected_at.isoformat(),
            }
            for item in raw_detections
        ],
        "report": serialize_report(report),
        "trace": serialize_trace(trace),
        "notifications": [
            {
                "notification_id": item.id,
                "channel_type": item.channel_type,
                "recipient": item.recipient,
                "status": item.status,
                "sent_at": item.sent_at.isoformat(),
            }
            for item in notifications
        ],
        "queries": [
            {
                "query_id": item.id,
                "question": item.user_text,
                "answer": item.answer_text,
                "citations": item.citations_json,
                "created_at": item.created_at.isoformat(),
            }
            for item in queries
        ],
    }


def build_metrics(session: Session) -> dict[str, int]:
    return {
        "sources_total": session.scalar(select(func.count()).select_from(VideoSource)) or 0,
        "jobs_total": session.scalar(select(func.count()).select_from(InferenceJob)) or 0,
        "events_total": session.scalar(select(func.count()).select_from(Event)) or 0,
        "raw_detections_total": session.scalar(select(func.count()).select_from(RawDetection)) or 0,
        "reports_total": session.scalar(select(func.count()).select_from(AgentReport)) or 0,
        "documents_total": session.scalar(select(func.count()).select_from(Document)) or 0,
        "notifications_total": session.scalar(select(func.count()).select_from(NotificationRecord)) or 0,
        "queries_total": session.scalar(select(func.count()).select_from(OperatorQuery)) or 0,
        "high_risk_events": session.scalar(
            select(func.count()).select_from(Event).where(Event.risk_level == "high")
        ) or 0,
    }


def ensure_sample_document(session: Session, settings: Settings) -> None:
    if not settings.seed_sample_data:
        return
    has_documents = session.scalar(select(func.count()).select_from(Document)) or 0
    if has_documents:
        return
    repo_root = Path(__file__).resolve().parents[3]
    sample_path = repo_root / "datasets" / "documents" / "sample_safety_sop.md"
    if not sample_path.exists():
        return
    raw_bytes = sample_path.read_bytes()
    create_document(session, settings, title="SOP-12", filename=sample_path.name, raw_bytes=raw_bytes, version="v1")
    session.commit()


def load_golden_cases() -> list[dict[str, Any]]:
    repo_root = Path(__file__).resolve().parents[3]
    golden_path = repo_root / "libs" / "eval" / "golden_cases.json"
    if not golden_path.exists():
        return []
    return json.loads(golden_path.read_text(encoding="utf-8"))


def create_document(
    session: Session,
    settings: Settings,
    title: str,
    filename: str,
    raw_bytes: bytes,
    version: str,
) -> tuple[Document, int]:
    text = read_upload_text(filename, raw_bytes)
    if not text.strip():
        raise HTTPException(status_code=400, detail="Document contains no indexable text.")
    document_id = new_id("doc")
    source_uri = save_bytes(settings.storage_root, "documents", document_id, filename, raw_bytes)
    document = Document(id=document_id, title=title or Path(filename).stem, source_uri=source_uri, version=version)
    session.add(document)
    chunks = chunk_text(text)
    if not chunks:
        chunks = [text.strip()]
    for index, chunk in enumerate(chunks, start=1):
        session.add(
            DocumentChunk(
                id=new_id("chunk"),
                document_id=document_id,
                document_title=document.title,
                chunk_text=chunk,
                embedding_ref="lexical",
                page_no=index,
                metadata_json={"chunk_index": index},
            )
        )
    session.flush()
    return document, len(chunks)

def create_source_file(session: Session, settings: Settings, source_name: str, upload: UploadFile) -> VideoSource:
    source_id = new_id("src")
    raw_bytes = upload.file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    source_uri = save_bytes(settings.storage_root, "sources", source_id, upload.filename or "source.bin", raw_bytes)
    source = VideoSource(
        id=source_id,
        source_type="file",
        source_name=source_name,
        source_uri=source_uri,
        is_active=True,
    )
    session.add(source)
    session.flush()
    return source


def create_rtsp_source(session: Session, payload: RtspSourceCreate) -> VideoSource:
    source = VideoSource(
        id=new_id("src"),
        source_type="rtsp",
        source_name=payload.source_name,
        source_uri=payload.source_uri,
        is_active=True,
    )
    session.add(source)
    session.flush()
    return source


def create_inference_job(session: Session, payload: InferenceJobCreate) -> tuple[InferenceJob, Event]:
    source = session.get(VideoSource, payload.source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    job = InferenceJob(
        id=new_id("job"),
        source_id=payload.source_id,
        model_name=payload.model_name,
        model_version=payload.model_version,
        backend_type=payload.backend_type,
        threshold=payload.threshold,
        status="completed",
        started_at=utcnow(),
        completed_at=utcnow(),
    )
    session.add(job)
    event_type = infer_event_type(f"{source.source_name} {Path(source.source_uri).name}")
    risk_level = infer_risk_level(event_type, has_evidence=True)
    confidence = 0.93 if risk_level == "high" else 0.72
    event = Event(
        id=new_id("evt"),
        source_id=source.id,
        job_id=job.id,
        event_type=event_type,
        start_ts=utcnow(),
        end_ts=utcnow(),
        confidence=confidence,
        risk_level=risk_level,
        location_label="zone-a",
        status="new",
    )
    session.add(event)
    session.flush()
    session.add(
        RawDetection(
            id=new_id("det"),
            job_id=job.id,
            source_id=source.id,
            event_id=event.id,
            label=event_type,
            confidence=confidence,
            frame_uri=source.source_uri,
            bbox_json={"x": 0.12, "y": 0.18, "w": 0.42, "h": 0.33},
            track_id="track-1",
            detected_at=utcnow(),
        )
    )
    session.add(
        EventEvidence(
            id=new_id("evi"),
            event_id=event.id,
            frame_uri=source.source_uri,
            clip_uri=source.source_uri,
            bbox_json={"x": 0.12, "y": 0.18, "w": 0.42, "h": 0.33},
            track_id="track-1",
            timestamp=utcnow(),
        )
    )
    session.flush()
    return job, event


def build_report(session: Session, settings: Settings, event_id: str) -> tuple[AgentReport, AgentTrace]:
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    evidence = get_evidence(session, event.id)
    chunks = search_chunks(session, f"{event.event_type} risk response safety actions", limit=3)
    citations = list(dict.fromkeys(chunk.document_title for chunk in chunks))
    citation_text = "\n".join(chunk.chunk_text for chunk in chunks)
    actions = extract_grounded_actions_from_chunks(session, chunks) or parse_actions(citation_text) or FALLBACK_ACTIONS.get(event.event_type, FALLBACK_ACTIONS["anomaly"])
    risk_level = infer_risk_level(event.event_type, has_evidence=bool(evidence))
    if citations:
        policy_text = f"{citations[0]} requires a structured response."
    else:
        policy_text = "No policy citation was retrieved, so additional confirmation is required."
    summary = (
        f"{event.event_type.title()} event detected from source {event.source_id}. "
        f"Evidence is available and the operator should follow the cited response steps."
    )
    risk_reason = (
        f"This event is {risk_level} risk because evidence exists and {policy_text}"
        if evidence
        else "Evidence is limited, so additional confirmation is required before escalation."
    )
    report = AgentReport(
        id=new_id("rpt"),
        event_id=event.id,
        summary=summary,
        risk_level=risk_level,
        risk_reason=risk_reason,
        recommended_actions_json=actions,
        policy_refs_json=citations,
        model_name="heuristic-grounded-agent",
        prompt_version="report_system_v1",
    )
    trace = AgentTrace(
        id=new_id("trc"),
        event_id=event.id,
        state_graph_json={
            "states": [
                {"name": "LOAD_EVENT", "status": "completed"},
                {"name": "FETCH_EVIDENCE", "status": "completed"},
                {"name": "RETRIEVE_POLICY", "status": "completed" if citations else "skipped"},
                {"name": "ASSESS_RISK", "status": "completed"},
                {"name": "GENERATE_SUMMARY", "status": "completed"},
                {"name": "RECOMMEND_ACTION", "status": "completed"},
                {"name": "VALIDATE_GROUNDING", "status": "completed" if citations else "needs_review"},
                {"name": "NOTIFY", "status": "completed" if risk_level == "high" else "skipped"},
                {"name": "PERSIST_REPORT", "status": "completed"},
            ]
        },
        tool_calls_json=[
            {"tool": "event_store", "event_id": event.id},
            {"tool": "policy_search", "citations": citations},
        ],
        token_usage_json={"prompt_tokens": 0, "completion_tokens": 0, "mode": "heuristic"},
        latency_ms=120,
    )
    session.add(report)
    session.add(trace)
    session.flush()
    existing_notification = session.execute(
        select(NotificationRecord).where(NotificationRecord.event_id == event.id)
    ).scalars().first()
    if risk_level == "high" and existing_notification is None:
        session.add(
            NotificationRecord(
                id=new_id("ntf"),
                event_id=event.id,
                channel_type="operator_channel",
                recipient=settings.notification_target,
                status="recorded" if settings.notification_mode == "record" else "pending",
                sent_at=utcnow(),
            )
        )
    session.flush()
    return report, trace


def build_answer(session: Session, settings: Settings, payload: QARequest) -> tuple[str, list[str]]:
    question = payload.question.strip()
    lowered = question.lower()
    if payload.event_id is None:
        counts = session.execute(select(Event.event_type, func.count()).group_by(Event.event_type)).all()
        parts = [f"{event_type}: {count}" for event_type, count in counts]
        answer = "Recent event summary: " + (", ".join(parts) if parts else "No recent events are available.")
        citations: list[str] = []
        return answer, citations

    event = session.get(Event, payload.event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")

    report = get_latest_report(session, event.id)
    if report is None:
        report, _ = build_report(session, settings, event.id)
        session.flush()

    evidence = get_evidence(session, event.id)
    citations = list(report.policy_refs_json)
    if evidence:
        citations.append(evidence[0].frame_uri)

    recent_window = utcnow() - timedelta(days=7)
    similar_count = session.scalar(
        select(func.count()).select_from(Event).where(Event.event_type == event.event_type, Event.created_at >= recent_window)
    ) or 0

    primary_policy = report.policy_refs_json[0] if report.policy_refs_json else "policy unavailable"
    primary_action = report.recommended_actions_json[0] if report.recommended_actions_json else "Review the event evidence immediately."

    if "왜" in question or "이유" in question or "why" in lowered:
        answer = (
            f"This event is high risk because operator evidence exists and {primary_policy} requires an immediate response. "
            f"The grounded event type is {event.event_type}."
        )
    elif "조치" in question or "먼저" in question or "first" in lowered or "action" in lowered:
        answer = f"The first recommended action is '{primary_action}'. Grounding policy: {primary_policy}."
    elif "최근" in question or "유사" in question or "recent" in lowered or "similar" in lowered:
        answer = f"There have been {similar_count} recent {event.event_type} events in the last 7 days."
    else:
        answer = f"This is a {report.risk_level} risk event. Summary: {report.summary} Next action: {primary_action}."

    return answer, citations

def record_query(session: Session, event_id: str | None, question: str, answer: str, citations: list[str]) -> OperatorQuery:
    query = OperatorQuery(
        id=new_id("qry"),
        event_id=event_id,
        user_text=question,
        answer_text=answer,
        citations_json=citations,
    )
    session.add(query)
    session.flush()
    return query


def get_session(request: Request):
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def create_default_app(**overrides: Any) -> FastAPI:
    settings = Settings(**overrides)
    ensure_storage_dirs(settings.storage_root)
    engine = build_engine(settings.database_url)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    ensure_schema_compatibility(engine)
    with session_factory() as session:
        ensure_sample_document(session, settings)
    app = FastAPI(title="EventOps Agent Platform", version="0.2.0")
    app.state.settings = settings
    app.state.session_factory = session_factory
    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

    @app.middleware("http")
    async def auth_metrics_logging(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and settings.api_token:
            token = request.headers.get("x-api-token", "")
            if token != settings.api_token:
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            elapsed = time.perf_counter() - started
            route = request.scope.get("route")
            path_label = getattr(route, "path", path)
            REQUEST_COUNT.labels(request.method, path_label, str(status_code)).inc()
            REQUEST_LATENCY.labels(request.method, path_label).observe(elapsed)
            logger.info(json.dumps({"method": request.method, "path": path, "status_code": status_code, "elapsed_ms": round(elapsed * 1000, 2)}))
            raise

        elapsed = time.perf_counter() - started
        route = request.scope.get("route")
        path_label = getattr(route, "path", path)
        REQUEST_COUNT.labels(request.method, path_label, str(status_code)).inc()
        REQUEST_LATENCY.labels(request.method, path_label).observe(elapsed)
        logger.info(json.dumps({"method": request.method, "path": path, "status_code": status_code, "elapsed_ms": round(elapsed * 1000, 2)}))
        response.headers["X-Process-Time-Ms"] = f"{elapsed * 1000:.2f}"
        return response

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics")
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.post("/api/v1/sources/files", status_code=status.HTTP_201_CREATED)
    def upload_source_file(
        source_name: str = Form(...),
        file: UploadFile = File(...),
        session: Session = Depends(get_session),
    ) -> dict[str, str]:
        source = create_source_file(session, settings, source_name, file)
        session.commit()
        return {"source_id": source.id, "status": "uploaded"}

    @app.post("/api/v1/sources/rtsp", status_code=status.HTTP_201_CREATED)
    def register_rtsp_source(payload: RtspSourceCreate, session: Session = Depends(get_session)) -> dict[str, str]:
        source = create_rtsp_source(session, payload)
        session.commit()
        return {"source_id": source.id, "status": "registered"}

    @app.get("/api/v1/sources")
    def get_sources_api(session: Session = Depends(get_session)) -> dict[str, Any]:
        sources = list_sources(session)
        return {"items": [serialize_source(source) for source in sources], "total": len(sources)}

    @app.post("/api/v1/inference/jobs", status_code=status.HTTP_201_CREATED)
    def create_job(payload: InferenceJobCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
        job, event = create_inference_job(session, payload)
        session.commit()
        return {"job_id": job.id, "status": job.status, "event_ids": [event.id]}

    @app.get("/api/v1/inference/jobs/{job_id}")
    def get_job(job_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
        job = session.get(InferenceJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return serialize_job(job)

    @app.get("/api/v1/events")
    def list_events(
        event_type: str | None = Query(default=None),
        risk_level: str | None = Query(default=None),
        status_filter: str | None = Query(default=None, alias="status"),
        start_date: str | None = Query(default=None),
        end_date: str | None = Query(default=None),
        source_id: str | None = Query(default=None),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        stmt = select(Event).order_by(Event.created_at.desc())
        start_dt = parse_datetime_filter(start_date)
        end_dt = parse_datetime_filter(end_date)
        if event_type:
            stmt = stmt.where(Event.event_type == event_type)
        if risk_level:
            stmt = stmt.where(Event.risk_level == risk_level)
        if status_filter:
            stmt = stmt.where(Event.status == status_filter)
        if start_dt:
            stmt = stmt.where(Event.created_at >= start_dt)
        if end_dt:
            stmt = stmt.where(Event.created_at <= end_dt)
        if source_id:
            stmt = stmt.where(Event.source_id == source_id)
        events = session.execute(stmt).scalars().all()
        return {"items": [serialize_event_summary(event) for event in events], "total": len(events)}

    @app.patch("/api/v1/events/{event_id}")
    def update_event(event_id: str, payload: EventReviewUpdate, session: Session = Depends(get_session)) -> dict[str, Any]:
        event = session.get(Event, event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found.")
        if payload.status is not None:
            event.status = payload.status
        if payload.operator_feedback is not None:
            event.operator_feedback = payload.operator_feedback
        session.add(event)
        session.commit()
        return serialize_detail(session, event)

    @app.get("/api/v1/events/{event_id}")
    def get_event(event_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
        event = session.get(Event, event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found.")
        return serialize_detail(session, event)

    @app.post("/api/v1/documents", status_code=status.HTTP_201_CREATED)
    def upload_document(
        title: str = Form(...),
        version: str = Form("v1"),
        file: UploadFile = File(...),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        raw_bytes = file.file.read()
        document, chunk_count = create_document(
            session, settings, title=title, filename=file.filename or "document.txt", raw_bytes=raw_bytes, version=version
        )
        session.commit()
        return {"document_id": document.id, "status": "indexed", "chunk_count": chunk_count}

    @app.get("/api/v1/documents")
    def get_documents_api(session: Session = Depends(get_session)) -> dict[str, Any]:
        documents = list_documents(session)
        return {"items": [serialize_document(document) for document in documents], "total": len(documents)}

    @app.get("/api/v1/documents/search")
    def search_documents(
        q: str = Query(..., min_length=1),
        limit: int = Query(3, ge=1, le=10),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        chunks = search_chunks(session, q, limit=limit)
        return {
            "items": [
                {
                    "document_title": chunk.document_title,
                    "page_no": chunk.page_no,
                    "chunk_text": chunk.chunk_text,
                    "metadata": chunk.metadata_json,
                }
                for chunk in chunks
            ],
            "total": len(chunks),
        }

    @app.post("/api/v1/reports/generate", status_code=status.HTTP_201_CREATED)
    def generate_report(payload: ReportGenerateRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
        report, _trace = build_report(session, settings, payload.event_id)
        session.commit()
        return serialize_report(report)

    @app.post("/api/v1/qa")
    def answer_question(payload: QARequest, session: Session = Depends(get_session)) -> dict[str, Any]:
        answer, citations = build_answer(session, settings, payload)
        record_query(session, payload.event_id, payload.question, answer, citations)
        session.commit()
        return {"answer": answer, "citations": citations}

    @app.get("/api/v1/metrics/summary")
    def metrics_summary(session: Session = Depends(get_session)) -> dict[str, int]:
        return build_metrics(session)

    @app.get("/api/v1/evaluations/golden")
    def evaluate_golden_cases(session: Session = Depends(get_session)) -> dict[str, Any]:
        from app.services.evaluation import evaluate_answer

        results: list[dict[str, Any]] = []
        for case in load_golden_cases():
            event = session.execute(
                select(Event).where(Event.event_type == case["event_type"]).order_by(Event.created_at.desc())
            ).scalars().first()
            if event is None:
                results.append({"name": case["name"], "score": 0.0, "status": "missing_event"})
                continue
            answer, citations = build_answer(session, settings, QARequest(event_id=event.id, question=case["question"]))
            score = evaluate_answer(answer, case["expected_terms"])
            results.append(
                {
                    "name": case["name"],
                    "status": "evaluated",
                    "score": score,
                    "citations": citations,
                    "answer": answer,
                }
            )
        average_score = sum(item["score"] for item in results) / len(results) if results else 0.0
        return {"cases": results, "average_score": average_score}

    @app.post("/ui/documents")
    def upload_document_ui(
        title: str = Form(...),
        version: str = Form("v1"),
        file: UploadFile = File(...),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        raw_bytes = file.file.read()
        create_document(session, settings, title=title, filename=file.filename or "document.txt", raw_bytes=raw_bytes, version=version)
        session.commit()
        return RedirectResponse(url="/", status_code=303)

    @app.post("/ui/sources/files")
    def upload_source_ui(
        source_name: str = Form(...),
        file: UploadFile = File(...),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        create_source_file(session, settings, source_name, file)
        session.commit()
        return RedirectResponse(url="/", status_code=303)

    @app.post("/ui/sources/rtsp")
    def upload_rtsp_ui(
        source_name: str = Form(...),
        source_uri: str = Form(...),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        create_rtsp_source(session, RtspSourceCreate(source_name=source_name, source_uri=source_uri))
        session.commit()
        return RedirectResponse(url="/", status_code=303)

    @app.post("/ui/inference/jobs")
    def run_inference_ui(
        source_id: str = Form(...),
        model_name: str = Form("demo-fall-detector"),
        model_version: str = Form("v1"),
        backend_type: str = Form("demo"),
        threshold: float = Form(0.5),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        _job, event = create_inference_job(
            session,
            InferenceJobCreate(
                source_id=source_id,
                model_name=model_name,
                model_version=model_version,
                backend_type=backend_type,
                threshold=threshold,
            ),
        )
        session.commit()
        return RedirectResponse(url=f"/events/{event.id}", status_code=303)

    @app.post("/ui/events/{event_id}/reports")
    def generate_report_ui(event_id: str, session: Session = Depends(get_session)) -> RedirectResponse:
        build_report(session, settings, event_id)
        session.commit()
        return RedirectResponse(url=f"/events/{event_id}", status_code=303)

    @app.post("/ui/events/{event_id}/review")
    def review_event_ui(
        event_id: str,
        status_value: str = Form(...),
        operator_feedback: str = Form(""),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        event = session.get(Event, event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found.")
        event.status = status_value
        event.operator_feedback = operator_feedback
        session.add(event)
        session.commit()
        return RedirectResponse(url=f"/events/{event_id}", status_code=303)

    @app.post("/ui/events/{event_id}/qa")
    def qa_ui(
        event_id: str,
        question: str = Form(...),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        answer, citations = build_answer(session, settings, QARequest(event_id=event_id, question=question))
        record_query(session, event_id, question, answer, citations)
        session.commit()
        return RedirectResponse(url=f"/events/{event_id}", status_code=303)

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
        events = session.execute(select(Event).order_by(Event.created_at.desc())).scalars().all()
        context = {
            "request": request,
            "events": [serialize_event_summary(event) for event in events],
            "metrics": build_metrics(session),
            "documents": [serialize_document(document) for document in list_documents(session)],
            "sources": [serialize_source(source) for source in list_sources(session)],
        }
        return templates.TemplateResponse(request, "dashboard.html", context)

    @app.get("/events/{event_id}", response_class=HTMLResponse)
    def event_detail_page(event_id: str, request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
        event = session.get(Event, event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found.")
        context = {"request": request, "event": serialize_detail(session, event)}
        return templates.TemplateResponse(request, "event_detail.html", context)

    return app





