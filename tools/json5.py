"""Minimal, strict JSON5 parser (data only, no code evaluation).

Supports: // and /* */ comments, unquoted identifier keys, single- or
double-quoted strings, trailing commas, true/false/null, numbers.
Anything that looks like code (function calls, operators, template literals)
raises ValueError.
"""

import re

IDENT_START = re.compile(r"[A-Za-z_$\u00a0-\uffff]")
IDENT = re.compile(r"[A-Za-z0-9_$\u00a0-\uffff]*")
NUM = re.compile(r"[+-]?(?:0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)")


class Json5Error(ValueError):
    pass


class Parser:
    def __init__(self, text, source="<string>"):
        self.s = text
        self.i = 0
        self.n = len(text)
        self.source = source

    def error(self, msg):
        line = self.s.count("\n", 0, self.i) + 1
        col = self.i - self.s.rfind("\n", 0, self.i)
        raise Json5Error(f"{self.source}:{line}:{col}: {msg}")

    def skip(self):
        s, n = self.s, self.n
        while self.i < n:
            c = s[self.i]
            if c in " \t\r\n\ufeff\u2028\u2029":
                self.i += 1
            elif c == "/" and self.i + 1 < n and s[self.i + 1] == "/":
                j = s.find("\n", self.i)
                self.i = n if j < 0 else j + 1
            elif c == "/" and self.i + 1 < n and s[self.i + 1] == "*":
                j = s.find("*/", self.i + 2)
                if j < 0:
                    self.error("unterminated block comment")
                self.i = j + 2
            else:
                return

    def parse(self):
        self.skip()
        value = self.value()
        self.skip()
        if self.i != self.n:
            self.error(f"trailing content: {self.s[self.i:self.i + 40]!r}")
        return value

    def value(self):
        self.skip()
        if self.i >= self.n:
            self.error("unexpected end of input")
        c = self.s[self.i]
        if c == "{":
            return self.obj()
        if c == "[":
            return self.arr()
        if c in "\"'":
            return self.string()
        if c.isdigit() or c in "+-.":
            return self.number()
        if IDENT_START.match(c):
            ident = self.ident()
            if ident == "true":
                return True
            if ident == "false":
                return False
            if ident == "null":
                return None
            if ident in ("Infinity", "NaN"):
                return ident
            self.error(f"unexpected identifier {ident!r} (code in data?)")
        self.error(f"unexpected character {c!r}")

    def ident(self):
        if not IDENT_START.match(self.s[self.i]):
            self.error("expected identifier")
        m = IDENT.match(self.s, self.i + 1)
        name = self.s[self.i:self.i + 1] + (m.group(0) if m else "")
        self.i += len(name)
        return name

    def number(self):
        m = NUM.match(self.s, self.i)
        if not m:
            self.error("bad number")
        raw = m.group(0)
        self.i += len(raw)
        low = raw.lower().lstrip("+-")
        if low.startswith("0x"):
            return int(raw, 16)
        if "." in raw or "e" in low:
            return float(raw)
        return int(raw)

    def string(self):
        quote = self.s[self.i]
        self.i += 1
        out = []
        s, n = self.s, self.n
        while True:
            if self.i >= n:
                self.error("unterminated string")
            c = s[self.i]
            if c == "\\":
                self.i += 1
                if self.i >= n:
                    self.error("unterminated escape")
                e = s[self.i]
                mapping = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
                if e in mapping:
                    out.append(mapping[e])
                    self.i += 1
                elif e == "u":
                    hexs = s[self.i + 1:self.i + 5]
                    if not re.fullmatch(r"[0-9a-fA-F]{4}", hexs):
                        self.error("bad unicode escape")
                    out.append(chr(int(hexs, 16)))
                    self.i += 5
                elif e == "x":
                    hexs = s[self.i + 1:self.i + 3]
                    if not re.fullmatch(r"[0-9a-fA-F]{2}", hexs):
                        self.error("bad hex escape")
                    out.append(chr(int(hexs, 16)))
                    self.i += 3
                elif e == "\n":
                    self.i += 1
                else:
                    out.append(e)
                    self.i += 1
            elif c == quote:
                self.i += 1
                return "".join(out)
            elif c == "\n":
                self.error("literal newline in string")
            else:
                out.append(c)
                self.i += 1

    def key(self):
        self.skip()
        if self.i >= self.n:
            self.error("unexpected end of input in object")
        c = self.s[self.i]
        if c in "\"'":
            return self.string()
        m = re.compile(r"[A-Za-z0-9_$\u00a0-\uffff]+").match(self.s, self.i)
        if m:
            self.i += len(m.group(0))
            return m.group(0)
        self.error(f"bad object key {c!r}")

    def obj(self):
        self.i += 1
        result = {}
        while True:
            self.skip()
            if self.i >= self.n:
                self.error("unterminated object")
            if self.s[self.i] == "}":
                self.i += 1
                return result
            k = self.key()
            self.skip()
            if self.i >= self.n or self.s[self.i] != ":":
                self.error("expected ':'")
            self.i += 1
            result[k] = self.value()
            self.skip()
            if self.i < self.n and self.s[self.i] == ",":
                self.i += 1
                continue
            if self.i < self.n and self.s[self.i] == "}":
                self.i += 1
                return result
            self.error("expected ',' or '}'")

    def arr(self):
        self.i += 1
        result = []
        while True:
            self.skip()
            if self.i >= self.n:
                self.error("unterminated array")
            if self.s[self.i] == "]":
                self.i += 1
                return result
            result.append(self.value())
            self.skip()
            if self.i < self.n and self.s[self.i] == ",":
                self.i += 1
                continue
            if self.i < self.n and self.s[self.i] == "]":
                self.i += 1
                return result
            self.error("expected ',' or ']'")


def loads(text, source="<string>"):
    return Parser(text, source).parse()
