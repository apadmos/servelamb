import datetime
import re

def date_format(d: datetime.datetime):
    if d:
        if hasattr(d, 'strftime'):
            return d.strftime("%b %d %Y")
        else:
            return d
    return ''

def date_input_format(d: datetime.datetime):
    """format a date into a string that a <input type="date" /> can understand"""
    if d:
        if hasattr(d, 'strftime'):
            return d.strftime("%Y-%m-%d")
        else:
            return d
    return ''

def words_split(s:str):
    parts = []
    if s:
        for word in re.split('[^a-zA-Z\\d]', s):
            parts.append(word)
    return " ".join(parts)