import unicodedata


def is_emoji(char: str) -> bool:
    if len(char) != 1:
        return False

    if unicodedata.category(char) == "So":
        return True

    code = ord(char)
    return (
        0x1F300 <= code <= 0x1F5FF  # Misc Symbols and Pictographs
        or 0x1F600 <= code <= 0x1F64F  # Emoticons
        or 0x1F680 <= code <= 0x1F6FF  # Transport and Map
        or 0x2600 <= code <= 0x26FF  # Misc symbols
        or 0x2700 <= code <= 0x27BF  # Dingbats
        or 0x1F900 <= code <= 0x1F9FF  # Supplemental Symbols and Pictographs
        or 0x1FA70 <= code <= 0x1FAFF  # Symbols and Pictographs Extended-A
    )


def get_emoji_data(char: str):
    code = hex(ord(char))[2:].upper()
    path = f"assets/emoji/{code}.png"

    return (code, path)
