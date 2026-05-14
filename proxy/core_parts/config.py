import logging
import os
from pathlib import Path

logger = logging.getLogger("hermes_lmstudio_proxy")

DEFAULT_LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://192.168.1.146:1235")
DEFAULT_INTERCEPT_MODE = os.getenv("PROXY_INTERCEPT_MODE", "true").lower() not in {
    "0",
    "false",
    "no",
    "off",
}
DEFAULT_HOST = os.getenv("PROXY_HOST", "0.0.0.0")
DEFAULT_PORT = int(os.getenv("PROXY_PORT", "1234"))
UPSTREAM_TIMEOUT_SECONDS = float(os.getenv("PROXY_UPSTREAM_TIMEOUT", "300"))
UPSTREAM_CONNECT_TIMEOUT_SECONDS = float(os.getenv("PROXY_UPSTREAM_CONNECT_TIMEOUT", "30"))
DEFAULT_LARGE_TEXT_BUFFER_CHARS = 500 * 1024 * 1024
MAX_TOOL_CALL_BUFFER = int(
    os.getenv("PROXY_MAX_TOOL_CALL_BUFFER", str(DEFAULT_LARGE_TEXT_BUFFER_CHARS))
)
DEFAULT_PROXY_MODE = os.getenv("PROXY_MODE", "orchestrator").strip().lower()
PROXY_RESUME_FORMAT = os.getenv("PROXY_RESUME_FORMAT", "auto").strip().lower()
XML_TOOL_RESPONSE_ROLE = os.getenv("PROXY_XML_TOOL_RESPONSE_ROLE", "user").strip().lower()
UPSTREAM_TOOL_FORMAT = os.getenv("PROXY_UPSTREAM_TOOL_FORMAT", "xml").strip().lower()
TOOL_EXECUTOR_URL = os.getenv("PROXY_TOOL_EXECUTOR_URL", "").strip()
TOOL_EXECUTOR_API_KEY = os.getenv("PROXY_TOOL_EXECUTOR_API_KEY", "").strip()
TOOL_EXECUTOR_TIMEOUT = float(os.getenv("PROXY_TOOL_EXECUTOR_TIMEOUT", "1800"))
MAX_TOOL_ITERATIONS = int(os.getenv("PROXY_MAX_TOOL_ITERATIONS", "8"))
MAX_TOOL_RESULT_CHARS = int(
    os.getenv("PROXY_MAX_TOOL_RESULT_CHARS", str(DEFAULT_LARGE_TEXT_BUFFER_CHARS))
)
ENABLE_BUILTIN_TOOLS = os.getenv("PROXY_ENABLE_BUILTIN_TOOLS", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ENABLE_BUILTIN_EXECUTE_CODE = os.getenv(
    "PROXY_ENABLE_BUILTIN_EXECUTE_CODE",
    "false",
).lower() in {"1", "true", "yes", "on"}
ENABLE_TOOL_INTENT_REPAIR = os.getenv(
    "PROXY_ENABLE_TOOL_INTENT_REPAIR",
    "true",
).lower() in {"1", "true", "yes", "on"}
DEFAULT_VISIBLE_REASONING = os.getenv(
    "PROXY_VISIBLE_REASONING",
    "false",
).lower() in {"1", "true", "yes", "on"}
MAX_TOOL_INTENT_REPAIR_ATTEMPTS = int(
    os.getenv(
        "PROXY_MAX_TOOL_INTENT_REPAIR_ATTEMPTS",
        os.getenv("PROXY_MAX_REPAIR_ATTEMPTS", "1"),
    )
)
TOOL_INTENT_REPAIR_MAX_TOKENS = int(os.getenv("PROXY_TOOL_INTENT_REPAIR_MAX_TOKENS", "512"))
TOOL_INTENT_REPAIR_CONTEXT_CHARS = int(
    os.getenv("PROXY_TOOL_INTENT_REPAIR_CONTEXT_CHARS", "6000")
)
PROXY_JSON_LOG_DIR = Path(
    os.getenv(
        "PROXY_JSON_LOG_DIR",
        str(Path(__file__).resolve().parents[2] / "log_proxy"),
    )
)
PROXY_JSON_LOG_RETENTION_DAYS = int(os.getenv("PROXY_JSON_LOG_RETENTION_DAYS", "3"))
PROXY_JSON_LOG_PRUNE_INTERVAL_SECONDS = int(
    os.getenv("PROXY_JSON_LOG_PRUNE_INTERVAL_SECONDS", "3600")
)
LAST_PROXY_JSON_LOG_PRUNE = 0.0
CAPTURE_FAILURES = os.getenv("PROXY_CAPTURE_FAILURES", "0").lower() in {"1", "true", "yes", "on"}
CAPTURE_DIR = Path(
    os.getenv(
        "PROXY_CAPTURE_DIR",
        str(Path(__file__).resolve().parents[1] / "test" / "samples" / "quarantine"),
    )
)
CAPTURE_RAW_CHUNKS = os.getenv("PROXY_CAPTURE_RAW_CHUNKS", "0").lower() in {"1", "true", "yes", "on"}
CAPTURE_CLIENT_CHUNKS = os.getenv("PROXY_CAPTURE_CLIENT_CHUNKS", "1").lower() in {"1", "true", "yes", "on"}
CAPTURE_STACKTRACE = os.getenv("PROXY_CAPTURE_STACKTRACE", "1").lower() in {"1", "true", "yes", "on"}
CAPTURE_MAX_CHARS = int(os.getenv("PROXY_CAPTURE_MAX_CHARS", "200000"))
CAPTURE_SAMPLE_RATE = float(os.getenv("PROXY_CAPTURE_SAMPLE_RATE", "1.0"))
CAPTURE_REDACT_PRIVATE_IPS = os.getenv("PROXY_CAPTURE_REDACT_PRIVATE_IPS", "0").lower() in {"1", "true", "yes", "on"}

OPEN_TAGS = ("<think>", "<tool_call>")
THINK_TAGS = ("</think>", "<tool_call>")
VISIBLE_XML_BLOCK_TAGS = {
    "<tool_call>": "</tool_call>",
    "<tool_response>": "</tool_response>",
    "<result>": "</result>",
    "<command>": "</command>",
}
VISIBLE_XML_TAG_PREFIXES = (
    "<tool_call>",
    "</tool_call>",
    "<tool_response>",
    "</tool_response>",
    "<result>",
    "</result>",
    "<command>",
    "</command>",
    "<function",
    "</function>",
    "<parameter",
    "</parameter>",
)
PROXY_XML_TOOL_PROMPT_SENTINEL = "[PROXY_XML_TOOL_PROMPT_V1]"
NATIVE_TOOL_REQUEST_FIELDS = {
    "tools",
    "tool_choice",
    "parallel_tool_calls",
    "functions",
    "function_call",
}
