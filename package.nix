{
  lib,
  python3,
}:

let
  inherit (builtins) readFile fromTOML;
  inherit (python3.pkgs)
    buildPythonApplication
    setuptools
    wheel
    psutil
    tabulate
    rich
    stringcase
  ;

  pname = "pzl";
  version = (fromTOML (readFile ./pyproject.toml)).project.version;
in
  buildPythonApplication {
    inherit pname version;
    src = lib.cleanSource ./.;
    format = "pyproject";

    pythonImportsCheck = [
      "pzl"
    ];

    nativeBuildInputs = [
      setuptools
      wheel
    ];

    propagatedBuildInputs = [
      psutil
      tabulate
      rich
      stringcase
    ];
  }
