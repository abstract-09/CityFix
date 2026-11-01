"""Log hygiene: contact details must never reach the logs."""
import logging
import re

EMAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s\-]?)?\d{10}(?!\d)")


def mask(text: str) -> str:
    return PHONE_RE.sub("[phone]", EMAIL_RE.sub("[email]", text))


class MaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask(record.getMessage())
        record.args = ()
        return True


def install_log_masking() -> None:
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for handler in root.handlers:
        if not any(isinstance(f, MaskingFilter) for f in handler.filters):
            handler.addFilter(MaskingFilter())
