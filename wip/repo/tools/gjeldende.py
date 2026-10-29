"""Prints the law of Norway as it stood on a given day, read from this repository's history.

    python tools/gjeldende.py 2022-05-31 grunnloven 63        # Grunnloven § 63 the day before the 2022 amendment
    python tools/gjeldende.py 2022-06-01 grunnloven 63        # the same paragraph, as amended
    python tools/gjeldende.py 2020-01-01 grunnlova 120-a      # the nynorsk text; '120-a' or 'paragraf-120-a'
    python tools/gjeldende.py 2019-01-01 personopplysningsloven   # the whole act on 1 January 2019
    python tools/gjeldende.py --law 2020-01-01 grunnloven 49  # also name the decision behind that wording

A thin wrapper around tools/on.py: the version is chosen by each commit's `In-force:` trailer, never by its commit
date, and branches named wip* are ignored. A bare paragraph number (`63`, `12-a`) means the file `paragraf-063.md`
(`paragraf-012-a.md`). Standard library only.
"""
import re
import runpy
import sys
from pathlib import Path


def paragraph(unit: str) -> str:
    m = re.fullmatch(r'(\d+)(?:[- ]?([a-z]))?', unit)
    if not m:
        return unit
    return 'paragraf-%03d' % int(m.group(1)) + ('-' + m.group(2) if m.group(2) else '')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    args = [a for a in sys.argv[1:] if a != '--law']
    if len(args) == 3:
        i = len(sys.argv) - 1 - sys.argv[::-1].index(args[2])
        sys.argv[i] = paragraph(args[2])
    sys.argv[0] = str(Path(__file__).with_name('on.py'))
    runpy.run_path(sys.argv[0], run_name='__main__')
