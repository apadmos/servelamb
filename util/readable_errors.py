import re

class ReadableError(Exception):
    def __init__(self, user_message:str):
        self.user_message = user_message


class ReadableErrors(object):

    def translate_for_end_user(self, ex) -> str:
        if hasattr(ex, 'user_message'):
            return ex.user_message

        txt = str(ex)
        """Look for a duplicate key exception and return the value that's dupe"""
        m = re.search(r"DETAIL:\s+Key\s+\((.+)\)=\((.+)\)\s+already\s+exists", txt, re.RegexFlag.M)
        if m:
            val = m[2]
            key = str(m[1]).capitalize()
            return f"A record for {val} already exists. {key}s must be unique."

        print(f"Could not translate error {ex}")
        return ''
