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
        try:
            req = self.pack_request(event, context)
            resp = app.handle(req)
            if resp.status in [500, 404]:
                return self.format_response(resp, additional_context=json.dumps(event))
            return self.format_response(resp)
        except Exception as ex:
            tb = traceback.format_exc()
            fancycli.print_error("Exception handling request", ex)
            try:
                rv = {
                    "statusCode": 500,
                    "headers": {
                        "Content-Type": 'application/json'
                    },
                    "body": json.dumps({
                        "event": event,
                        "trace": tb
                    }, indent=2),
                    "isBase64Encoded": False
                }
                fancycli.print_error("About to try and return error")
                fancycli.print_error(rv)
                return rv
            except Exception as ex:
                fancycli.print_error("Exception handling error", exception=ex)
                return {
                    "statusCode": 500,
                    "headers": {
                        "Content-Type": 'text/plain'
                    },
                    "body": "Second layer exception",
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

        req.headers = {}
        for k in event["headers"].keys():
            req.headers[k] = event["headers"].get(k)
            req.headers[k.lower()] = event["headers"].get(k)

        body = {}
        if event.get("body"):
            body = event["body"]
            if event["isBase64Encoded"]:
                body = base64.b64decode(body)
                body = body.decode('utf-8')

        if req.headers.get('content-type') == 'application/json':
            req.body = json.loads(body)
        else:
            req.body = self.util.to_param_dict(parse.parse_qs(body, keep_blank_values=True))

        req.path = event.get("path") or requestContext["http"]["path"]
        req.host = req.headers['host']

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

    def format_response(self, resp: RespBuilder, additional_context: str = None):

        body = resp.body
        print("HEADERS:", repr(resp.headers))

        if additional_context:
            body += f"\n\nADDITIONAL CONTEXT: \n{additional_context}"

        return {
            "statusCode": resp.status,
            "headers": resp.headers,
            "body": body,
            "isBase64Encoded": False
        }
