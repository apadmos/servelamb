class ParamParser:

    def to_param_dict(self, parsed_query):
        rdict = {}
        if not parsed_query:
            return rdict
        for k in parsed_query:
            if not parsed_query[k]:
                # be explicit about empty arrays of values
                rdict[k] = None
            elif len(parsed_query[k]) == 1:
                # for single values take them out of the array packing
                rdict[k] = parsed_query[k][0]
            else:
                rdict[k] = parsed_query[k]
        return rdict
