import base64
import json
import traceback
from urllib import parse

import fancycli
from .param_parser import ParamParser
from .req_wrapper import ReqWrapper
from .resp_builder import RespBuilder

"""

https://docs.aws.amazon.com/lambda/latest/dg/urls-invocation.html

Context:
https://docs.aws.amazon.com/lambda/latest/dg/python-context.html
stuff just about the runtime context
"""


class LambdaHosting:

    def __init__(self):
        self.util = ParamParser()

    def handle_request(self, app, event, context):
        """The app answers everything it can, exceptions included (ServerApp.pre_exception). What reaches the except
        here is a real failure: an event that couldn't be read, or an app hook that raised. It's printed with the
        event for the logs, passed to the app's on_failure, and answered with a plain 500"""
        req: ReqWrapper | None = None
        try:
            req = self.pack_request(event, context)
            resp: RespBuilder = app.handle(req)
            """function URLs / HTTP APIs send payload version 2.0, REST APIs send 1.0"""
            is_v2: bool = event.get("version") == "2.0"
            if resp.status in [500, 404]:
                fancycli.print_error(f"{resp.status} request event: {json.dumps(event)}")
            response: dict = self.format_response(resp, is_v2=is_v2)
            if req.method == "HEAD":
                """Same status and headers as the GET, no body. The function URL sends Content-Length: 0"""
                response["body"] = ""
            return response
        except Exception as ex:
            request_context: dict = event.get("requestContext") or {}
            method: str = request_context.get("httpMethod") or (request_context.get("http") or {}).get("method") or ""
            path: str = event.get("rawPath") or event.get("path") or ""
            query: str = self.event_query_string(event)
            path_and_query: str = f"{path}?{query}" if query else path
            title: str = f"Exception handling request {method} {path_and_query}"
            details: str = f"{self.describe_event(event)}\n\n{traceback.format_exc()}"
            fancycli.print_error(title, ex)
            print(details)
            try:
                app.on_failure(title=title, details=details, req=req)
            except Exception as failure_error:
                print(f"on_failure failed: {failure_error!r}")
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "text/plain"},
                "body": "Something went wrong. Please try again later.",
                "isBase64Encoded": False
            }

    def pack_request(self, event, context):
        req = ReqWrapper()
        """seems the same across contexts"""
        requestContext = event['requestContext']
        req.method = requestContext.get('httpMethod') or requestContext["http"]["method"]
        req.body = {}
        req.query = {}
        req.form = {}
        req.file = {}

        """A hand-built event (direct invoke, test event) may have no headers"""
        event_headers: dict = event.get("headers") or {}
        req.headers = {}
        for k in event_headers.keys():
            req.headers[k] = event_headers.get(k)
            req.headers[k.lower()] = event_headers.get(k)
        req.cookies = req.parse_cookie_header()

        req.body = self.parse_body(raw_body=event.get("body"), is_base64=bool(event.get("isBase64Encoded")),
                                   content_type=req.headers.get('content-type') or "")

        req.path = event.get("path") or requestContext["http"]["path"]
        """HTTP/1.0 clients (some bots) can leave out Host"""
        req.host = req.headers.get('host') or ""

        """ 
        "queryStringParameters": {
          "single": "one",
          "test": "two"
        },
        "multiValueQueryStringParameters": {
          "single": [
            "one"
          ],
          "test": [
            "one",
            "two"
          ]
        },"""
        qs = event.get("queryStringParameters")

        req.query = self.util.to_param_dict(qs)
        return req

    def event_query_string(self, event: dict) -> str:
        """The query string as sent: rawQueryString (payload 2.0), or rebuilt from the parameters (1.0)"""
        try:
            raw: str = event.get("rawQueryString") or ""
            if raw:
                return raw
            params: dict = event.get("multiValueQueryStringParameters") or event.get("queryStringParameters") or {}
            return parse.urlencode(params, doseq=True)
        except Exception:
            return ""

    def describe_event(self, event: dict) -> str:
        """Who sent a request and what was in it, for error reports. Read straight from the Lambda event, so it
        works even when the request couldn't be packed. Never raises"""
        try:
            headers: dict = {str(k).lower(): v for k, v in (event.get("headers") or {}).items()}
            request_context: dict = event.get("requestContext") or {}
            source_ip: str = ((request_context.get("http") or {}).get("sourceIp")
                              or (request_context.get("identity") or {}).get("sourceIp") or "")
            host: str = headers.get("x-forwarded-host") or headers.get("host") or ""
            body: str = str(event.get("body") or "")
            body_note: str = " (base64)" if event.get("isBase64Encoded") else ""
            lines: list[str] = [
                f"Host: {host or '(none)'}",
                f"Query: {self.event_query_string(event) or '(none)'}",
                f"IP: {source_ip or '(none)'}  Forwarded for: {headers.get('x-forwarded-for') or '(none)'}",
                f"Referer: {headers.get('referer') or '(none)'}",
                f"User agent: {headers.get('user-agent') or '(none)'}",
                f"Content type: {headers.get('content-type') or '(none)'}",
                f"Body{body_note}: {body[:500] if body else '(none)'}",
            ]
            return "\n".join(lines)
        except Exception as describe_error:
            return f"(request details unavailable: {describe_error!r})"

    def parse_body(self, raw_body: str | bytes | dict | list | None, is_base64: bool,
                   content_type: str) -> dict | list | bytes:
        """
        The request body as ServerApp expects it: a dict of fields, a list (a JSON array), or bytes (a raw upload).
        Never raises: a body that can't be read is logged and treated as empty, so one bad request can't 500.
        - HTTP events (function URLs, API Gateway, ALB) always send text, base64 encoded when isBase64Encoded
        - a dict or list only comes from a hand-built event (direct invoke, test event) and is used as is
        - a JSON content type can come with no body (bots send it on GETs) or with "; charset=utf-8"
        - bytes that aren't UTF-8 (a binary upload) are passed on as bytes
        """
        if not raw_body:
            return {}
        if isinstance(raw_body, (dict, list)):
            return raw_body
        try:
            body: str | bytes = raw_body
            if is_base64:
                body = base64.b64decode(body)
            if isinstance(body, (bytes, bytearray)):
                try:
                    body = body.decode('utf-8')
                except UnicodeDecodeError:
                    return bytes(body)

            if content_type.lower().startswith('application/json'):
                parsed = json.loads(body)
                """A JSON string or number has no fields to read"""
                return parsed if isinstance(parsed, (dict, list)) else {}
            return self.util.to_param_dict(parse.parse_qs(body, keep_blank_values=True))
        except Exception as ex:
            print(f"Ignoring a request body that couldn't be read ({ex!r}): {str(raw_body)[:200]!r}")
            return {}

    def format_response(self, resp: RespBuilder, is_v2: bool = True):

        body = resp.body
        response: dict = {
            "statusCode": resp.status,
            "headers": resp.headers,
            "body": body,
            "isBase64Encoded": False
        }
        """headers is a dict so it can't repeat Set-Cookie; each payload version has its own list for cookies"""
        cookie_strings: list[str] = list(resp.cookies.values())
        if cookie_strings:
            if is_v2:
                response["cookies"] = cookie_strings
            else:
                response["multiValueHeaders"] = {"Set-Cookie": cookie_strings}
        return response
