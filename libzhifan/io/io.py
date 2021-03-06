import json
import pickle


def read_txt(fname):
    """
    Read space-separated columns in txt file as a list of list
    """
    with open(fname, 'r') as fp:
        lines = fp.readlines()
    lines = [v.strip().replace('\t', ' ') for v in lines]
    lines = [
            list(filter(lambda x: len(x) > 0, v.split(' ')))
            for v in lines
            ]
    return lines


def read_json(fname):
    with open(fname) as fp:
        data = json.load(fp)
    return data


def read_pickle(fname, encoding='ASCII'):
    with open(fname, 'rb') as fp:
        data = pickle.load(fp, encoding=encoding)
    return data


def readfile(fname, *args, **kwargs):
    if fname.endswith('.txt'):
        return read_txt(fname)
    elif fname.endswith('.json'):
        return read_json(fname)
    elif fname.endswith('.pkl'):
        return read_pickle(fname, *args, **kwargs)


def write_txt(obj, fname):
    with open(fname, 'w') as fp:
        fp.writelines(obj)


def write_json(obj, fname, **kwargs):
    with open(fname, 'w') as fp:
        json.dump(obj, fp, **kwargs)


def write_pickle(obj, fname, protocol=None):
    with open(fname, 'wb') as fp:
        pickle.dump(obj, fp, protocol=protocol)


def writefile(obj, fname, *args, **kwargs):
    if fname.endswith('.txt'):
        return write_txt(obj, fname)
    elif fname.endswith('.json'):
        return write_json(obj, fname)
    elif fname.endswith('.pkl'):
        return write_pickle(obj, fname, *args, **kwargs)
