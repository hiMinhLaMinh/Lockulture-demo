"""Firebase Admin SDK initialization — singleton per process."""
import os
import threading
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore, storage

_lock = threading.Lock()
_initialized = False


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

        if not firebase_admin._apps:
            options = {"projectId": project}
            if storage_bucket:
                options["storageBucket"] = storage_bucket
            if cred_path:
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
    return storage.bucket()
