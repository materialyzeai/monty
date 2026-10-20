[![GitHub license](https://img.shields.io/github/license/materialyzeai/monty)](https://github.com/materialyzeai/monty/blob/main/LICENSE.rst)
[![Lint](https://github.com/materialyzeai/monty/actions/workflows/lint.yml/badge.svg)](https://github.com/materialyzeai/monty/actions/workflows/lint.yml)
[![Test](https://github.com/materialyzeai/monty/actions/workflows/test.yml/badge.svg)](https://github.com/materialyzeai/monty/actions/workflows/test.yml)
[![Downloads](https://static.pepy.tech/badge/monty)](https://pepy.tech/project/monty)
[![codecov](https://codecov.io/gh/materialyzeai/monty/branch/main/graph/badge.svg)](https://codecov.io/gh/materialyzeai/monty)

# Monty: Python Made Even Easier

Monty is the missing complement to Python. It implements supplementary
utilities that are not part of the standard library: transparent support for
compressed files, JSON/YAML/msgpack serialization of arbitrary objects, design
patterns such as `cached_class`, deprecation helpers, and many more.

Python comes with "batteries included", but in building several large
scientific frameworks (most notably [pymatgen](https://pymatgen.org)), we found
ourselves repeatedly writing the same small utilities. Monty collects these
into a single, well-tested, dependency-light library. Where the standard
library has since caught up, Monty delegates to it.

Monty supports Python 3.11+.

## Installation

```bash
pip install monty
# or
uv add monty
```

Optional extras pull in dependencies for specific features:

| Extra | Enables |
|---|---|
| `json` | Serialization of numpy, pandas, pint, pydantic, torch and bson objects |
| `serialization` | msgpack support in `dumpfn`/`loadfn` |
| `multiprocessing` | `imap_tqdm` progress bars |
| `dev` | IPython-based `install_excepthook` |
| `optional` | All of the above |

```bash
pip install "monty[optional]"
```

## Highlights

**Transparent compressed I/O.** `zopen` opens plain, `.gz`, `.bz2`, `.xz` and
`.lzma` files with one call; `reverse_readline` reads large files from the end.

```python
from monty.io import reverse_readline, zopen

with zopen("OUTCAR.gz", mode="rt", encoding="utf-8") as f:
    for line in reverse_readline(f):
        if "TOTAL-FORCE" in line:
            break
```

**Serialization of arbitrary objects.** Subclass `MSONable` to get
`as_dict()`/`from_dict()` and JSON round-tripping for free; `dumpfn`/`loadfn`
pick the format (JSON, JSON lines, YAML, msgpack) and compression from the
file extension.

```python
from monty.json import MSONable
from monty.serialization import dumpfn, loadfn


class Calculation(MSONable):
    def __init__(self, name: str, energy: float):
        self.name = name
        self.energy = energy


dumpfn(Calculation("relax", -3.42), "calc.json.gz")
calc = loadfn("calc.json.gz")  # -> Calculation instance
```

**Scratch directories.** `ScratchDir` runs a block in a temporary directory
and copies results back on exit.

```python
from monty.tempfile import ScratchDir

with ScratchDir(".", copy_from_current_on_enter=True, copy_to_current_on_exit=True):
    ...  # run an expensive calculation
```

**Development helpers.** Mark deprecations with an optional removal deadline,
and guard code paths on optional dependencies.

```python
from monty.dev import deprecated, requires

try:
    import torch
except ImportError:
    torch = None


@deprecated(replacement="new_func", deadline=(2028, 1, 1))
def old_func(): ...


@requires(torch is not None, "torch is required for this function.")
def train(): ...
```

Other modules include `monty.design_patterns` (`cached_class`, `singleton`),
`monty.functools` (`lazy_property`, `return_if_raise`, `timeout`),
`monty.shutil` (`compress_dir`, `decompress_dir`, `gzip_dir`),
`monty.os.path` (`zpath`, `find_exts`), `monty.re` (`regrep`) and
`monty.collections` (`frozendict`, `AttrDict`, `tree`).

See the [official docs](https://materialyzeai.github.io/monty) for the full API.

## Development

```bash
git clone https://github.com/materialyzeai/monty.git
cd monty
uv sync --all-extras
uv run pytest
uv run ruff check src && uv run ruff format src
uv run mypy -p monty
```
