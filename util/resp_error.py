import requests

def check(resp: requests.Response) -> None:
    """
    Like resp.raise_for_status(), but also prints the response body
    when an error occurs for easier debugging.
    """
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        print("HTTP error:", e)
        print("Response body:", resp.text.strip())
        raise