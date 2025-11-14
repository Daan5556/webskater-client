headers = {"Connection": "close", "User-Agent": "Webskater"}


def stringify_headers():
    headers_string = ""

    for key, value in headers.items():
        headers_string += f"{key}: {value}\r\n"

    return headers_string
