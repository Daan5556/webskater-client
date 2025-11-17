import socket
import ssl
import tkinter

from data.headers import stringify_headers
from file import read_file


class URL:
    def __init__(self, url):
        if ":" not in url:
            url = "about:blank"

        self.scheme, url = url.split(":")

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
        version, status, explanation = statusline.split(" ", 2)

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


def layout(text, width):
    display_list = []
    cursor_x, cursor_y = HSTEP, VSTEP

    for c in text:
        if c == "\n":
            cursor_x = HSTEP
            cursor_y += VSTEP
            continue
        display_list.append((cursor_x, cursor_y, c))
        cursor_x += HSTEP
        if cursor_x >= width - HSTEP:
            cursor_y += VSTEP
            cursor_x = HSTEP

    return display_list


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
        self.window.bind("<Configure>", self.on_resize)

    def load(self, url):
        body = url.request()
        self.text = lex(body)
        self.display_list = layout(self.text, self.width)
        self.set_max_scroll()
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        self.calculate_scroll_status()

        if self.max_scroll != 0:
            self.canvas.create_text(HSTEP, VSTEP, text=self.scroll_status)

        for x, y, c in self.display_list:
            if y > self.scroll + self.height:
                continue
            if y + VSTEP < self.scroll:
                continue
            self.canvas.create_text(x, y - self.scroll, text=c)

    def on_resize(self, e):
        self.width = e.width
        self.height = e.height
        self.display_list = layout(self.text, self.width)
        self.set_max_scroll()
        self.draw()

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

    def scrollup(self, e):
        self.scroll -= SCROLL_STEP
        if self.scroll < 0:
            self.scroll = 0
        self.draw()

    def scrolldown(self, e):
        self.scroll += SCROLL_STEP
        if self.scroll > self.max_scroll:
            self.scroll = self.max_scroll
        self.draw()


def lex(body):
    text = ""
    in_tag = False
    for c in body:
        if c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif not in_tag:
            text += c

    return text


if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else "about:blank"
    Browser().load(URL(url))
    tkinter.mainloop()
