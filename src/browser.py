import socket
import ssl
import tkinter
import tkinter.font
from typing import Literal
from dataclasses import dataclass

from src.emoji import get_emoji_data, is_emoji

from .data.headers import stringify_headers
from .file import read_file


class URL:
    def __init__(self, url):
        if ":" not in url:
            url = "about:blank"

        self.scheme, url = url.split(":", 1)

        if self.scheme not in ["http", "https", "file", "data", "about"]:
            self.scheme = "about"
            return

        if self.scheme == "data":
            self.media_type, self.data = url.split(",")
            return

        if self.scheme == "about":
            return

        _, url = url.split("//")

        if self.scheme == "http":
            self.port = 80

        if self.scheme == "https":
            self.port = 443

        if "/" not in url:
            url += "/"

        self.host, url = url.split("/", 1)
        self.path = "/" + url

        if ":" in self.host:
            self.host, port = self.host.split(":", 1)
            self.port = int(port)

    def request(self):
        if self.scheme == "file":
            return read_file(self.path)

        if self.scheme == "data":
            return self.data

        if self.scheme == "about":
            return []

        s = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
        )

        s.connect((self.host, self.port))

        if self.scheme == "https":
            ctx = ssl.create_default_context()
            s = ctx.wrap_socket(s, server_hostname=self.host)

        request = "GET {} HTTP/1.0\r\n".format(self.path)
        request += "Host: {}\r\n".format(self.host)
        request += stringify_headers()
        request += "\r\n"
        s.send(request.encode("utf8"))

        response = s.makefile("r", encoding="utf8", newline="\r\n")
        statusline = response.readline()
        _, _, _ = statusline.split(" ", 2)  # version status explanation

        response_headers = {}
        while True:
            line = response.readline()
            if line == "\r\n":
                break
            header, value = line.split(":", 1)
            response_headers[header.casefold()] = value.strip()

        assert "transfer-encoding" not in response_headers
        assert "content-encoding" not in response_headers

        content = response.read()
        s.close()

        return content


WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100
FONTS = {}


class Layout:
    def __init__(self, tokens):
        self.display_list = []
        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        self.style: Literal["roman", "italic"] = "roman"
        self.weight: Literal["normal", "bold"] = "normal"
        self.size = 12
        self.line = []
        for tok in tokens:
            self.token(tok)
        self.flush()

    def token(self, tok):
        if isinstance(tok, Text):
            self.word(tok.text)

        elif tok.tag == "i":
            self.style = "italic"
        elif tok.tag == "/i":
            self.style = "roman"
        elif tok.tag == "b":
            self.weight = "bold"
        elif tok.tag == "/b":
            self.weight = "normal"
        elif tok.tag == "small":
            self.size -= 2
        elif tok.tag == "/small":
            self.size += 2
        elif tok.tag == "big":
            self.size += 4
        elif tok.tag == "/big":
            self.size -= 4
        elif tok.tag == "br":
            self.flush()
        elif tok.tag == "/p":
            self.flush()
            self.cursor_y += VSTEP

    def word(self, word):
        font = get_font(self.size, self.weight, self.style)
        for word in word.split():
            w = font.measure(word)
            if self.cursor_x + w > WIDTH - HSTEP:
                self.flush()
            self.line.append((self.cursor_x, word, font))
            self.cursor_x += w + font.measure(" ")

    def flush(self):
        if not self.line:
            return
        metrics = [font.metrics() for _, _, font in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent
        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent

        for x, word, font in self.line:
            y = baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font))

        self.cursor_x = HSTEP
        self.line = []


class Browser:
    def __init__(self):
        self.width = WIDTH
        self.height = HEIGHT

        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=self.width, height=self.height)
        self.canvas.pack(fill=tkinter.BOTH, expand=True)
        self.scroll = 0

        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Button-4>", self.scrollup)
        self.window.bind("<Button-5>", self.scrolldown)

    def load(self, url):
        body = url.request()
        tokens = lex(body)
        self.display_list = Layout(tokens).display_list
        self.set_max_scroll()
        self.draw()

    def draw(self):
        self.canvas.delete("all")

        self.calculate_scroll_status()

        if self.max_scroll != 0:
            self.canvas.create_text(HSTEP, VSTEP, text=self.scroll_status)

        for x, y, c, font in self.display_list:
            if y > self.scroll + self.height:
                continue
            if y + VSTEP < self.scroll:
                continue

            if is_emoji(c):
                if not hasattr(self, "emoji_images"):
                    self.emoji_images = {}

                code, path = get_emoji_data(c)

                if code not in self.emoji_images:
                    self.emoji_images[code] = tkinter.PhotoImage(file=path)

                image = self.emoji_images[code]
                self.canvas.create_image(x, y - self.scroll, image=image)
                continue

            self.canvas.create_text(x, y - self.scroll, text=c, font=font, anchor="nw")

    def set_max_scroll(self):
        if len(self.display_list) == 0:
            self.max_scroll = 0
            return

        last_item = self.display_list[-1]
        max_y = last_item[1]

        self.max_scroll = (max_y + VSTEP) - self.height

    def calculate_scroll_status(self):
        if self.max_scroll == 0:
            self.scroll_status = 100
            return

        self.scroll_status = round(self.scroll / self.max_scroll * 100)

    def scrollup(self, _):
        self.scroll -= SCROLL_STEP
        if self.scroll < 0:
            self.scroll = 0
        self.draw()

    def scrolldown(self, _):
        self.scroll += SCROLL_STEP
        if self.scroll > self.max_scroll:
            self.scroll = self.max_scroll
        self.draw()


@dataclass
class Text:
    text: str


@dataclass
class Tag:
    tag: str


def lex(body):
    out = []
    buffer = ""
    in_tag = False
    for c in body:
        if c == "<":
            in_tag = True
            if buffer:
                out.append(Text(buffer))
            buffer = ""
        elif c == ">":
            in_tag = False
            out.append(Tag(buffer))
            buffer = ""
        else:
            buffer += c
    if not in_tag and buffer:
        out.append(Text(buffer))

    return out


def get_font(size, weight, style):
    key = (size, weight, style)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight, slant=style)
        label = tkinter.Label(font=font)
        FONTS[key] = (font, label)
    return FONTS[key][0]


if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else "about:blank"
    Browser().load(URL(url))
    tkinter.mainloop()
