import os
from uuid import UUID, uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .social.core import SocialError, require
from .social.fixtures import FixtureUrls, load_fixture_services
from .social.http import router
from .firestore_repo import load_firebase_social_services
from .platform_routes import router as platform_router
from .assets_routes import router as assets_router
from .worker.http import router as worker_router


def create_app(*, social=None):
    fixtures = os.getenv("LOCKULTURE_SOCIAL_FIXTURES") == "1"
    fixture_services = social is not None or fixtures
    environment = os.getenv("ENV", "production")
    if (fixtures or social is not None) and environment not in {"development", "test"}:
        raise RuntimeError("Social fixtures require ENV=development or ENV=test")

    app = FastAPI(title="Lockulture Backend")
    app.state.social = (
        social if social is not None else
        load_fixture_services() if fixtures else
        load_firebase_social_services()
    )
    if environment in {"development", "test"}:
        app.add_middleware(
            CORSMiddleware, allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        )

    @app.get("/health", include_in_schema=False)
    def legacy_health():
        return {"status": "HEALTHY", "service": "lockulture-backend"}

    def envelope(status, code, message, retry_after=None):
        return JSONResponse(status_code=status, headers={"Retry-After": str(retry_after)} if retry_after else None, content={"error": {
            "code": code, "message": message, "retryable": status in (429, 503) or retry_after is not None,
            "request_id": str(uuid4()),
        }})

    @app.exception_handler(SocialError)
    def social_error(_: Request, error: SocialError):
        return envelope(error.status, error.code, error.message, error.retry_after)

    @app.exception_handler(RequestValidationError)
    def validation_error(_: Request, error: RequestValidationError):
        field = ".".join(map(str, error.errors()[0]["loc"]))
        return envelope(422, "validation_error", f"Invalid request field: {field}")

    @app.exception_handler(Exception)
    def internal_error(_: Request, error: Exception):
        return envelope(500, "internal_error", "Internal server error")

    if app.state.social and isinstance(app.state.social.urls, FixtureUrls):
        @app.get("/_dev/social-assets/{asset_id}", include_in_schema=False)
        def fixture_image(asset_id: UUID, expires: int, signature: str):
            services = app.state.social
            require(services.urls.valid(str(asset_id), expires, signature, services.clock()),
                    404, "Asset not found")
            return Response(services.urls.image, media_type="image/svg+xml",
                            headers={"Cache-Control": "no-store"})

    if fixture_services:
        app.include_router(router)
        app.include_router(platform_router)
        app.include_router(assets_router)
    else:
        app.include_router(assets_router)
        app.include_router(platform_router)
        app.include_router(router)
    app.include_router(worker_router)
    return app


app = create_app()
