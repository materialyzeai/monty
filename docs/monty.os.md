---
layout: default
title: monty.os.md
nav_exclude: true
---

# monty.os package

Os functions, e.g., cd, makedirs_p.

## monty.os.cd(path)

A Fabric-inspired cd context that temporarily changes directory for
performing some tasks, and returns to the original working directory
afterwards. E.g.,

> with cd(“/my/path/”):
> ```none
> do_something()
> ```
* **Parameters**
  **path** – Path to cd to.

## monty.os.makedirs_p(path, \*\*kwargs)

Wrapper for os.makedirs that does not raise an exception if the directory
already exists, in the fashion of “mkdir -p” command. The check is
performed in a thread-safe way

* **Parameters**
  * **path** – path of the directory to create
  * **kwargs** – standard kwargs for os.makedirs
* [monty.os.path module](monty.os.path.md)
  * `find_exts()`
  * `zpath()`