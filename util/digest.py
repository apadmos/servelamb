class Digest(dict):

    def __init__(self, *source, **kwargs):
        super(Digest).__init__()
        for arg in source:
            if arg and isinstance(arg, dict):
                for key in arg.keys():
                    self[key] = arg[key]
        for kw in kwargs:
            self[kw] = kwargs[kw]

    def __getattr__(self, attr):
        if attr not in self:
            raise AttributeError("No attribute '{}' in digest".format(attr))
        return self[attr]

    def __setattr__(self, key, value):
        self[key] = value

    @classmethod
    def from_locals(cls, locals, ignore_falsies=True):
        del locals["self"]
        if ignore_falsies:
            locals = {k: v for k, v in locals.items() if v}
        return Digest(locals)

    @classmethod
    def list_of(cls, items: list):
        return list([Digest(i) for i in items])


class NullableDigest(Digest):

    def __init__(self, *source, **kwargs):
        super(NullableDigest, self).__init__(*source, **kwargs)

    def __getattr__(self, attr):
        if attr not in self:
            return None
        return self[attr]


if __name__ == '__main__':
    print(Digest({"test": 1234}, mix='up'))
    print(Digest(test=1234, two="three", source="crap"))
