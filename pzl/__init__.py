import argparse
import builtins
from collections.abc import Iterator
from dataclasses import dataclass
import itertools
from pathlib import Path
import re
import sys
from typing import Any, ClassVar, Callable, Generic, Literal, Optional, Union, TypeVar

import psutil
import rich, rich.text, rich.table, rich.console
from rich.align import Align
from rich.text import Text
from rich.table import Table
from rich.console import Console
from rich.columns import Columns

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

def abbrev_home(path: str) -> str:
    without_prefix = path.removeprefix(str(Path.home()))
    if without_prefix != path:
        return f"~{without_prefix}"
    return path

T = TypeVar("T")
@dataclass
class ProcessField(Generic[T]):
    """ Generic and base class for process fields. """

    name: str
    value: T | psutil.Error

    def __lt__(self, other):
        return self.value < other.value

    def __str__(self):

        match self.value:
            case psutil.Error() as e:
                return type(e).__name__

            case None:
                return ""

        return str(self.value)

    def format(self) -> Text:
        match self.value:
            case psutil.Error() as e:
                return Text.from_markup(f"[dim]{type(e).__name__}")
            case None:
                return Text.from_markup(f"[dim]none")

        markup = ""
        if self.name == "pid":
            markup = "[cyan]"

        return Text.from_markup(f"{markup}{self}")

    @classmethod
    def for_name(cls, name: str) -> type:
        for subcls in cls.__subclasses__():
            if subcls.name == name:
                return subcls

        def process_field_for_name(value):
            return cls(name, value)

        return process_field_for_name # type: ignore

@dataclass
class ParentField(ProcessField):
    name: ClassVar[str] = "ppid"
    value: int | None

    #def format(self):
    #    # Try to get the parent process.
    #    parent = psutil.Process(self.value)
    #    pname = parent.name()
    #    if pname:
    #        subgrid = Table.grid(expand=True)
    #        subgrid.add_column(justify="left")
    #        subgrid.add_column(justify="right")
    #        subgrid.add_row(Text.from_markup(f"[bright]{self.value}"), Text.from_markup(f"[dim] ({pname})"))
    #        return subgrid
    #    else:
    #        return str(self)

@dataclass
class Cmdline0Field(ProcessField):
    name: ClassVar[str] = "cmdline0"
    value: str | None | psutil.Error

    def __str__(self):
        match self.value:
            case str(string):
                return abbrev_home(string)

        return super().__str__()

@dataclass
class TerminalField(ProcessField):

    name: ClassVar[str] = "terminal"

    value: str | None | psutil.Error

    def __str__(self):
        match self.value:
            case str(string):
                return string.removeprefix("/dev/")

        return super().__str__()

T = TypeVar("T")
ProcField = Union[T, psutil.Error]
OptionalProcField = Union[T, psutil.Error, None]

@dataclass
class ProcInfo:

    pid: ProcessField[int]
    ppid: ParentField
    name: ProcessField[str]
    cmdline: ProcessField[list[str]]
    exe: ProcessField[Path | None]
    terminal: TerminalField
    status: ProcField[str]
    username: ProcField[str]

    _matched_field: Optional[str] = None

    @classmethod
    def from_process(cls, proc: psutil.Process):

        init_args = dict()

        init_args["pid"] = ProcessField[int](name="pid", value=proc.pid)

        for field in "name ppid cmdline exe terminal status username".split():
            getter = getattr(proc, field)
            try:
                value = getter()
            except psutil.Error as e:
                value = e

            init_args[field] = ProcessField.for_name(field)(value)

        return cls(**init_args)

    @classmethod
    def sorter(cls, proc):
        return (proc.username, proc.ppid, proc.terminal, proc.pid)

    @property
    def cmdline0(self) -> Cmdline0Field:

        match self.cmdline.value:
            case [cmd, *_rest]:
                return Cmdline0Field(cmd)
            case []:
                return Cmdline0Field(None)

        return Cmdline0Field(self.cmdline.value)

    @property
    def parent_name(self) -> Optional[ProcessField[str]]:
        match self.ppid.value:
            case int(ppid):
                parent = psutil.Process(ppid)
                field = ProcessField(name="parent", value=parent.name())
                field.format = lambda: Text.from_markup(f"[dim]({field.value})")
                return field

        return None

    def format_row(self, fields=None) -> list[Text]:
        if not fields:
            fields = "pid ppid parent_name name cmdline0 exe terminal status username".split()

        row = []
        for field in fields:
            try:
                value = getattr(self, field).format()
            except AttributeError as e:
                e.add_note(f"field {field} on {self} was None")
                raise

            if field == self._matched_field:
                row.append(Text.from_markup(f"[bold]{value}"))
            else:
                row.append(value)

        return row


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
    parser.add_argument("-g", "--group", help="Comma separated grouping hierarchy")

    args = parser.parse_args()
    #print(args)

    selector = args.selectors[0] # FIXME: for each selector.
    key, _, value = selector.partition("=")
    if not value:
        value = key
        key = "smart"

    if value.startswith("/"):
        matcher_value = re.compile(value[1:])
    else:
        matcher_value = re.compile(re.escape(value))

    processes = [ProcInfo.from_process(process) for process in psutil.process_iter(ATTRS)]

    matched_processes = []

    for field_name in "name cmdline0 exe".split():
        for proc in (p for p in processes if p not in matched_processes):
            field_value = getattr(proc, field_name)
            if not isinstance(field_value, psutil.Error) and field_value is not None:
                try:
                    if matcher_value.search(str(field_value)):
                        proc._matched_field = field_name
                        matched_processes.append(proc)
                except:
                    print(f"{proc=}, {field_value=}")
                    raise

    table = Table(box=None, expand=False)
    for col in ["pid", "parent", "", *"name cmdline0 exe terminal status username".split()]:
        table.add_column(col)

    #sorted_procs = sorted(matched_processes, key=lambda proc: (proc.username, proc.ppid, proc.terminal))
    sorted_procs = sorted(matched_processes, key=ProcInfo.sorter)
    for proc in sorted_procs:
        table.add_row(*proc.format_row())

    Console().print(table)

    return

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

if __name__ == "__main__":
    sys.exit(main())
