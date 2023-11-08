import argparse
from collections.abc import Iterator
from dataclasses import dataclass
import itertools
import re
import sys
from typing import Any, Callable, Literal, Optional, Union

import psutil
import rich, rich.text, rich.table, rich.console
from rich.text import Text
from rich.table import Table
from rich.console import Console

@dataclass
class Selector:
    key: Literal["default", "name", "exe", "pid", "term", "parent"]
    value: str | int

ATTRS = [
    "cmdline",
    "exe",
    "name",
    "cpu_percent",
    "pid",
    "ppid",
    "status",
    "terminal",
    "username",
]

class Process(psutil.Process):

    def pid_(self):
        return self.pid

    def cmdline0(self):
        try:
            return self.cmdline()[0]
        except IndexError:
            return None


def process_iter(*args, **kwargs) -> Iterator[Process]:
    return (Process(proc.pid) for proc in psutil.process_iter(*args, **kwargs))

@dataclass
class ProcMatch:

    #proc: Process
    #matched_value: str
    #matched_on: Union[Callable[[], str], Any]
    #match: re.Match
    #
    #def format(self) -> list[Text]:
    #
    #    proc = self.proc
    #
    #    columns = []
    #
    #    for field in proc.pid_, proc.name, proc.exe, proc.cmdline0:
    #
    #        if field == self.matched_on:
    #            print(f"{field=}, {self.matched_on=}")
    #            col = Text.from_markup(f"[bold]{field()}[/bold]")
    #        else:
    #            col = Text.from_markup(str(field()))
    #
    #        columns.append(col)
    #
    #    return columns

    pid: int
    matched_on: str


def proc_match(proc: Process, pattern: re.Pattern, match_on: Union[Callable[[], str], Any]) -> Optional[ProcMatch]:
    try:
        if callable(match_on):
            value = match_on()
        else:
            value = str(match_on)

        if value and (match := pattern.search(value)):
            #return ProcMatch(proc=proc, matched_value=value, matched_on=match_on, match=match)
            return ProcMatch(pid=proc.pid, matched_on=match_on.__name__) # XXX

    except psutil.AccessDenied:
        pass


def catch_as_none(function: Callable, *exceptions: type[Exception]):

    # By default catch `Exception` and subclasses..
    if not exceptions:
        exceptions = (Exception,)

    try:
        return function()
    except exceptions:
        return None


class ExceptNoneMeta(type):
    def __getitem__(self, key):
        return _ExceptNonePartial(exceptions=[key])

class _ExceptNonePartial(metaclass=ExceptNoneMeta):
    """ A partially applied `except_none`. """

    def __init__(self, exceptions: Optional[list[type[Exception]]] = None, function : Optional[Callable] = None):
        if exceptions is None:
            exceptions = []
        self.exceptions = list(exceptions)
        self.function = function

    def __call__(self, function: Callable):
        return except_none(function, *self.exceptions)


class except_none(metaclass=ExceptNoneMeta):
    """ Converts the specified exceptions to None. """

    def __init__(self, function: Optional[Callable] = None, *exceptions: type[Exception]):
        self.function = function
        self.exceptions = list(exceptions)

    @classmethod
    def on(cls, *exceptions: type[Exception]):
        return _ExceptNonePartial(exceptions=list(exceptions))

    def __call__(self, *args, **kwargs):
        if self.function:
            return self.function(*args, **kwargs)
        else:
            function = args[0]
            args = args[1:]
            return function(*args, **kwargs)


def proc_map(proc, attrs=ATTRS):

    proc_dict = proc.as_dict(attrs)
    proc_dict["_self"] = proc

    try:
        proc_dict["cmdline0"] = proc_dict["cmdline"][0]
    except IndexError:
        pass

    return proc_dict

def main():
    parser = argparse.ArgumentParser("pzl")
    parser.add_argument("selectors", type=str, action="append", nargs="*")
    parser.add_argument("-s", dest="selectors", type=str, action="append")
    parser.add_argument("-p", "--parent", dest="parent_selector")

    args = parser.parse_args()
    print(args)

    selector = args.selectors[0] # FIXME: for each selector.
    key, _, value = selector.partition("=")
    if not value:
        value = key
        key = "default"

    if value.startswith("/"):
        value = re.compile(value[1:])
    else:
        value = re.compile(re.escape(value))

    matching_procs = []
    for proc in map(proc_map, process_iter(ATTRS)):
        if value.search(proc["name"]):
            proc["_matched"] = "name"
            matching_procs.append(proc)

    table = Table(box=None)
    for col in "pid name exe cmdline0 terminal".split():
        table.add_column(col)

    for proc in matching_procs:
        row = []
        for key in "pid name exe cmdline0 terminal".split():
            # If that field is None, try to get it by method call,
            # both in case it succeeds this time, and so we can grab the error.
            if proc[key] is None:
                try:
                    field_getter = getattr(proc["_self"], key)
                    field = field_getter()
                except psutil.Error as e:
                    execption_name = type(e).__name__
                    field = f"[italic dim]<{execption_name}>[/]"
            else:
                field = str(proc[key])

            if key == proc.get("_matched"):
                row.append(Text.from_markup(f"[bold]{str(field)}[/bold]"))
            else:
                if field is not None:
                    row.append(Text.from_markup(field))
                else:
                    row.append(Text.from_markup("[italic dim]<none>[/]"))
        table.add_row(*row)

    Console().print(table)

    return

    ignore_access = except_none[psutil.AccessDenied]

    # Try name, then cmdline[0], then exe, then cmdline[:].
    #matching_name = (proc for proc in psutil.process_iter(ATTRS) if value.search(proc.name()))
    #matching_exe = (proc for proc in psutil.process_iter(ATTRS) if ignore_access(lambda : value.search(proc.exe())))
    #matching_cmdline0 = (proc for proc in psutil.process_iter(ATTRS) if ignore_access(lambda : value.search(proc.cmdline()[0])))
    matching_name = filter(bool, (proc_match(proc, value, proc.name) for proc in process_iter(ATTRS)))
    matching_cmdline0 = filter(bool, (proc_match(proc, value, proc.cmdline0) for proc in process_iter(ATTRS)))

    #find_iter = itertools.chain(matching_name, matching_exe, matching_cmdline0)
    find_iter = itertools.chain(matching_name, matching_cmdline0)

    #all_found = []
    #if first := next(find_iter, None):
    #    all_found.append(first)
    #all_found.extend(list(find_iter))

    #table_rows = [match.format() for match in find_iter]

    table = Table(box=None)
    for col in "pid name exe cmdline".split():
        table.add_column(col)

    for match in find_iter:
        table.add_row(*match.format())

    Console().print(table)


if __name__ == "__main__":
    sys.exit(main())
