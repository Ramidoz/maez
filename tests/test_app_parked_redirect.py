import os, re, unittest
import skills.web_interface as wi

# HAZARD: wi.UI_DIR is hardcoded to the MAIN checkout (/home/rohit/maez/ui), NOT this
# worktree. Read the WORKTREE's ui/ via a repo-relative path off wi.__file__ so the
# coverage test sees the files we actually edit on this branch.
_WT_UI = os.path.join(os.path.dirname(wi.__file__), "..", "ui")

# Every Task-0 'repoint' served UI file (the live daily-entry surfaces).
_REPOINTED_PAGES = (
    "index.html",
    "login.html",
    "progress_public.html",
    "progress_local.html",
    "analytics_local.html",
)


class AppParked(unittest.TestCase):
    def setUp(self):
        self.c = wi.app.test_client()

    def test_app_redirects_to_cockpit(self):
        r = self.c.get("/app", environ_base={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"].rstrip("/"), "/cockpit")

    def test_app_trailing_slash_redirects(self):
        r = self.c.get("/app/", environ_base={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"].rstrip("/"), "/cockpit")

    def test_app_with_test_t_still_redirects_never_serves_old_ui(self):
        # THE half-park guard: the test_t bypass must NOT serve app.html.
        r = self.c.get("/app?test_t=anything", environ_base={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"].rstrip("/"), "/cockpit")
        # No app.html body served — only Flask's redirect stub. Pin on app.html's actual
        # <title> marker (a bare <html tag is present in every Flask 302 "Redirecting..." stub,
        # so it cannot distinguish a redirect from a served page).
        self.assertNotIn(b"the one that began with you", r.data)   # app.html <title> not served


class NoLiveAppEntry(unittest.TestCase):
    def test_nav_tuple_app_channel_removed(self):
        with open(wi.__file__, encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn('("/app", "Channel")', src)
        self.assertNotIn("('/app', 'Channel')", src)

    def test_served_entry_pages_have_no_app_daily_link(self):
        # The live-served entry surfaces (Task-0 'repoint' set) must not point users at /app.
        # Read the WORKTREE files (NOT wi.UI_DIR, which is the main checkout).
        for page in _REPOINTED_PAGES:
            with open(os.path.join(_WT_UI, page), encoding="utf-8") as fh:
                html = fh.read()
            # no href/window.location to "/app" as a daily entry (allow none)
            self.assertFalse(re.search(r'(href|location(\.href)?\s*=)\s*[\'"]/app[\'"/]', html),
                             f"{page} still emits a /app entry link")

    def test_app_html_retained(self):
        self.assertTrue(os.path.exists(os.path.join(_WT_UI, "app.html")))   # parked, not deleted
