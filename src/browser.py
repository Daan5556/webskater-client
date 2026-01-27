from __future__ import annotations
import socket
import ssl
import tkinter
import tkinter.font
from typing import Dict
from dataclasses import dataclass, field

from src.data.entities import entities

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


@dataclass
class Element:
    tag: str
    attributes: Dict
    parent: Element | None
    children: list["Element"] = field(default_factory=list)

    def __repr__(self) -> str:
        return "<" + self.tag + ">"


@dataclass
class Text:
    text: str
    parent: Element
    children: list["Element"] = field(default_factory=list)

    def __repr__(self) -> str:
        return repr(self.text)


FONTS = {}


def get_font(size, weight, style):
    key = (size, weight, style)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight, slant=style)
        label = tkinter.Label(font=font)
        FONTS[key] = (font, label)
    return FONTS[key][0]


WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100


class BlockLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
        self.x = None
        self.y = None
        self.width = None
        self.height = None
        self.display_list = []

    def __repr__(self):
        return "BlockLayout[{}](x={}, y={}, width={}, height={}, node={})".format(
            self.layout_mode(), self.x, self.y, self.width, self.height, self.node
        )

    def layout_intermediate(self):
        previous = None
        for child in self.node.children:
            next = BlockLayout(child, self, previous)
            self.children.append(next)
            previous = next

    def open_tag(self, tag):
        if tag == "i":
            self.style = "italic"
        elif tag == "b":
            self.weight = "bold"
        elif tag == "small":
            self.size -= 2
        elif tag == "big":
            self.size += 4
        elif tag == "br":
            self.flush()

    def close_tag(self, tag):
        if tag == "/i":
            self.style = "roman"
        elif tag == "/b":
            self.weight = "normal"
        elif tag == "/small":
            self.size += 2
        elif tag == "/big":
            self.size -= 4
            self.flush()
        elif tag == "/p":
            self.flush()
            self.cursor_y += VSTEP

    def token(self, tok):
        if isinstance(tok, Text):
            self.word(tok.text)

    def recurse(self, tree):
        if isinstance(tree, Text):
            for word in tree.text.split():
                self.word(word)
        else:
            self.open_tag(tree.tag)
            for child in tree.children:
                self.recurse(child)
            self.close_tag(tree.tag)

    def word(self, word):
        font = get_font(self.size, self.weight, self.style)
        for word in word.split():
            w = font.measure(word)
            if self.cursor_x + w > self.width:
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
        self.cursor_x = 0
        self.cursor_y = baseline + 1.25 * max_descent

        for rel_x, word, font in self.line:
            x = self.x + rel_x
            y = self.y + baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font))

        self.cursor_x = HSTEP
        self.line = []

    BLOCK_ELEMENTS = [
        "html",
        "body",
        "article",
        "section",
        "nav",
        "aside",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hgroup",
        "header",
        "footer",
        "address",
        "p",
        "hr",
        "pre",
        "blockquote",
        "ol",
        "ul",
        "menu",
        "li",
        "dl",
        "dt",
        "dd",
        "figure",
        "figcaption",
        "main",
        "div",
        "table",
        "form",
        "fieldset",
        "legend",
        "details",
        "summary",
    ]

    def layout_mode(self):
        if isinstance(self.node, Text):
            return "inline"
        elif any(
            [
                isinstance(child, Element) and child.tag in self.BLOCK_ELEMENTS
                for child in self.node.children
            ]
        ):
            return "block"
        elif self.node.children:
            return "inline"
        else:
            return "block"

    def layout(self):
        self.x = self.parent.x
        self.width = self.parent.width

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        mode = self.layout_mode()
        if mode == "block":
            previous = None
            for child in self.node.children:
                next = BlockLayout(child, self, previous)
                self.children.append(next)
                previous = next
        else:
            self.cursor_x = 0
            self.cursor_y = 0
            self.weight = "normal"
            self.style = "roman"
            self.size = 12

            self.line = []
            self.recurse(self.node)
            self.flush()

        for child in self.children:
            child.layout()

        if mode == "block":
            self.height = sum([child.height for child in self.children])
        else:
            self.height = self.cursor_y

    def paint(self):
        cmds = []
        if isinstance(self.node, Element) and (
            self.node.tag == "pre"
            or (self.node.tag == "nav" and self.node.attributes.get("class") == "links")
        ):
            assert self.x is not None
            assert self.y is not None
            x2 = self.x + self.width
            y2 = self.y + self.height
            rect = DrawRect(self.x, self.y, x2, y2, "gray")
            cmds.append(rect)
        if self.layout_mode() == "inline":
            for x, y, word, font in self.display_list:
                cmds.append(DrawText(x, y, word, font))
        return cmds


class DocumentLayout:
    def __init__(self, node):
        self.node = node
        self.parent = None
        self.children = []
        self.x = None
        self.y = None
        self.width = None
        self.height = None

    def layout(self):
        child = BlockLayout(self.node, self, None)
        self.children.append(child)

        self.width = WIDTH - 2 * HSTEP
        self.x = HSTEP
        self.y = VSTEP
        child.layout()
        self.height = child.height

    def paint(self):
        return []


class HTMLParser:
    def __init__(self, body):
        self.body = body
        self.unfinished = []
        self.SELF_CLOSING_TAGS = [
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        ]

    HEAD_TAGS = [
        "base",
        "basefont",
        "bgsound",
        "noscript",
        "link",
        "meta",
        "title",
        "style",
        "script",
    ]

    def implicit_tags(self, tag):
        while True:
            open_tags = [node.tag for node in self.unfinished]
            if open_tags == [] and tag != "html":
                self.add_tag("html")
            elif open_tags == ["html"] and tag not in ["head", "body", "/html"]:
                if tag in self.HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")
            elif (
                open_tags == ["html", "head"] and tag not in ["/head"] + self.HEAD_TAGS
            ):
                self.add_tag("/head")
            else:
                break

    def add_text(self, text):
        if text.isspace():
            return
        self.implicit_tags(None)
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)

    def add_tag(self, tag):
        tag, attributes = self.get_attributes(tag)
        if tag.startswith("!"):
            return
        self.implicit_tags(tag)
        if tag.startswith("/"):
            if len(self.unfinished) == 1:
                return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        elif tag in self.SELF_CLOSING_TAGS:
            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            parent.children.append(node)

        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(tag, attributes, parent)
            self.unfinished.append(node)

    def get_attributes(self, text):
        parts = text.split()
        tag = parts[0].casefold()
        attributes = {}
        for attrpair in parts[1:]:
            if "=" in attrpair:
                key, value = attrpair.split("=", 1)
                if len(value) > 2 and value[0] in ["'", '"']:
                    value = value[1:-1]
                attributes[key.casefold()] = value
            else:
                attributes[attrpair.casefold()] = ""

        return tag, attributes

    def finish(self):
        if not self.unfinished:
            self.implicit_tags(None)
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        return self.unfinished.pop()

    def parse(self):
        text = ""
        in_tag = False
        in_comment = False
        i = 0
        while i < len(self.body):
            c = self.body[i]
            if in_comment:
                if self.body.startswith("-->", i):
                    in_comment = False
                    i += 3
                    continue
                i += 1
                continue
            if not in_comment and not in_tag and self.body.startswith("<!--", i):
                if text:
                    self.add_text(text)
                    text = ""
                in_comment = True
                i += 4
                continue
            if c == "<":
                in_tag = True
                if text:
                    self.add_text(text)
                text = ""
            elif c == ">":
                in_tag = False
                self.add_tag(text)
                text = ""
            elif c == "&":
                # Character reference parser
                matches = []
                for key in entities:
                    if self.body.startswith(key, i):
                        matches.append(key)
                longest_match = max(matches, key=len, default=None)
                if longest_match:
                    text += entities.get(longest_match).get("characters")
                    i += len(longest_match)
                    continue
                else:
                    text += c

            else:
                text += c

            i += 1

        if not in_tag and text:
            self.add_text(text)

        return self.finish()


def print_tree(node, indent=0):
    print(" " * indent, node)
    for child in node.children:
        print_tree(child, indent + 2)


def paint_tree(layout_object, display_list):
    display_list.extend(layout_object.paint())

    for child in layout_object.children:
        paint_tree(child, display_list)


class DrawText:
    def __init__(self, x1, y1, text, font):
        self.top = y1
        self.left = x1
        self.text = text
        self.font = font
        self.bottom = y1 + font.metrics("linespace")

    def execute(self, scroll, canvas):
        canvas.create_text(
            self.left, self.top - scroll, text=self.text, font=self.font, anchor="nw"
        )


class DrawRect:
    def __init__(self, x1, y1, x2, y2, color):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2
        self.color = color

    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.left,
            self.top - scroll,
            self.right,
            self.bottom - scroll,
            width=0,
            fill=self.color,
        )


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
        self.nodes = HTMLParser(body).parse()
        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        # print_tree(self.document)
        self.display_list = []
        paint_tree(self.document, self.display_list)
        self.draw()

    def draw(self):
        self.canvas.delete("all")

        for cmd in self.display_list:
            if cmd.top > self.scroll + HEIGHT:
                continue
            if cmd.bottom < self.scroll:
                continue
            cmd.execute(self.scroll, self.canvas)

    def scrollup(self, _):
        self.scroll -= SCROLL_STEP
        if self.scroll < 0:
            self.scroll = 0
        self.draw()

    def scrolldown(self, _):
        assert self.document.height is not None
        max_y = max(self.document.height + 2 * VSTEP - HEIGHT, 0)
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)
        self.draw()


if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else "about:blank"
    Browser().load(URL(url))
    tkinter.mainloop()
