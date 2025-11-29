---
layout: default
title: monty.re.md
nav_exclude: true
---

# monty.re module

Helpful regex based functions. E.g., grepping.

## monty.re.regrep(filename, patterns, reverse=False, terminate_on_match=False, postprocess=<class ‘str’>)

A powerful regular expression version of grep.

* **Parameters**
  * **filename** (*str*) – Filename to grep.
  * **patterns** (*dict*) – A dict of patterns, e.g.,
    {“energy”: r”energy\\(sigma->0\\)\\s+=\\s+([\\d-.]+)”}.
  * **reverse** (*bool*) – Read files in reverse. Defaults to false. Useful for
    large files, especially when used with terminate_on_match.
  * **terminate_on_match** (*bool*) – Whether to terminate when there is at
    least one match in each key in pattern.
  * **postprocess** (*callable*) – A post processing function to convert all
    matches. Defaults to str, i.e., no change.
* **Returns**

> {key1: [[[matches…], lineno], [[matches…], lineno],
> ```none
> [[matches…], lineno], …],
> ```
> key2: …}

For reverse reads, the lineno is given as a -ve number. Please note
that 0-based indexing is used.

* **Return type**
  A dict of the following form