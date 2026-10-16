"""Offline regressions for artwork layout, providers and partial regeneration."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from hsiyc_writer import art
from hsiyc_writer.art import remote, text, local


class ArtworkTests(unittest.TestCase):
    def setUp(self):
        self.article = {"meta": {"slug": "test"}, "title": {"cn": "摄影工作坊", "en": "Photography Workshop"},
                        "sections": [{"heading_cn": "学习"}]}

    def test_text_respects_width_height_and_line_count(self):
        for title in ("很长的中文标题" * 50, "InternationalYouthClub" * 20, "Long English title " * 50):
            font, rows, size = text.fit_size(title, 300, 3, start=78, minimum=18, max_height=80)
            self.assertLessEqual(len(rows), 3)
            self.assertLessEqual(len(rows) * size * 1.34, 80)
            self.assertTrue(all(font.getlength(row) <= 300 for row in rows))
            self.assertTrue(rows[-1].endswith("…"))

    def test_partial_poster_matches_full_kit(self):
        with tempfile.TemporaryDirectory() as tmp:
            art.make_art(self.article, tmp, backend="local", seed=7)
            before = (Path(tmp) / "poster.png").read_bytes()
            result = art.make_art(self.article, tmp, backend="local", seed=7, kinds=("poster",))
            self.assertEqual(before, (Path(tmp) / "poster.png").read_bytes())
            # Name the kit rather than counting it: one section plus the three wide
            # and square assets, so adding an asset kind is a deliberate edit here.
            self.assertEqual(sorted(a["kind"] for a in result["assets"]),
                             ["banner", "cover", "divider", "poster", "social"])
            self.article["sections"] = []
            result = art.make_art(self.article, tmp, backend="local", kinds=("dividers",))
            self.assertFalse(any(a["kind"] == "divider" for a in result["assets"]))

    def test_provider_seed_prompt_and_partial_provenance(self):
        calls = []
        def generated(prompt, width, height, **kwargs):
            calls.append((prompt, kwargs["seed"]))
            return dict(image=Image.new("RGB", (40, 60)), model="test", seed=kwargs["seed"],
                        prompt=prompt, url="https://example.test/image", cached=False, backend="remote:custom")
        with tempfile.TemporaryDirectory() as tmp, patch.object(remote, "generate", side_effect=generated), \
                patch.object(local, "strip_vendor_marks", side_effect=AssertionError("custom image cropped")):
            result = art.make_art(self.article, tmp, seed=7, kinds=("poster", "social"))
            self.assertEqual(result["backend"], "remote:custom")
            self.assertIn("portrait", calls[0][0])
            self.assertIn("square", calls[1][0])
            art.make_art(self.article, tmp, seed=8, kinds=("poster",))
            self.assertNotEqual(calls[0][1], calls[2][1])
            result = art.make_art(self.article, tmp, backend="local", kinds=("poster",))
            self.assertEqual(result["backend"], "mixed")

    def test_provider_outage_only_attempted_once_per_kit(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(remote, "generate", side_effect=remote.RemoteArtError("offline")) as generate:
            result = art.make_art(self.article, tmp)
            self.assertEqual(generate.call_count, 1)
            self.assertEqual(result["backend"], "local")

    def test_cache_isolated_by_provider(self):
        with patch.dict(os.environ, {"HSIYC_ART_ENDPOINT": "https://a.test/images"}):
            first = remote._cache_paths("same", 100, 100, "model", 7)
        with patch.dict(os.environ, {"HSIYC_ART_ENDPOINT": "https://b.test/images"}):
            self.assertNotEqual(first, remote._cache_paths("same", 100, 100, "model", 7))

    def test_browser_lists_artwork_downloads(self):
        from hsiyc_writer import web
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            bundle = root / "event"
            (bundle / "art").mkdir(parents=True)
            (bundle / "art" / "poster.png").write_bytes(b"png")
            (bundle / "event.md").write_text("article")
            (bundle / "run_log.json").write_text("{}")
            handler = object.__new__(web.Handler)
            replies = []
            handler._json = lambda code, body: replies.append((code, body))
            from urllib.parse import urlencode
            with patch.object(web, "OUTPUT_DIR", root):
                handler._list_files(urlencode({"dir": str(bundle)}))
                self.assertEqual(replies[-1][0], 200)
                self.assertIn("event/art/poster.png", replies[-1][1]["files"])
                self.assertNotIn("event/run_log.json", replies[-1][1]["files"])
                handler._list_files(urlencode({"dir": str(root.parent)}))
                self.assertEqual(replies[-1][0], 403)

    def test_custom_response_validation_and_download_headers(self):
        def response(data, content_type="application/json"):
            stream = io.BytesIO(json.dumps(data).encode())
            stream.headers = {"Content-Type": content_type}
            return stream
        for payload in ({"data": ["invalid"]}, {"data": [{"b64_json": "%%%"}]}, {"data": [{"url": "file:///secret"}]}):
            with patch.object(remote.urllib.request, "urlopen", return_value=response(payload)):
                with self.assertRaises(remote.RemoteArtError):
                    remote._fetch_custom("prompt", 100, 100, "model", 7, "https://api.test/images", "secret", 10)
        with patch.object(remote.urllib.request, "urlopen", side_effect=[
                response({"data": [{"url": "https://storage.test/image"}]}), io.BytesIO(b"image")]) as fetch:
            remote._fetch_custom("prompt", 100, 100, "model", 7, "https://api.test/images", "secret", 10)
            self.assertEqual(fetch.call_args_list[0].args[0].get_header("Authorization"), "Bearer secret")
            self.assertIsNone(fetch.call_args_list[1].args[0].get_header("Authorization"))
        with patch.object(remote.urllib.request, "urlopen", side_effect=[
                response({"data": [{"url": "https://storage.test/image"}]}), TimeoutError("timeout")]):
            with self.assertRaises(remote.RemoteArtError):
                remote._fetch_custom("prompt", 100, 100, "model", 7, "https://api.test/images", "secret", 10)


if __name__ == "__main__":
    unittest.main()
