"""Firebase Admin SDK initialization — singleton per process."""
import os
import threading

import firebase_admin
from firebase_admin import credentials, firestore, storage
from google.auth.credentials import AnonymousCredentials
from google.cloud.storage import Client as StorageClient

_lock = threading.Lock()
_initialized = False


class EmulatorCredentials(credentials.Base):
    def get_credential(self):
        return AnonymousCredentials()


def _init():
    global _initialized
    if _initialized:
        return
    with _lock:
        if _initialized:
            return
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        project = os.getenv("FIREBASE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        storage_bucket = os.getenv("STORAGE_BUCKET")
        if not project:
            raise RuntimeError("Set FIREBASE_PROJECT_ID or GOOGLE_CLOUD_PROJECT")

        emulated = any(os.getenv(host) for host in (
            "FIRESTORE_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST", "FIREBASE_STORAGE_EMULATOR_HOST",
        ))
        if emulated and (os.getenv("ENV") not in {"development", "test"} or not project.startswith("demo-")):
            raise RuntimeError("Firebase emulators require a demo project in development or test")

        if not firebase_admin._apps:
            options = {"projectId": project}
            if storage_bucket:
                options["storageBucket"] = storage_bucket
            if emulated:
                firebase_admin.initialize_app(EmulatorCredentials(), options)
            elif cred_path:
                if not os.path.isfile(cred_path):
                    raise FileNotFoundError(f"Firebase credentials not found: {cred_path}")
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred, options)
            else:
                # Emulator or Application Default Credentials
                firebase_admin.initialize_app(options=options)
        _initialized = True


def get_db() -> firestore.client:
    """Return a Firestore client, initializing Firebase first."""
    _init()
    return firestore.client()


def get_storage_bucket():
    """Return the Cloud Storage bucket, initializing Firebase first."""
    _init()
    emulator = os.getenv("FIREBASE_STORAGE_EMULATOR_HOST")
    if emulator:
        app = firebase_admin.get_app()
        client = StorageClient(project=app.project_id, credentials=AnonymousCredentials(),
                               client_options={"api_endpoint": f"http://{emulator}"})
        return client.bucket(app.options.get("storageBucket") or f"{app.project_id}.appspot.com")
    return storage.bucket()
