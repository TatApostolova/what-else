"""FastAPI app: full pages, plus HTML fragments that HTMX swaps into the page."""

from __future__ import annotations

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, func, select

from whatelse.config import PACKAGE_DIR, Settings, code_fingerprint, load_settings
from whatelse.db import make_engine
from whatelse.demo import REWORK_NOTE, ReplayLLM, seed_demo
from whatelse.llm import LLM, ClaudeCLI, LLMError, purge_log
from whatelse.models import Challenge, Event, GenerationRun, Idea
from whatelse.orchestrator import GenerateRefused, load_techniques, run_generate, run_rework, technique_label
from whatelse.service import (
    CHALLENGE_ACTIONS, IDEA_ACTIONS, ServiceError, add_own_idea, change_challenge_status, create_challenge,
    delete_challenge, edit_challenge, react,
)
from whatelse.summary import build_summary

TABS = ("explore", "library", "experiments", "summary")
CLOSED = ("achieved", "abandoned")
STATUS_ORDER = {"active": 0, "paused": 1, "achieved": 2, "abandoned": 2}
PANELS = ("save", "discard", "rework", "feedback", "progress", "complete")
EVENT_LABELS = {
    "idea_created": "Generated", "saved": "Saved", "discarded": "Discarded", "reworked": "Reworked",
    "feedback": "Feedback", "actioned": "Moved to Action", "progress": "Progress", "completed": "Finished",
}
VERDICT_LABELS = {"worked": "Worked", "partly": "Partly worked", "didnt_work": "Didn't work", "dropped": "Dropped"}


def create_app(settings: Settings | None = None, llm: LLM | None = None) -> FastAPI:
    settings = settings or load_settings()
    engine = make_engine(settings)
    techniques = load_techniques(settings.techniques)
    if llm is None and settings.is_demo:
        llm = ReplayLLM.load({t.key: t.label for t in techniques})
    llm = llm or ClaudeCLI(
        model=settings.model, timeout=settings.timeout_seconds, log_path=settings.log_path, effort=settings.effort
    )
    if settings.is_demo:
        seed_demo(engine, settings, llm)  # every start is a fresh sample

    app = FastAPI(title="What Else?", docs_url=None, redoc_url=None)
    app.state.fingerprint = code_fingerprint()
    app.state.server = None  # set by __main__ so a newer launch can stop a stale copy
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
    tag_labels = {t["key"]: t["label"] for t in settings.save_tags + settings.discard_tags}
    templates.env.globals.update(
        settings=settings,
        technique_label=lambda keys: technique_label(keys, techniques),
        tag_label=lambda key: tag_labels.get(key, key.replace("_", " ")),
        event_label=lambda type_: EVENT_LABELS.get(type_, type_.replace("_", " ").capitalize()),
        verdicts=VERDICT_LABELS,
        rework_note=REWORK_NOTE,
    )
    templates.env.filters["when"] = lambda dt: dt.astimezone().strftime("%d %b %Y, %H:%M") if dt else ""

    def render(request: Request, name: str, status_code: int = 200, **ctx) -> HTMLResponse:
        return templates.TemplateResponse(request, name, ctx, status_code=status_code)

    def get_challenge(session: Session, challenge_id: int) -> Challenge:
        challenge = session.get(Challenge, challenge_id)
        if challenge is None:
            raise HTTPException(404, "Challenge not found")
        return challenge

    def ideas_with_status(session: Session, challenge_id: int, *statuses: str) -> list[Idea]:
        # Newest batch first; within a batch, the order the agents produced them.
        return list(session.exec(
            select(Idea)
            .where(Idea.challenge_id == challenge_id, Idea.status.in_(statuses))
            .order_by(Idea.run_id.desc(), Idea.id)
        ).all())

    def workspace_data(session: Session, challenge: Challenge) -> dict:
        explore = ideas_with_status(session, challenge.id, "generated")
        library = ideas_with_status(session, challenge.id, "saved")
        experiments = sorted(  # running first, then finished; newest activity first within each
            ideas_with_status(session, challenge.id, "actioned", "completed"),
            key=lambda i: (i.status == "completed", -i.updated_at.timestamp()),
        )
        events: dict[int, list[Event]] = {}
        for event in session.exec(
            select(Event).where(Event.challenge_id == challenge.id, Event.idea_id.is_not(None)).order_by(Event.id)
        ):
            events.setdefault(event.idea_id, []).append(event)
        titles = dict(session.exec(select(Idea.id, Idea.title).where(Idea.challenge_id == challenge.id)).all())
        return {
            "challenge": challenge,
            "summary": build_summary(session, challenge.id) if challenge.status in CLOSED else None,
            "events": events,
            "titles": titles,
            "explore": explore,
            "library": library,
            "experiments": experiments,
            "counts": {"explore": len(explore), "library": len(library), "experiments": len(experiments)},
        }

    @app.get("/_version", response_class=PlainTextResponse)
    def version():
        return app.state.fingerprint

    @app.post("/_shutdown", response_class=PlainTextResponse)
    def shutdown(token: str = Form("")):
        """Lets a newer launch replace this copy. Needs this copy's fingerprint as the token."""
        if settings.is_demo or token != app.state.fingerprint or app.state.server is None:
            raise HTTPException(403)
        with Session(engine) as session:
            if session.exec(select(GenerationRun).where(GenerationRun.status == "running")).first():
                raise HTTPException(409, "The agents are working; try again when they finish.")
        app.state.server.should_exit = True
        return "stopping"

    @app.post("/demo/reset")
    def demo_reset():
        """Demo only: throw away everyone's changes and rebuild the sample challenge."""
        if not settings.is_demo:
            raise HTTPException(404)
        challenge_id = seed_demo(engine, settings, llm)
        return RedirectResponse(f"/challenges/{challenge_id}", status_code=303)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        with Session(engine) as session:
            if not session.exec(select(func.count()).select_from(Challenge)).one():
                return render(request, "welcome.html")
            challenges = sorted(
                session.exec(select(Challenge)).all(),
                key=lambda c: (STATUS_ORDER.get(c.status, 3), -c.updated_at.timestamp()),
            )
            stats: dict[int, dict[str, int]] = {}
            for cid, status in session.exec(select(Idea.challenge_id, Idea.status)):
                s = stats.setdefault(cid, {"ideas": 0, "saved": 0, "experiments": 0})
                s["ideas"] += 1
                s["saved"] += status == "saved"
                s["experiments"] += status in ("actioned", "completed")
            return render(request, "dashboard.html", challenges=challenges, stats=stats)

    @app.get("/challenges/new", response_class=HTMLResponse)
    def new_challenge(request: Request):
        if settings.is_demo:
            return render(request, "demo_new.html")
        return render(request, "challenge_form.html", statement="", context="", error=None)

    @app.post("/challenges")
    def create(request: Request, statement: str = Form(""), context: str = Form("")):
        if settings.is_demo:
            return RedirectResponse("/challenges/new", status_code=303)
        with Session(engine) as session:
            try:
                challenge = create_challenge(session, statement, context)
            except ServiceError as exc:
                return render(request, "challenge_form.html", 400, statement=statement, context=context, error=str(exc))
            return RedirectResponse(f"/challenges/{challenge.id}", status_code=303)

    @app.get("/challenges/{challenge_id}", response_class=HTMLResponse)
    def workspace(request: Request, challenge_id: int, tab: str | None = None):
        with Session(engine) as session:
            challenge = get_challenge(session, challenge_id)
            closed = challenge.status in CLOSED
            if tab not in TABS or (tab == "summary" and not closed):
                tab = "summary" if closed else "explore"
            data = workspace_data(session, challenge)
            return render(request, "workspace.html", tab=tab, **data)

    @app.post("/challenges/{challenge_id}/edit")
    def edit(challenge_id: int, statement: str = Form(""), context: str = Form("")):
        with Session(engine) as session:
            get_challenge(session, challenge_id)
            try:
                edit_challenge(session, challenge_id, statement, context)
            except ServiceError:
                pass  # an empty statement simply isn't saved
        return RedirectResponse(f"/challenges/{challenge_id}", status_code=303)

    @app.post("/challenges/{challenge_id}/status")
    def status(challenge_id: int, action: str = Form(""), note: str = Form("")):
        if action not in CHALLENGE_ACTIONS:
            raise HTTPException(400, "Unknown action")
        with Session(engine) as session:
            get_challenge(session, challenge_id)
            try:
                challenge = change_challenge_status(session, challenge_id, action, note)
            except ServiceError:
                return RedirectResponse(f"/challenges/{challenge_id}", status_code=303)
            tab = "summary" if challenge.status in CLOSED else "explore"
        return RedirectResponse(f"/challenges/{challenge_id}?tab={tab}", status_code=303)

    @app.post("/challenges/{challenge_id}/delete")
    def delete(challenge_id: int, confirm: str = Form("")):
        if confirm != "yes":
            raise HTTPException(400, "Deletion must be confirmed")
        with Session(engine) as session:
            get_challenge(session, challenge_id)
            if session.exec(select(GenerationRun).where(
                GenerationRun.challenge_id == challenge_id, GenerationRun.status == "running")).first():
                return RedirectResponse(f"/challenges/{challenge_id}", status_code=303)
            statements = delete_challenge(session, challenge_id)
        purge_log(settings.log_path, statements)
        return RedirectResponse("/", status_code=303)

    @app.post("/challenges/{challenge_id}/ideas", response_class=HTMLResponse)
    def own_idea(request: Request, challenge_id: int, title: str = Form(""), text: str = Form("")):
        error = None
        with Session(engine) as session:
            get_challenge(session, challenge_id)
            try:
                add_own_idea(session, challenge_id, title, text)
            except ServiceError as exc:
                error = str(exc)
            data = workspace_data(session, get_challenge(session, challenge_id))
            return render(request, "_tabs.html", tab="library", error=error, **data)

    @app.post("/challenges/{challenge_id}/generate", response_class=HTMLResponse)
    def generate(request: Request, challenge_id: int):
        error = None
        try:
            run_generate(engine, challenge_id, llm, settings)
        except (GenerateRefused, ServiceError) as exc:
            error = str(exc)
        except LLMError as exc:
            error = exc.user_message
        with Session(engine) as session:
            data = workspace_data(session, get_challenge(session, challenge_id))
            return render(request, "_tabs.html", tab="explore", error=error, **data)

    @app.get("/ideas/{idea_id}/panel/{action}", response_class=HTMLResponse)
    def feedback_panel(request: Request, idea_id: int, action: str, tab: str = "explore"):
        if action not in PANELS:
            raise HTTPException(404)
        with Session(engine) as session:
            idea = session.get(Idea, idea_id)
            if idea is None:
                raise HTTPException(404)
            tags = {"save": settings.save_tags, "discard": settings.discard_tags}.get(action, [])
            return render(request, "_feedback_panel.html", idea=idea, action=action, tags=tags,
                          tab=tab if tab in TABS else "explore")

    @app.post("/ideas/{idea_id}/rework", response_class=HTMLResponse)
    def rework(request: Request, idea_id: int, note: str = Form(""), tab: str = Form("explore")):
        error = None
        try:
            run_rework(engine, idea_id, note, llm, settings)
        except (ServiceError, GenerateRefused) as exc:
            error = str(exc)
        except LLMError as exc:
            error = exc.user_message
        with Session(engine) as session:
            idea = session.get(Idea, idea_id)
            if idea is None:
                raise HTTPException(404)
            data = workspace_data(session, get_challenge(session, idea.challenge_id))
            return render(request, "_tabs.html", tab=tab if tab in TABS else "explore", error=error, **data)

    @app.post("/ideas/{idea_id}/{action}", response_class=HTMLResponse)
    def idea_reaction(request: Request, idea_id: int, action: str,
                      tags: list[str] = Form(default_factory=list), note: str = Form(""),
                      verdict: str = Form(""), tab: str = Form("explore")):
        if action not in IDEA_ACTIONS:
            raise HTTPException(404)
        error = None
        with Session(engine) as session:
            idea = session.get(Idea, idea_id)
            if idea is None:
                raise HTTPException(404)
            try:
                react(session, settings, idea_id, action, tags, note, verdict or None)
            except ServiceError as exc:
                error = str(exc)
            data = workspace_data(session, get_challenge(session, idea.challenge_id))
            return render(request, "_tabs.html", tab=tab if tab in TABS else "explore", error=error, **data)

    return app
