import json
import time
import traceback
import urllib.request


class ErrorReportingSettings:
    """What ErrorReporter needs from a project's config"""

    def __init__(self, slack_webhook_url: str = "", environment_label: str = "", throttle_minutes: float = 0,
                 report_status_codes: list[int] | None = None, slack_mention: str = ""):
        """A Slack incoming webhook; its channel (the recipient) is chosen when the webhook is created. Empty: off"""
        self.slack_webhook_url: str = slack_webhook_url
        """Shown at the start of every message, e.g. "prod" """
        self.environment_label: str = environment_label
        """At most one message per kind of error in this many minutes. 0 sends every error"""
        self.throttle_minutes: float = throttle_minutes
        """Response statuses report_response sends, e.g. [404, 500]"""
        self.report_status_codes: list[int] = report_status_codes or []
        """Put in front of every message, e.g. "<!channel>" or "<@U012AB3CD>" to notify someone"""
        self.slack_mention: str = slack_mention


class ErrorReporter:
    """
    Sends a site's own errors to Slack. Off until a project calls configure() with its ErrorReportingSettings,
    which are read once and kept: call it as early in start up as the config allows.

    What servelamb reports by itself once configured: exceptions LambdaHosting catches.
    What a project wires up: report_response from its before_response, and report() for its start up failure.

    Each kind of error has its own throttle, so a burst of 404s can't hide an exception.
    The throttle is per process (in memory), so on Lambda each warm container throttles on its own.
    Urgent reports skip the throttle.

    It never raises. If reporting itself fails, one plain message about that failure is attempted straight to the
    webhook, skipping the throttle and the formatting.
    Only the standard library is used, so a missing package can't stop a start up failure from being reported.

    Import it by one module path only (e.g. always servelamb.error_reporter): a second path makes a second class
    that was never configured.
    """
    SLACK_TIMEOUT_SECONDS: float = 3
    MAX_DETAIL_CHARS: int = 2500

    _settings: ErrorReportingSettings | None = None
    """kind -> time.time() of the last message sent for it"""
    _last_sent_at: dict[str, float] = {}
    """kind -> errors held back by the throttle since the last message for it"""
    _held_back: dict[str, int] = {}

    @classmethod
    def configure(cls, settings: ErrorReportingSettings) -> None:
        cls._settings = settings

    @classmethod
    def report(cls, kind: str, title: str, details: str | None = None, urgent: bool = False) -> None:
        """kind groups errors for the throttle ("exception", "404", "startup"); title is the first line in Slack"""
        settings: ErrorReportingSettings | None = cls._settings
        if not settings or not settings.slack_webhook_url:
            return
        try:
            now: float = time.time()
            throttle_seconds: float = settings.throttle_minutes * 60
            is_throttled: bool = bool(throttle_seconds) and now - cls._last_sent_at.get(kind, 0) < throttle_seconds
            if is_throttled and not urgent:
                cls._held_back[kind] = cls._held_back.get(kind, 0) + 1
                return

            held_back: int = cls._held_back.get(kind, 0)
            held_back_note: str = (f"\n_{held_back} more \"{kind}\" errors were held back by the "
                                   f"{settings.throttle_minutes} minute throttle_") if held_back else ""
            mention: str = f"{settings.slack_mention} " if settings.slack_mention else ""
            detail_block: str = f"\n```{details[:cls.MAX_DETAIL_CHARS]}```" if details else ""
            text: str = f"{mention}*[{settings.environment_label}] {title}*{detail_block}{held_back_note}"
            cls._post(url=settings.slack_webhook_url, text=text)

            """the held back count was just sent; an urgent message doesn't restart the throttle window"""
            cls._held_back[kind] = 0
            if not urgent:
                cls._last_sent_at[kind] = now
        except Exception as reporting_error:
            cls._report_own_failure(title=title, details=details, reporting_error=reporting_error)

    @classmethod
    def report_response(cls, req, resp) -> None:
        """For a ServerApp before_response hook: reports the response if its status is in report_status_codes.
        An exception in a controller leaves the status at 200, so it's reported once, by LambdaHosting, not here"""
        settings: ErrorReportingSettings | None = cls._settings
        if not settings or not settings.slack_webhook_url:
            return
        try:
            if resp.status not in settings.report_status_codes:
                return
            headers: dict = req.headers or {}
            details: str = "\n".join([
                f"Referer: {headers.get('referer') or '(none)'}",
                f"User agent: {headers.get('user-agent') or '(none)'}",
                f"Response: {str(resp.body or '')[:500]}",
            ])
            cls.report(kind=str(resp.status), title=f"{resp.status} {req.method} {req.path}", details=details)
        except Exception as reporting_error:
            cls._report_own_failure(title=f"{resp.status} response", details=None, reporting_error=reporting_error)

    @classmethod
    def _report_own_failure(cls, title: str, details: str | None, reporting_error: BaseException) -> None:
        """Last resort: print, then one plain message straight to the webhook, no throttle"""
        print(f"Error reporting failed while reporting: {title}")
        traceback.print_exc()
        try:
            text: str = (f"Error reporting failed ({reporting_error!r}) while reporting: {title}\n"
                         f"{(details or '')[:1500]}")
            cls._post(url=cls._settings.slack_webhook_url, text=text)
        except BaseException as last_error:
            print(f"Could not send the error reporting failure to Slack either: {last_error!r}")

    @classmethod
    def _post(cls, url: str, text: str) -> None:
        """A Slack incoming webhook: the channel is chosen when the webhook is created"""
        request = urllib.request.Request(url=url, data=json.dumps({"text": text}).encode("utf-8"),
                                         headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=cls.SLACK_TIMEOUT_SECONDS) as response:
            response.read()
