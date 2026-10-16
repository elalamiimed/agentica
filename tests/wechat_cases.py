"""The 公众号 draft route: it must be correct before it is ever pointed at WeChat.

Nothing here touches the network. The client takes a transport, and these cases pass a fake
one that records every call and returns canned WeChat responses - so the token caching, the
image-size guard, the draft payload limits and the failure messages are all testable
without the club's AppSecret, and without creating anything in their account.

    <python> tests/wechat_cases.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hsiyc_writer import render, wechat  # noqa: E402

SLOT = render.PASTE_SLOT_LABEL

ARTICLE = {
    "meta": {"doc_type": "回顾", "slug": "wechat-case"},
    "title": {"cn": "国际青年俱乐部 | 回顾：冬季羽毛球友谊赛圆满收官", "en": "Winter Badminton Friendly"},
    "lead": {"cn": "2026年12月20日，冬季羽毛球友谊赛在体育馆举行，24 名国际学生参赛，约 40 名观众到场助威。",
             "en": "On 20 December the friendly took place."},
    "sections": [
        {"number": "01", "heading_cn": "赛场之上", "heading_en": "On Court",
         "body": [
             {"kind": "bilingual", "cn": "比赛采用双打赛制。", "en": "Played in doubles."},
             {"kind": "photo_grid", "layout": "1x1",
              "photos": [{"file": "shot-01.jpg", "alt": "court",
                          "caption_cn": "决赛现场", "caption_en": "the final"}]},
         ]},
        {"number": "02", "heading_cn": "获奖名单", "heading_en": "Award Winners",
         "body": [{"kind": "photo_grid", "layout": "1x1",
                   "photos": [{"file": "shot-02.jpg", "alt": "team", "caption_cn": "合影"}]}]},
    ],
    "closing": {"heading_cn": "结语", "heading_en": "Closing", "cn": "感谢每一位参赛者。", "en": "Thank you."},
    "signoff": {"cn": "哈工大（深圳）国际青年俱乐部", "en": "HITSZ International Youth Club"},
    "credits": {"文字": "Yalalt", "图片": "Ferraa Ahmed", "排版": "Najmia Popal",
                "一审": "Samin", "二审": "周宣彤", "三审": "卢锦章"},
    "toc": {}, "facts": [], "needs_editor": [],
}

failures: list[str] = []


def check(condition: bool, label: str) -> None:
    if not condition:
        failures.append(label)


class FakeTransport:
    """Stands in for WeChat: records calls, returns canned responses."""

    def __init__(self, errors: dict | None = None) -> None:
        self.calls: list[tuple[str, str, object]] = []
        self.errors = errors or {}
        self.token_calls = 0

    def get_json(self, url: str) -> dict:
        self.calls.append(("GET", url, None))
        if url.endswith("/cgi-bin/token?grant_type=client_credential&appid=wx-test&secret=s3cret"):
            self.token_calls += 1
            return {"access_token": f"TOKEN{self.token_calls}", "expires_in": 7200}
        return {"errcode": 40013, "errmsg": "invalid appid"}

    def post_json(self, url: str, payload: dict) -> dict:
        self.calls.append(("POST-JSON", url, payload))
        return {"media_id": "DRAFT_MEDIA_ID"}

    def post_file(self, url: str, content: bytes, filename: str, field_name: str = "media") -> dict:
        self.calls.append(("POST-FILE", url, (filename, len(content), content[:4])))
        if "/media/uploadimg" in url:
            return {"url": f"https://mmbiz.qpic.cn/{filename}", "errcode": 0}
        return {"media_id": f"COVER_{filename}", "url": "https://mmbiz.qpic.cn/cover"}


def make_bundle(root: Path, with_photos: bool = True, cover: bool = True) -> Path:
    bundle = root / "wechat-case"
    (bundle / "media").mkdir(parents=True, exist_ok=True)
    (bundle / "art").mkdir(parents=True, exist_ok=True)
    (bundle / "wechat-case.json").write_text(json.dumps(ARTICLE, ensure_ascii=False), encoding="utf-8")
    if with_photos:
        for name in ("shot-01.jpg", "shot-02.jpg"):
            (bundle / "media" / name).write_bytes(tiny_jpeg())
    if cover:
        (bundle / "art" / "cover.png").write_bytes(tiny_png())
    return bundle


def tiny_jpeg(color: tuple[int, int, int] = (120, 40, 90)) -> bytes:
    """A real JPEG, so the size guard is tested against something WeChat would accept."""
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (320, 240), color).save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def tiny_png() -> bytes:
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (900, 383), (27, 56, 112)).save(buffer, format="PNG")
    return buffer.getvalue()


def case_dry_run_never_sends() -> None:
    """The default must not touch the network or the club's account."""
    print("dry run")
    work = Path(tempfile.mkdtemp(prefix="hsiyc_wx_"))
    try:
        bundle = make_bundle(work)
        result = wechat.create_draft(bundle, wechat.WeChatSettings(), send=False)
        check(not result.sent, "a dry run must not report a sent draft")
        check(not result.draft_media_id, "a dry run must not create a draft")
        check(result.uploaded == [], "a dry run must not upload anything")
        entry = result.payload["articles"][0]
        check(entry["title"].startswith("国际青年俱乐部"), "the payload should carry the headline")
        check(SLOT in entry["content"],
              "a dry run leaves the photo slots in place, since nothing was uploaded")
        check(entry["article_type"] == "news", "the draft must be a news article")
        check((bundle / "wechat-draft.json").is_file(),
              "the payload must always be written into the bundle for inspection")
        saved = json.loads((bundle / "wechat-draft.json").read_text(encoding="utf-8"))
        check(saved["sent"] is False, "the saved record must say it was not sent")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def case_upload_and_payload() -> None:
    """A real send uploads every placed photo, then creates the draft with their URLs."""
    print("upload and create")
    work = Path(tempfile.mkdtemp(prefix="hsiyc_wx_"))
    try:
        bundle = make_bundle(work)
        transport = FakeTransport()
        settings = wechat.WeChatSettings(appid="wx-test", secret="s3cret")
        seen: list[str] = []
        result = wechat.create_draft(bundle, settings, send=True, transport=transport,
                                     progress=seen.append)

        check(result.sent and result.draft_media_id == "DRAFT_MEDIA_ID",
              "the draft media_id must come back")
        check([name for name, _ in result.uploaded] == ["shot-01.jpg", "shot-02.jpg"],
              f"both photos must be uploaded in reading order, got {result.uploaded}")
        check(result.cover_media_id.startswith("COVER_"),
              "the cover must be uploaded as a permanent material")

        kinds = [call[1] for call in transport.calls]
        check(sum(1 for u in kinds if "/media/uploadimg" in u) == 2, "two body images uploaded")
        check(sum(1 for u in kinds if "/material/add_material" in u) == 1, "one cover uploaded")
        check(sum(1 for u in kinds if "/draft/add" in u) == 1, "exactly one draft created")
        check(transport.token_calls == 1, f"the access_token must be cached, got {transport.token_calls} calls")

        entry = result.payload["articles"][0]
        check(SLOT not in entry["content"], "the body must have no leftover slot")
        check('src="https://mmbiz.qpic.cn/shot-01.jpg"' in entry["content"],
              "the photo URL must be in the body")
        check("决赛现场" in entry["content"], "the caption must survive into the body")
        check(entry["thumb_media_id"].startswith("COVER_"), "the draft must carry the cover media_id")
        check(entry["author"] == "Yalalt", "the author should be the 文字 credit")
        check(entry["need_open_comment"] == 0, "comments stay closed unless asked for")
        check(any("draft created" in line for line in seen), "progress should reach the caller")
        for blocked in ("class=", "<style", "<div", "flex", "grid"):
            check(blocked not in entry["content"], f"the body must not contain {blocked!r}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def case_limits() -> None:
    """WeChat's length limits are applied, not hoped for."""
    print("payload limits")
    long_title = {"title": {"cn": "标" * 60}, "credits": {}, "lead": {"cn": "文" * 200}}
    payload = wechat.build_draft_payload(long_title, "body")
    entry = payload["articles"][0]
    check(len(entry["title"]) == wechat.TITLE_MAX, "the title must be cut to 32 characters")
    check(len(entry["digest"]) <= wechat.DIGEST_MAX, "the digest must stay under 120 characters")
    check(not entry.get("thumb_media_id"), "no cover means no thumb_media_id key")
    check("author" not in entry, "no 文字 credit means no author key")

    author = wechat.build_draft_payload({"title": {"cn": "t"}, "credits": {"文字": "名" * 40}}, "b")
    check(len(author["articles"][0]["author"]) == wechat.AUTHOR_MAX, "the author must be cut to 16")

    huge = wechat.build_draft_payload({"title": {"cn": "t"}}, "x" * (wechat.CONTENT_MAX_BYTES + 10))
    check(bool(wechat.content_size_warning(huge)), "an oversized payload must warn")
    check(not wechat.content_size_warning(wechat.build_draft_payload({"title": {"cn": "t"}}, "small")),
          "a normal payload must not warn")

    # empty content must still produce a well-formed payload
    empty = wechat.build_draft_payload({}, "")
    check(empty["articles"][0]["title"] == "", "a missing title is empty, not a crash")
    check(empty["articles"][0]["digest"] == "", "a missing lead is empty, not a crash")


def case_errors_are_actionable() -> None:
    """A failure has to tell the operator what to fix, because the API is unforgiving."""
    print("error messages")
    class Failing(FakeTransport):
        def __init__(self, code: int, where: str) -> None:
            super().__init__()
            self.code = code
            self.where = where

        def get_json(self, url: str) -> dict:
            return {"errcode": self.code, "errmsg": "boom"}

        def post_file(self, url, content, filename, field_name="media"):
            return {"errcode": self.code, "errmsg": "boom"}

        def post_json(self, url, payload):
            return {"errcode": self.code, "errmsg": "boom"}

    client = wechat.WeChatClient(wechat.WeChatSettings(appid="a", secret="b"), Failing(40164, "token"))
    try:
        client.token()
        check(False, "an IP whitelist error must raise")
    except wechat.WeChatError as exc:
        check("IP 白名单" in str(exc), f"errcode 40164 must mention the IP whitelist, got {exc}")

    for code, needle in ((40013, "AppID"), (40125, "AppSecret"), (48001, "permission")):
        client = wechat.WeChatClient(wechat.WeChatSettings(appid="a", secret="b"),
                                     Failing(code, "token"))
        try:
            client.token()
            check(False, f"errcode {code} must raise")
        except wechat.WeChatError as exc:
            check(needle in str(exc), f"errcode {code} must mention {needle}, got {exc}")

    try:
        wechat.WeChatClient(wechat.WeChatSettings()).token()
        check(False, "an unconfigured client must refuse before any call")
    except wechat.WeChatError as exc:
        check("HSIYC_WECHAT_APPID" in str(exc), "the message must name the variables to set")

    # A bundle with no article at all.
    work = Path(tempfile.mkdtemp(prefix="hsiyc_wx_"))
    try:
        empty = work / "nothing"
        empty.mkdir()
        try:
            wechat.create_draft(empty, send=False)
            check(False, "a bundle with no article must fail")
        except wechat.WeChatError as exc:
            check("no article JSON" in str(exc), f"the message must say what is missing, got {exc}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def case_missing_photos_block_a_send() -> None:
    """WeChat filters external image URLs, so a missing photo must stop the send."""
    print("missing photos")
    work = Path(tempfile.mkdtemp(prefix="hsiyc_wx_"))
    try:
        bundle = make_bundle(work, with_photos=False)
        try:
            wechat.create_draft(bundle, wechat.WeChatSettings(appid="a", secret="b"), send=True,
                                transport=FakeTransport())
            check(False, "sending with a missing photo must stop")
        except wechat.WeChatError as exc:
            check("shot-01.jpg" in str(exc), f"the missing file must be named, got {exc}")
        # The dry run must still work: it is how the operator finds out.
        result = wechat.create_draft(bundle, wechat.WeChatSettings(), send=False)
        check(not result.sent, "a dry run must still succeed without the photos")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def case_image_size_guard() -> None:
    """media/uploadimg refuses anything over 1 MB, and phone photos are 4 MB."""
    print("image size")
    work = Path(tempfile.mkdtemp(prefix="hsiyc_wx_"))
    try:
        small = work / "small.png"
        small.write_bytes(tiny_png())
        raw, name = wechat.prepare_image(small)
        check(raw == small.read_bytes() and name == "small.png",
              "an already-small file must be passed through untouched")

        # A renamed or truncated file must be reported, not raised as a PIL traceback -
        # by then some photos are already in the club's account.
        broken = work / "broken.jpg"
        broken.write_bytes(b"this is not an image, it is a text file")
        try:
            wechat.prepare_image(broken)
            check(False, "a file that is not an image must be refused")
        except wechat.WeChatError as exc:
            check("not an image" in str(exc), f"the message must say so plainly, got {exc}")

        try:
            from PIL import Image
        except ImportError:  # pragma: no cover - Pillow ships with the runtime
            print("  (Pillow unavailable, skipping the resize case)")
            return
        big = work / "big.jpg"
        # Noise, not a flat colour: a solid image compresses to a few KB and would not
        # exercise the guard at all.
        noise = __import__("os").urandom(2400 * 1600 * 3)
        Image.frombytes("RGB", (2400, 1600), noise).save(big, quality=98)
        check(big.stat().st_size > wechat.IMAGE_MAX_BYTES,
              "the fixture must start over WeChat's limit")
        raw, name = wechat.prepare_image(big)
        check(len(raw) <= wechat.IMAGE_MAX_BYTES,
              f"the prepared image must fit in 1 MB, got {len(raw) / 1024:.0f} KB")
        check(name.endswith(".jpg"), f"an oversized image is re-encoded as jpg, got {name}")
        with Image.open(__import__("io").BytesIO(raw)) as check_image:
            check(max(check_image.size) <= wechat.IMAGE_MAX_PX,
                  f"the long edge must be capped at {wechat.IMAGE_MAX_PX}px")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def case_content_is_the_paste_export() -> None:
    """The draft body is the same markup the 秀米 export produces - one renderer."""
    print("one renderer")
    with_images = render.to_xiumi_html(ARTICLE, images={"shot-01.jpg": "https://mmbiz.qpic.cn/a"})
    check("<img" in with_images and "https://mmbiz.qpic.cn/a" in with_images,
          "a photo with a URL must render as an image")
    check(SLOT in with_images,
          "a photo without a URL keeps its slot even when another one has a URL")
    check(with_images.count(SLOT) == 1, "exactly the un-uploaded photo keeps a slot")
    for blocked in ("class=", "<style", "<div", "flex", "grid", "@media"):
        check(blocked not in with_images, f"the draft body must not contain {blocked!r}")

    slot_only = render.to_xiumi_html(ARTICLE)
    check(slot_only.count(SLOT) == 2, "with no URLs, every photo is a slot")


def case_credential_check() -> None:
    """`wechat --check` must distinguish the four ways the setup can be wrong."""
    print("credential check")
    unset = wechat.check_credentials(wechat.WeChatSettings(), probe_ip=False)
    check(not unset["ok"], "an unconfigured account cannot check out")
    check("HSIYC_WECHAT_APPID" in unset["error"], "the error must name the variables to set")

    good = wechat.check_credentials(wechat.WeChatSettings(appid="wx-test", secret="s3cret"),
                                    transport=FakeTransport(), probe_ip=False)
    check(good["ok"], f"a working setup must report ok, got {good}")
    check(good["token"].startswith("TOKEN") or "…" in good["token"],
          "the token must be reported in a masked form")

    for code, needle in ((40164, "IP 白名单"), (40013, "AppID"), (40125, "AppSecret"),
                         (48001, "permission"), (40243, "frozen"), (40001, "AppSecret"),
                         (50007, "account itself is frozen")):
        class Failing:
            def get_json(self, url):
                return {"errcode": code, "errmsg": "boom"}

        result = wechat.check_credentials(wechat.WeChatSettings(appid="wx-x", secret="s"),
                                          transport=Failing(), probe_ip=False)
        check(not result["ok"], f"errcode {code} must not report ok")
        check(needle in result["error"], f"errcode {code} must mention {needle}, got {result['error']}")

    # A frozen AppSecret is a security setting, not a broken setup: the message has to say
    # that 秀米's own sync is unaffected, or the club will think it has lost its workflow.
    class Frozen:
        def get_json(self, url):
            return {"errcode": 40243, "errmsg": "AppSecret已被冻结"}

    frozen = wechat.check_credentials(wechat.WeChatSettings(appid="wx-x", secret="s"),
                                      transport=Frozen(), probe_ip=False)
    check("秀米" in frozen["error"], "a frozen secret must say that 秀米 still works")
    check("unfrozen" in frozen["error"], "and that it can be unfrozen")

    # A network failure must come back as a message, not an exception.
    class Dead:
        def get_json(self, url):
            raise OSError("no route to host")

    result = wechat.check_credentials(wechat.WeChatSettings(appid="wx-x", secret="s"),
                                      transport=Dead(), probe_ip=False)
    check(not result["ok"] and "OSError" in result["error"],
          f"a dead network must be reported, got {result}")

    # The IP lookup is best-effort and must never raise.
    check(isinstance(wechat.public_ip(timeout=1), str), "public_ip must always return a string")


def main() -> int:
    case_dry_run_never_sends()
    case_upload_and_payload()
    case_limits()
    case_errors_are_actionable()
    case_missing_photos_block_a_send()
    case_image_size_guard()
    case_content_is_the_paste_export()
    case_credential_check()

    if failures:
        print(f"\nwechat_cases: {len(failures)} FAILURE(S)")
        for item in failures:
            print("  -", item)
        return 1
    print("\nwechat_cases: OK - the draft route is correct offline, and a dry run sends nothing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
