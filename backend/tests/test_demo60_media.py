"""Isolated adapter tests. No network, cloud write, real users or provider calls."""
import base64
from hashlib import sha256
from io import BytesIO
import json
import socket
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from uuid import uuid4

from PIL import Image
from backend.src.media import souvenir as media
from backend.src.media import storage
from backend.src.social.core import SocialError


def image(color="red", fmt="PNG"):
    buffer = BytesIO()
    Image.new("RGB", (16, 16), color).save(buffer, format=fmt)
    return buffer.getvalue()


def generated(data, mime="image/png"):
    return {"candidates": [{"finishReason": "STOP", "content": {"parts": [
        {"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode()}}
    ]}}]}


class SouvenirTests(unittest.TestCase):
    def setUp(self):
        self.context = {"place_name": "Test context only", "place_id": "test-only", "era_id": "ERA_CONTEMPORARY"}
        self.args = {"evidence_images": [image()], "portrait": None, "place_context": self.context, "timeout_s": 10}

    def test_output_is_new_decodable_image_one_call(self):
        result = image("blue")
        with patch.dict("os.environ", {"GEMINI_IMAGE_MODEL": "explicit-test-model"}), patch.object(media, "gemini_request", return_value=generated(result)) as call:
            self.assertEqual(media.generate_souvenir(**self.args), (result, "image/png"))
        call.assert_called_once()
        self.assertEqual(call.call_args.kwargs["model"], "explicit-test-model")

    def test_portrait_is_separate_input_and_arbitrary_context_ignored(self):
        self.args["portrait"] = image("green")
        self.args["place_context"]["prompt"] = "TEST MUST NOT BE INCLUDED"
        with patch.object(media, "gemini_request", return_value=generated(image("blue"))) as call:
            media.generate_souvenir(**self.args)
        body = call.call_args.kwargs["body"]
        self.assertEqual(len(body["contents"][0]["parts"]), 3)
        self.assertNotIn("TEST MUST NOT BE INCLUDED", json.dumps(body))
        self.assertIn("refuse", body["contents"][0]["parts"][0]["text"])

    def test_refusal_text_missing_image_corruption_and_echo_fail(self):
        for response in ({"promptFeedback": {"blockReason": "SAFETY"}}, {},
                         {"candidates": [{"content": {"parts": [{"text": "no image"}]}}]},
                         generated(b"bad bytes"), generated(image(), "image/jpeg"), generated(image()),
                         {"candidates": [{"finishReason": "SAFETY", "content": {"parts": []}}]}):
            with self.subTest(response_type=list(response)), patch.object(media, "gemini_request", return_value=response) as call:
                with self.assertRaises(media.MediaProviderError) as error:
                    media.generate_souvenir(**self.args)
                self.assertEqual(error.exception.code, "provider_failed")
                call.assert_called_once()

    def test_malformed_provider_shapes_are_safe_errors(self):
        for response in ({"candidates": [None]}, {"candidates": [{"content": None}]},
                         {"candidates": [{"content": {"parts": [None]}}]},
                         {"promptFeedback": []}):
            with self.subTest(shape=str(type(response))), patch.object(media, "gemini_request", return_value=response):
                with self.assertRaises(media.MediaProviderError):
                    media.generate_souvenir(**self.args)

    def test_input_size_and_decode_fail_before_provider(self):
        for data in (b"", b"invalid", b"x" * (media.MAX_BYTES + 1)):
            with self.subTest(size=len(data)), patch.object(media, "gemini_request") as call:
                with self.assertRaises(media.MediaProviderError):
                    media.generate_souvenir(**{**self.args, "evidence_images": [data]})
                call.assert_not_called()

    def test_rest_http_error_timeout_no_retry_and_no_secret_in_error(self):
        failures = [HTTPError("https://not-logged.invalid", 429, "SECRET-test", {}, None), socket.timeout("SECRET-test")]
        for failure in failures:
            with self.subTest(type=type(failure).__name__), patch.dict("os.environ", {"GEMINI_API_KEY": "SECRET-test"}), patch.object(media.urllib.request, "build_opener") as opener:
                opener.return_value.open.side_effect = failure
                with self.assertRaises(media.MediaProviderError) as error:
                    media.gemini_request(model="explicit-test", body={}, timeout_s=1)
                self.assertNotIn("SECRET", str(error.exception))
                self.assertEqual(error.exception.code, "provider_failed" if isinstance(failure, HTTPError) else "deadline_exceeded")
                opener.return_value.open.assert_called_once()

    def test_missing_key_or_model_never_calls_http(self):
        for model in ("", "https://invalid", "../invalid"):
            with patch.object(media.urllib.request, "build_opener") as opener:
                with self.assertRaises(media.MediaProviderError):
                    media.gemini_request(model=model, body={}, timeout_s=10)
                opener.assert_not_called()

    def test_timeout_is_bounded_and_finite(self):
        for timeout in (0, -1, 61, float('nan'), float('inf')):
            with patch.dict("os.environ", {"GEMINI_API_KEY": "test"}), patch.object(media.urllib.request, "build_opener") as opener:
                with self.assertRaises(media.MediaProviderError):
                    media.gemini_request(model="explicit-test", body={}, timeout_s=timeout)
                opener.assert_not_called()


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.asset = str(uuid4()), str(uuid4())
        self.data = image()
        self.path = f"discoveries/{self.actor}/{uuid4()}/{uuid4()}.png"
        self.record = {"owner_id": self.actor, "state": "attached", "object_path": self.path,
                       "mime_type": "image/png", "sha256": sha256(self.data).hexdigest()}

    def test_outsider_and_nonready_asset_never_read_storage(self):
        for record in (None, {**self.record, "owner_id": "other"}, {**self.record, "state": "deleted"}):
            with patch.object(storage, "get_db") as db, patch.object(storage, "get_storage_bucket") as bucket:
                db.return_value.collection.return_value.document.return_value.get.return_value.to_dict.return_value = record
                with self.assertRaises(SocialError) as error:
                    storage.load_owned_image(actor_id=self.actor, asset_id=self.asset)
                self.assertEqual(error.exception.status, 404)
                bucket.assert_not_called()

    def test_download_uses_generation_and_verifies_checksum(self):
        with patch.object(storage, "get_db") as db, patch.object(storage, "get_storage_bucket") as bucket:
            db.return_value.collection.return_value.document.return_value.get.return_value.to_dict.return_value = self.record
            blob = bucket.return_value.blob.return_value
            blob.size, blob.generation = len(self.data), 7
            blob.download_as_bytes.return_value = self.data
            self.assertEqual(storage.load_owned_image(actor_id=self.actor, asset_id=self.asset), self.data)
            blob.download_as_bytes.assert_called_once_with(if_generation_match=7, timeout=30, retry=None)
            blob.download_as_bytes.return_value = image("blue")
            with self.assertRaises(storage.MediaStorageError):
                storage.load_owned_image(actor_id=self.actor, asset_id=self.asset)

    def test_upload_is_private_create_only_no_db_reward_write(self):
        with patch.object(storage, "get_storage_bucket") as bucket, patch.object(storage, "get_db") as db:
            result = storage.put_private_image(object_path=self.path, image_bytes=self.data, mime_type="image/png")
            bucket.return_value.blob.return_value.upload_from_string.assert_called_once_with(self.data, content_type="image/png", if_generation_match=0, timeout=30, retry=None)
            self.assertEqual(result["sha256"], sha256(self.data).hexdigest())
            self.assertEqual((result["width"], result["height"]), (16, 16))
            db.assert_not_called()

    def test_invalid_path_mime_and_storage_fail_cleanly(self):
        for path in ("/tmp/file", "https://host/file", "discoveries/a/../b", "discoveries//x", "outside/file"):
            with patch.object(storage, "get_storage_bucket") as bucket:
                with self.assertRaises(storage.MediaStorageError):
                    storage.put_private_image(object_path=path, image_bytes=self.data, mime_type="image/png")
                bucket.assert_not_called()
        with patch.object(storage, "get_storage_bucket") as bucket:
            with self.assertRaises(media.MediaProviderError):
                storage.put_private_image(object_path=self.path, image_bytes=self.data, mime_type="image/jpeg")
            bucket.assert_not_called()
            bucket.return_value.blob.return_value.upload_from_string.side_effect = RuntimeError("SECRET-test")
            with self.assertRaises(storage.MediaStorageError) as error:
                storage.put_private_image(object_path=self.path, image_bytes=self.data, mime_type="image/png")
            self.assertNotIn("SECRET", str(error.exception))


if __name__ == '__main__':
    unittest.main()
