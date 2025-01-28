#!/usr/bin/env python
import json

import colormap
from colormap import Colormap


def _main():
    import sys

    if len(sys.argv) != 2:
        print("Usage: pbpaste | convert_windy_colormap.py <units>")
        sys.exit(1)
    units = sys.argv[1]

    input_value = sys.stdin.read()
    parsed_input = json.loads(input_value)

    entries: list[colormap.Entry] = []
    for windy_entry in parsed_input:
        assert len(windy_entry) == 2
        assert(len(windy_entry[1]) == 4)
        assert isinstance(windy_entry[0], float) or isinstance(windy_entry[0], int)
        for n in windy_entry[1]:
            assert isinstance(n, int) and 0 <= n <= 255

        v = windy_entry[0]
        [r, g, b, a] = windy_entry[1]

        h, s, l = colormap.rgb_to_hsl(r, g, b)
        entry = colormap.Entry(v, h, s, l, a)
        entries.append(entry)

    cmap = Colormap("Based on a color scale from windy.com", units, entries)
    print(cmap.serialize(), end='')


if __name__ == "__main__":
    _main()
