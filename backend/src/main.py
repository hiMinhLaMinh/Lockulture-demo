import os
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .social.core import SocialError
from .social.fixtures import load_fixture_services
from .social.http import router


def create_app(*, social=None):
    fixtures = os.getenv("LOCKULTURE_SOCIAL_FIXTURES") == "1"
    environment = os.getenv("ENV", "production")
    if (fixtures or social is not None) and environment not in {"development", "test"}:
        raise RuntimeError("Social fixtures require ENV=development or ENV=test")

    app = FastAPI(title="Lockulture Backend")
    app.state.social = social if social is not None else load_fixture_services() if fixtures else None
    if environment in {"development", "test"} and app.state.social:
        app.add_middleware(
            CORSMiddleware, allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        )

    @app.get("/health", include_in_schema=False)
    def legacy_health():
        return {"status": "HEALTHY", "service": "lockulture-backend"}

    def envelope(status, code, message):
        return JSONResponse(status_code=status, content={"error": {
            "code": code, "message": message, "retryable": status == 503,
            "request_id": str(uuid4()),
        }})

    @app.exception_handler(SocialError)
    def social_error(_: Request, error: SocialError):
        return envelope(error.status, error.code, error.message)

    @app.exception_handler(RequestValidationError)
    def validation_error(_: Request, error: RequestValidationError):
        field = ".".join(map(str, error.errors()[0]["loc"]))
        return envelope(422, "validation_error", f"Invalid request field: {field}")

    @app.exception_handler(Exception)
    def internal_error(_: Request, error: Exception):
        return envelope(500, "internal_error", "Internal server error")

    app.include_router(router)
    return app


app = create_app()
