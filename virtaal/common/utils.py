def get_bytes(string):
    if isinstance(string, str):
        return string.encode()
    return string
