---
layout: default
title: monty.functools.md
nav_exclude: true
---

# monty.functools module

functools, especially backported from Python 3.

## *exception* monty.functools.TimeoutError(message)

Bases: `Exception`

Exception class for timeouts.

* **Parameters**
  **message** – Error message

## *class* monty.functools.lazy_property(func)

Bases: `object`

lazy_property descriptor

Used as a decorator to create lazy attributes. Lazy attributes
are evaluated on first use.

* **Parameters**
  **func** – Function to decorate.

### *classmethod* invalidate(inst, name)

Invalidate a lazy attribute.

This obviously violates the lazy contract. A subclass of lazy
may however have a contract where invalidation is appropriate.

## monty.functools.lru_cache(maxsize=128, typed=False)

Least-recently-used cache decorator, which is a backport of the same
function in Python >= 3.2.

If *maxsize* is set to None, the LRU features are disabled and the cache
can grow without bound.

If *typed* is True, arguments of different types will be cached separately.
For example, f(3.0) and f(3) will be treated as distinct calls with
distinct results.

Arguments to the cached function must be hashable.

View the cache statistics named tuple (hits, misses, maxsize, currsize)
with f.cache_info().  Clear the cache and statistics with f.cache_clear().
Access the underlying function with f.**wrapped**.

See:  [http://en.wikipedia.org/wiki/Cache_algorithms#Least_Recently_Used](http://en.wikipedia.org/wiki/Cache_algorithms#Least_Recently_Used)

## monty.functools.prof_main(main)

Decorator for profiling main programs.

Profiling is activated by prepending the command line options
supported by the original main program with the keyword prof.
.. rubric:: Example

$ script.py arg –foo=1

becomes

> $ script.py prof arg –foo=1

The decorated main accepts two new arguments:

> prof_file: Name of the output file with profiling data
> ```none
> If not given, a temporary file is created.
> ```
> sortby: Profiling data are sorted according to this value.
> ```none
> default is “time”. See sort_stats.
> ```

## monty.functools.return_if_raise(exception_tuple, retval_if_exc, disabled=False)

Decorator for functions, methods or properties. Execute the callable in a
try block, and return retval_if_exc if one of the exceptions listed in
exception_tuple is raised (se also `return_node_if_raise`).

Setting disabled to True disables the try except block (useful for
debugging purposes). One can use this decorator to define properties.

Example:

```default
@return_if_raise(ValueError, None)
def return_none_if_value_error(self):
    pass

@return_if_raise((ValueError, KeyError), "hello")
def another_method(self):
    pass

@property
@return_if_raise(AttributeError, None)
def name(self):
    "Name of the object, None if not set."
    return self._name
```

## monty.functools.return_none_if_raise(exception_tuple, \*, retval_if_exc=None, disabled=False)

This decorator returns None if one of the exceptions is raised.

> @return_none_if_raise(ValueError)
> def method(self):

## *class* monty.functools.timeout(seconds=1, error_message=’Timeout’)

Bases: `object`

Timeout function. Use to limit matching to a certain time limit. Note that
this works only on Unix-based systems as it uses signal. Usage:

try:

```none
with timeout(3):

    do_stuff()
```

except TimeoutError:

```none
do_something_else()
```

* **Parameters**
  * **seconds** (*int*) – Allowed time for function in seconds.
  * **error_message** (*str*) – An error message.

### handle_timeout(signum, frame)

* **Parameters**
  * **signum** – Return signal from call.
  * **frame** –