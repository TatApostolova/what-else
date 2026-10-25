"""FastAPI app: full pages, plus HTML fragments that HTMX swaps into the page."""

from __future__ import annotations

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, func, select

from whatelse.config import PACKAGE_DIR, Settings, load_settings
from whatelse.db import make_engine
from whatelse.llm import LLM, ClaudeCLI, LLMError
from whatelse.models import Challenge, Idea
from whatelse.orchestrator import GenerateRefused, load_techniques, run_generate, technique_label
from whatelse.service import ServiceError, create_challenge

TABS = ("explore", "library", "experiments")


def create_app(settings: Settings | None = None, llm: LLM | None = None) -> FastAPI:
    settings = settings or load_settings()
    engine = make_engine(settings)
    llm = llm or ClaudeCLI(
        model=settings.model, timeout=settings.timeout_seconds, log_path=settings.log_path, effort=settings.effort
    )
    techniques = load_techniques(settings.techniques)

    app = FastAPI(title="What Else?", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
    templates.env.globals.update(
        settings=settings,
        technique_label=lambda keys: technique_label(keys, techniques),
    )

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
        experiments = ideas_with_status(session, challenge.id, "actioned", "completed")
        return {
            "challenge": challenge,
            "explore": explore,
            "library": library,
            "experiments": experiments,
            "counts": {"explore": len(explore), "library": len(library), "experiments": len(experiments)},
        }

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        with Session(engine) as session:
            if not session.exec(select(func.count()).select_from(Challenge)).one():
                return render(request, "welcome.html")
            challenges = session.exec(select(Challenge).order_by(Challenge.updated_at.desc())).all()
            return render(request, "dashboard.html", challenges=challenges)

    @app.get("/challenges/new", response_class=HTMLResponse)
    def new_challenge(request: Request):
        return render(request, "challenge_form.html", statement="", context="", error=None)

    @app.post("/challenges")
    def create(request: Request, statement: str = Form(""), context: str = Form("")):
        with Session(engine) as session:
            try:
                challenge = create_challenge(session, statement, context)
            except ServiceError as exc:
                return render(request, "challenge_form.html", 400, statement=statement, context=context, error=str(exc))
            return RedirectResponse(f"/challenges/{challenge.id}", status_code=303)

    @app.get("/challenges/{challenge_id}", response_class=HTMLResponse)
    def workspace(request: Request, challenge_id: int, tab: str = "explore"):
        tab = tab if tab in TABS else "explore"
        with Session(engine) as session:
            data = workspace_data(session, get_challenge(session, challenge_id))
            return render(request, "workspace.html", tab=tab, **data)

    @app.post("/challenges/{challenge_id}/generate", response_class=HTMLResponse)
    def generate(request: Request, challenge_id: int):
        error = None
        try:
            run_generate(engine, challenge_id, llm, settings)
        except GenerateRefused as exc:
            error = str(exc)
        except LLMError as exc:
            error = exc.user_message
        with Session(engine) as session:
            data = workspace_data(session, get_challenge(session, challenge_id))
            return render(request, "_tabs.html", tab="explore", error=error, **data)

    return app
