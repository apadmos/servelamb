import base64
import json
import traceback
from urllib import parse

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
                return self.format_response(resp, additional_context=json.dumps(event, indent=2))
            return self.format_response(resp)
        except Exception as ex:
            tb = traceback.format_exc()
            print(tb)
            return {
                "statusCode": 500,
                "headers": {
                    "Content-type": 'application/json'
                },
                "body": json.dumps({
                    "event": event,
                    "trace": tb
                }, indent=2),
                "isBase64Encoded": False
            }

    def pack_request(self, event, context):
        req = ReqWrapper()
        req.method = event['requestContext']['httpMethod']
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

        req.path = event["path"]
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
        qs = event["queryStringParameters"]

        req.query = self.util.to_param_dict(qs)
        return req

    def format_response(self, resp: RespBuilder, additional_context: str = None):

        body = resp.body
        if additional_context:
            if "<html" in body.lower():
                body += f"<div>{additional_context}</div>"
            else:
                body += f"\n\n{additional_context}"

        return {
            "statusCode": resp.status,
            "headers": resp.headers,
            "body": body,
            "isBase64Encoded": False
        }
