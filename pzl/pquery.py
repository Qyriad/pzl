import argparse
import json
import shlex

import psutil

def _process_to_json(process: psutil.Process, verbose=False) -> dict:
    """ A custom version of .as_dict(). """
    d = dict()

    d["pid"] = process.pid
    for field in "ppid status terminal username exe name cwd".split():
        try:
            value = getattr(process, field)()
            d[field] = value
            #if value is not None:
            #    d[field] = value
            #else:
            #    d[field] = None
        except psutil.AccessDenied:
            d[field] = "<AccessDenied>"

    complex_fields = ["cmdline"]
    if verbose:
        complex_fields.append("environ")
    for field in complex_fields:
        try:
            value = getattr(process, field)()
            # FIXME: make configurable
            if verbose:
                d[field] = value
            else:
                d[field] = [item for item in value if item]
        except psutil.AccessDenied:
            d[field] = "<AccessDenied>"

    return d

def _process_field_get(process: psutil.Process, field: str):
    return process.as_dict(attrs=[field])[field]

def main():
    parser = argparse.ArgumentParser("pq",
        description="Prints a newline separated list of PIDs that match all the supplied selectors",
    )
    selector_group = parser.add_mutually_exclusive_group(required=True)
    selector_group.add_argument("selectors", type=str, nargs="*", default="",
        help="A field name, an equals sign (`=`), and that field's value, to match on. "
        "Ex: `terminal=/dev/pts/11` "
    )
    selector_group.add_argument("-a", "--all", action="store_true")
    parser.add_argument("-j", "--json", action="store_true",
        help="Output all process fields as JSON, instead of printing PIDs",
    )
    parser.add_argument("-v", "--verbose", action="store_true",
        help="In JSON mode, include environment variables and empty cmdline arguments",
    )
    args = parser.parse_args()

    matching_processes = []

    if not args.all:
        selectors_split = [selector.split("=", maxsplit=1) for selector in args.selectors]
        selectors = dict(selectors_split)
        for process in psutil.process_iter():
            for key, value in selectors.items():
                if str(_process_field_get(process, key)) == value:
                    matching_processes.append(process)
    else:
        matching_processes = list(psutil.process_iter())

    if args.json:
        procs_json = [_process_to_json(proc, args.verbose) for proc in matching_processes]
        print(json.dumps(procs_json, indent=4))
    else:
        print("\n".join([str(proc.pid) for proc in matching_processes]))


if __name__ == "__main__":
    main()
