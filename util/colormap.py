from collections import namedtuple

Value = namedtuple("Value", ["v", "r", "g", "b", "a"])


def html_legend(path: str) -> str:
    values: list[Value] = []
    with open(path, "r") as f:
        for line in f.readlines():
            parts = line.split(",")

            v = parts[0]

            r = int(parts[1])
            g = int(parts[2])
            b = int(parts[3])

            a = 1.0
            if len(parts) > 4:
                a = float(parts[4]) / 255.0

            values.append(Value(
                v=v,
                r=r,
                g=g,
                b=b,
                a=a,
            ))

    out = ""
    for v in values:
        if v.v == "nv":
            continue

        out += (
                    '<span style="height: 1.3em; display: inline-flex; align-items: center; gap: 0.2em; margin: 4px 2px;">' +
                    '<span style="' +
                    'background-color: rgba(' + str(v.r) + ',' + str(v.g) + ',' + str(v.b) + ',' + str(v.a) + '); ' +
                    'display: inline-block; width: 7px; height: 100%; border: 1px solid #282828;' +
                    '"></span>' +
                    '<span>' + v.v + '</span>' +
                    '</span>\n'
                    )
    return out
