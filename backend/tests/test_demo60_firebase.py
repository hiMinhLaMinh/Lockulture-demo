"""Preflight/startup checks: no cloud requests, no credentials or users created."""
import importlib.util
import os
from pathlib import Path
import sys
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4
import unittest
from unittest.mock import Mock, patch

from backend.src.media.config import live_errors

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("demo_common_test", ROOT / "scripts/demo/common.py")
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)


class CloudGuardTests(unittest.TestCase):
    def config(self):
        return {key: 'test-only' for key in (
            'FIREBASE_PROJECT_ID', 'STORAGE_BUCKET', 'GEMINI_API_KEY', 'GOOGLE_MAPS_API_KEY',
            'GEMINI_MODEL', 'GEMINI_IMAGE_MODEL', 'TASK_QUEUE_PATH', 'TASK_SERVICE_ACCOUNT',
            'SCHEDULER_SERVICE_ACCOUNT', 'INTERNAL_AUDIENCE')} | {'STORAGE_TYPE': 'firebase', 'ASSESSMENT_PROVIDER': 'gemini'}

    def test_explicit_cloud_config_passes_without_network(self):
        with patch.dict(os.environ, self.config(), clear=True):
            self.assertEqual(live_errors(), [])
            self.assertEqual(common.cloud_errors(), [])

    def test_local_emulator_fixture_and_missing_credential_rejected(self):
        for extra in ({'STORAGE_TYPE':'local'}, {'FIRESTORE_EMULATOR_HOST':'localhost:8081'},
                      {'FIREBASE_AUTH_EMULATOR_HOST':'localhost:9099'}, {'LOCKULTURE_SOCIAL_FIXTURES':'1'},
                      {'ASSESSMENT_PROVIDER':'fixture'}, {'GOOGLE_APPLICATION_CREDENTIALS':'/does-not-exist/credential'}):
            with self.subTest(config=list(extra)), patch.dict(os.environ, self.config() | extra, clear=True):
                self.assertTrue(live_errors())
                self.assertTrue(common.cloud_errors())

    def test_missing_models_are_not_guessed(self):
        with patch.dict(os.environ, self.config(), clear=True):
            os.environ.pop('GEMINI_IMAGE_MODEL')
            self.assertIn('Missing GEMINI_IMAGE_MODEL', live_errors())

    def test_missing_config_reports_names_not_secret_values(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY':'SECRET-test'}, clear=True):
            self.assertTrue(live_errors())
            self.assertNotIn('SECRET-test', str(live_errors()))

    def test_state_file_and_restart_required(self):
        spec = importlib.util.spec_from_file_location('smoke_firebase_test', ROOT / 'scripts/smoke/smoke_firebase.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.dict(os.environ, {'SMOKE_STATE_FILE': str(ROOT / 'state.json')}, clear=True):
            with self.assertRaisesRegex(Exception, 'outside'):
                module.state_path()
            with self.assertRaisesRegex(Exception, 'SMOKE_BACKEND_PID'):
                module.marker()

    def test_expired_signed_url_must_be_denied_then_refreshed(self):
        spec = importlib.util.spec_from_file_location('smoke_expiry_test', ROOT / 'scripts/smoke/smoke_firebase.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        from backend.src.media import storage
        asset_id, owner = str(uuid4()), str(uuid4())
        data = b'isolated test only'
        checksum = sha256(data).hexdigest()
        now = datetime.now(timezone.utc)
        dto = {'url':'https://storage.googleapis.com/test-only/object', 'expires_at':(now+timedelta(seconds=60)).isoformat()}
        for denied in (True, False):
            with self.subTest(expired_denied=denied), patch.dict(os.environ, {'STORAGE_BUCKET':'test-only'}, clear=True), patch('backend.src.firebase.get_db') as db, patch.object(storage, 'load_owned_image', return_value=data), patch.object(module, 'api', return_value=(200,dto)), patch.object(module, 'http') as http, patch.object(module, 'datetime', wraps=datetime) as clock, patch.object(module, 'emit'):
                db.return_value.collection.return_value.document.return_value.get.return_value.to_dict.return_value = {'owner_id':owner, 'sha256':checksum, 'byte_size':len(data)}
                clock.now.side_effect = [now, now+timedelta(seconds=62)]
                http.side_effect = [(200,data), module.SmokeError('HTTP 403') if denied else (200,data), (200,data)]
                if denied:
                    self.assertEqual(module.verify_asset(asset_id, owner, check_expiry=True)['sha256'], checksum)
                    self.assertEqual(http.call_count, 3)
                else:
                    with self.assertRaisesRegex(module.SmokeError, 'still allowed'):
                        module.verify_asset(asset_id, owner, check_expiry=True)


if __name__ == '__main__':
    unittest.main()
