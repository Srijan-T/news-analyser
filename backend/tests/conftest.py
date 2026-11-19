"""Keep tests hermetic: real environment variables always win over backend/.env, so pin the
ones that change app behaviour before any app code reads settings. This stops a developer's
local .env (e.g. NEWS_PROVIDER=gnews) from making tests call real APIs."""

import os

os.environ["NEWS_PROVIDER"] = "fake"
for name in ("GNEWS_API_KEY", "APP_PASSWORD", "SESSION_SECRET", "STATIC_DIR"):
    os.environ[name] = ""
