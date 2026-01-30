from __future__ import annotations
import socket
import ssl
import tkinter
import tkinter.font
from typing import Dict
from dataclasses import dataclass, field

from src.data import errors
from src.data.entities import entities

from .data.headers import stringify_headers
from .file import read_file


class URL:
    def __init__(self, url):
        self.error = None
        if ":" not in url:
            url = "about:blank"

        self.scheme, url = url.split(":", 1)

        if self.scheme not in ["http", "https", "file", "data", "about"]:
            self.scheme = "about"
            return

        if self.scheme == "data":
            try:
                self.media_type, self.data = url.split(",")  # noqa: vulture
            except ValueError:
                self.error = errors.invalid_url
            return

        if self.scheme == "about":
            return

        try:
            _, url = url.split("//", 1)
        except ValueError:
            self.error = errors.invalid_url
            return

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
        if self.error:
            return self.error
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


def is_head_tag(node):
    if isinstance(node, Element) and node.tag in HEAD_TAGS + ["head"]:
        return True
    parent = node.parent
    while parent:
        if parent.tag == "head":
            return True

        parent = parent.parent

    return False


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

    def layout_mode(self):
        if isinstance(self.node, Text):
            return "inline"
        elif any(
            [
                isinstance(child, Element) and child.tag in BLOCK_ELEMENTS
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
                if is_head_tag(child):
                    continue
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

    def recurse(self, tree):
        if is_head_tag(tree):
            return
        if isinstance(tree, Text):
            for word in tree.text.split():
                self.word(word)
        else:
            self.open_tag(tree.tag)
            for child in tree.children:
                self.recurse(child)
            self.close_tag(tree.tag)

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
        if tag == "i":
            self.style = "roman"
        elif tag == "b":
            self.weight = "normal"
        elif tag == "small":
            self.size += 2
        elif tag == "big":
            self.size -= 4
            self.flush()
        elif tag == "p":
            self.flush()
            self.cursor_y += VSTEP

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

    def word(self, word):
        font = get_font(self.size, self.weight, self.style)
        w = font.measure(word)
        if self.cursor_x + w > self.width:
            self.flush()
        self.line.append((self.cursor_x, word, font))
        self.cursor_x += w + font.measure(" ")

    def paint(self):
        cmds = []
        if isinstance(self.node, Element) and (
            # TEMPORARY STYLES
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
    def __init__(self, node, window_width):
        self.node = node
        self.parent = None
        self.children = []
        self.x = None
        self.y = None
        self.width = None
        self.height = None
        self.window_width = window_width

    def __repr__(self):
        return "DocumentLayout[]()"

    def layout(self):
        child = BlockLayout(self.node, self, None)
        self.children.append(child)

        self.width = self.window_width - 2 * HSTEP
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

    def implicit_tags(self, tag):
        while True:
            open_tags = [node.tag for node in self.unfinished]
            if open_tags == [] and tag != "html":
                self.add_tag("html")
            elif open_tags == ["html"] and tag not in ["head", "body", "/html"]:
                if tag in HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")
            elif open_tags == ["html", "head"] and tag not in ["/head"] + HEAD_TAGS:
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
            elif not in_tag and c == "&":
                # Character reference parser
                matches = []
                for key in entities:
                    if self.body.startswith(key, i):
                        matches.append(key)
                longest_match = max(matches, key=len, default=None)
                if longest_match:
                    char_ref = entities.get(longest_match)
                    assert char_ref is not None
                    characters = char_ref.get("characters")
                    assert isinstance(characters, str)
                    text += characters
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
        self.canvas = tkinter.Canvas(self.window)
        self.canvas.pack(fill=tkinter.BOTH, expand=True)
        self.scroll = 0

        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Button-4>", self.scrollup)
        self.window.bind("<Button-5>", self.scrolldown)
        self.canvas.bind("<Configure>", self.configure)

    def max_scroll_y(self):
        assert self.document.height is not None
        return max(self.document.height + 2 * VSTEP - self.height, 0)

    def load(self, url):
        body = url.request()
        self.nodes = HTMLParser(body).parse()
        # print_tree(self.nodes)
        self.relayout()

    def relayout(self):
        self.document = DocumentLayout(self.nodes, self.width)
        self.document.layout()
        # print_tree(self.document)
        self.display_list = []
        paint_tree(self.document, self.display_list)
        max_y = self.max_scroll_y()
        if self.scroll > max_y:
            self.scroll = max_y
        self.draw()

    def draw(self):
        self.canvas.delete("all")

        for cmd in self.display_list:
            if cmd.top > self.scroll + self.height:
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
        max_y = self.max_scroll_y()
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)
        self.draw()

    def configure(self, e):
        if e.width == self.width and e.height == self.height:
            return
        self.width = e.width
        self.height = e.height
        self.relayout()


if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else "about:blank"
    Browser().load(URL(url))
    tkinter.mainloop()
