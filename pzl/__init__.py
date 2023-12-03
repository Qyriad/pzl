import argparse
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import re
import sys
from typing import ClassVar, Generic, Literal, Optional, TypeVar

import psutil
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
    "pid",
    "ppid",
    "status",
    "terminal",
    "username",
    "cpu_percent",
]

def abbrev_home(path: str) -> str:
    without_prefix = path.removeprefix(str(Path.home()))
    if without_prefix != path:
        return f"~{without_prefix}"
    return path

T = TypeVar("T")
@dataclass
class ProcessField(Generic[T]):
    """ Generic and base class for process fields. """

    # Set from None in __post_init__ if necessary.
    column_title: ClassVar[str] = None # type: ignore

    name: str
    value: T | psutil.Error

    def __post_init__(self):
        if type(self).column_title is None:
            type(self).column_title = self.name

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
                return Text.from_markup(f"[dim]<{type(e).__name__}>")
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
class Cmdline0Field(ProcessField[str | None]):
    name: ClassVar[str] = "cmdline0"

    def __str__(self):
        match self.value:
            case str(string):
                return abbrev_home(string)

        return super().__str__()

@dataclass
class TerminalField(ProcessField[str]):

    name: ClassVar[str] = "terminal"

    def __str__(self):
        match self.value:
            case str(string):
                return string.removeprefix("/dev/")

        return super().__str__()

@dataclass
class ProcInfo:

    pid: ProcessField[int]
    ppid: ProcessField[int]
    name: ProcessField[str]
    cmdline: ProcessField[list[str]] = field(repr=False)
    exe: ProcessField[Path | None]
    terminal: TerminalField
    status: ProcessField[str]
    username: ProcessField[str]

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
            case [cmd, *_]:
                return Cmdline0Field(cmd)
            case []:
                return Cmdline0Field(None)
            case None | psutil.Error() as value:
                return Cmdline0Field(value)

        # Should be unreachable.
        assert False, f"{self.cmdline.value} is not a list, None, or psutil.Error (unreachable)"

    @property
    def parent_name(self) -> Optional[ProcessField[str]]:
        try:
            match self.ppid.value:
                case int(ppid):
                    parent = psutil.Process(ppid)
                    field = ProcessField(name="parent", value=parent.name())
                    field.format = lambda: Text.from_markup(f"[dim]({field.value})")
                    return field

            return None
        except psutil.Error as e:
            return ProcessField[str](name="parent", value=e)

    def format_row(self, fields=None, extras=None) -> list[Text]:
        if not fields:
            fields = "pid ppid parent_name name cmdline0 exe terminal status".split()

        if not extras:
            extras = []

        fields.extend(extras)

        row = []
        for field in fields:
            try:
                value = getattr(self, field)
                formatted = value.format()
            except Exception as e:
                e.add_note(f"(while formatting {field} on {self})")
                raise

            if field == self._matched_field:
                row.append(Text.from_markup(f"[bold]{formatted}"))
            else:
                row.append(formatted)

        return row

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
            if matcher_value.search(str(field_value)):
                proc._matched_field = field_name
                matched_processes.append(proc)

    extras = defaultdict(dict)
    for proc in matched_processes:
        extras["username"][proc.username.value] = proc.pid.value

    table = Table(box=None, expand=False)
    for col in ["pid", "parent", "", *"name cmdline0 exe terminal status".split()]:
        table.add_column(col, overflow="fold")

    extra_columns = []
    if len(extras["username"].keys()) > 1:
        extra_columns.append("username")
        table.add_column("username")

    sorted_procs = sorted(matched_processes, key=ProcInfo.sorter)
    for proc in sorted_procs:
        table.add_row(*proc.format_row(extras=extra_columns))

    Console().print(table)


if __name__ == "__main__":
    sys.exit(main())
