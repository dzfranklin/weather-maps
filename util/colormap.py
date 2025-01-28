import colorsys
import html
from typing import Optional, NamedTuple


class Entry(NamedTuple):
    v: Optional[float]
    h: int
    s: int
    l: int
    a: int

    @classmethod
    def parse(cls, line: str) -> Optional['Entry']:
        if line.strip() == "" or line.strip().startswith("#"):
            return None

        parts = [p.strip() for p in line.strip().split(",")]

        if parts[0] == "nv":
            v = None
        else:
            v = float(parts[0])

        h = int(parts[1])
        s = int(parts[2])
        l = int(parts[3])

        a = 255
        if len(parts) > 4:
            a = int(parts[4])

        return cls(v, h, s, l, a)

    def serialize(self) -> str:
        v_part = str(self.v) if self.v is not None else "nv"
        if self.a == 0:
            parts = [v_part, "0", "0", "0", "0"]
        elif self.a == 255:
            parts = [v_part, str(self.h), str(self.s), str(self.l)]
        else:
            parts = [v_part, str(self.h), str(self.s), str(self.l), str(self.a)]
        return ",".join(parts)

    def gdal_format(self) -> str:
        r, g, b = hsl_to_rgb(self.h, self.s, self.l)
        return ",".join([
            str(self.v) if self.v is not None else "nv",
            str(r),
            str(g),
            str(b),
            str(self.a)
        ])

    def css_color(self) -> str:
        hsl_part = ' '.join([str(self.h if self.h != 360 else 0) + 'deg', str(self.s) + '%', str(self.l) + '%'])
        if self.a == 255:
            return 'hsl(' + hsl_part + ')'
        else:
            return ('hsl(' + hsl_part +
                    ' / ' + _strip_trailing_zero_decimal(str(round(float(self.a) / 255.0, 2))) + '%' + ')')

    def pretty_value(self) -> str:
        if self.v is None:
            return "N/A"
        else:
            return _strip_trailing_zero_decimal(f'{self.v:,}')


class Colormap:
    doc_comment: Optional[str]
    units: str
    entries: list[Entry]

    def __init__(self, doc_comment: Optional[str], units: str, entries: list[Entry]):
        self.doc_comment = doc_comment
        self.units = units
        self.entries = entries

    @classmethod
    def parse(cls, source: str) -> 'Colormap':
        doc_comment: Optional[str] = None
        units: Optional[str] = None
        entries: list[Entry] = []

        started = False
        for line in source.splitlines():
            entry = Entry.parse(line)
            if entry:
                if not started:
                    started = True
                entries.append(entry)
            elif line.strip().startswith("#"):
                inner = line.strip().strip("#").strip()
                if inner.startswith("units:"):
                    units = inner[len("units:"):].strip()
                elif not started:
                    if doc_comment is None:
                        doc_comment = ""
                    doc_comment += line.strip()[1:] + "\n"

        if doc_comment is not None:
            doc_comment = doc_comment.strip("\n")
            if doc_comment.strip() == "":
                doc_comment = None

        if units is None:
            raise RuntimeError("expected colormap source to specify units")

        return cls(doc_comment, units, entries)

    @classmethod
    def read(cls, path: str) -> 'Colormap':
        with open(path, "r") as f:
            return cls.parse(f.read())

    def gdal_format(self) -> str:
        out = ""

        if self.doc_comment is not None:
            out += self.doc_comment + "\n\n"

        out += "# units: " + self.units + "\n\n"

        for entry in self.entries:
            out += entry.gdal_format() + "\n"

        return out

    def serialize(self) -> str:
        out = ""

        if self.doc_comment:
            out += "\n".join(["# " + l for l in self.doc_comment.split("\n")]) + "\n\n"

        out += "# units: " + self.units + "\n\n"

        for entry in self.entries:
            out += entry.serialize() + "\n"

        return out

    def html_legend(self) -> str:
        entry_style = ('vertical-align: top; ' +
                       'height: 1.3em; ' +
                       'display: inline-flex; ' +
                       'align-items: center; ' +
                       'gap: 0.3em; ' +
                       'margin: 0.4em 0.3em; ')

        out = ""

        if self.doc_comment is not None:
            out += _escaped_html_comment(self.doc_comment)

        out += '<span style="' + entry_style + '">' + html.escape(self.units) + '</span>\n'

        for entry in self.entries:
            out += ('<span style="' + entry_style + '">')

            out += '<span class="legend-layer-content" style="'
            out += ('display: inline-block; ' +
                    'width: 10px; ' +
                    'height: calc(100% - 2px); ' +
                    'border: 1px solid #6d6d6d; ')
            out += 'background-color: ' + entry.css_color() + '; '
            out += '"></span>'

            out += '<span>' + html.escape(entry.pretty_value()) + '</span>'

            out += '</span>\n'

        return out


def html_legend(path: str) -> str:
    return Colormap.read(path).html_legend()


def rgb_to_hsl(r: int, g: int, b: int) -> tuple[int, int, int]:
    hls_pct = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    h = min(max(int(round(hls_pct[0] * 360.0)), 0), 360)
    l = min(max(int(round(hls_pct[1] * 100.0)), 0), 100)
    s = min(max(int(round(hls_pct[2] * 100.0)), 0), 100)
    return h, s, l


def hsl_to_rgb(h: int, s: int, l: int) -> tuple[int, int, int]:
    rgb_pct = colorsys.hls_to_rgb(h / 360.0, l / 100.0, s / 100.0)
    r = min(max(int(round(rgb_pct[0] * 255.0)), 0), 255)
    g = min(max(int(round(rgb_pct[1] * 255.0)), 0), 255)
    b = min(max(int(round(rgb_pct[2] * 255.0)), 0), 255)
    return r, g, b


def _strip_trailing_zero_decimal(num: str) -> str:
    if "." in num:
        num = num.rstrip("0").rstrip(".")
    return num


def _escaped_html_comment(contents: str) -> str:
    while "--" in contents:
        contents = contents.replace("--", "-")

    if "\n" in contents:
        return "<!--\n" + "\n".join(["  " + l for l in contents.split("\n")]) + "\n-->"
    else:
        return "<!-- " + contents.strip() + " -->"
