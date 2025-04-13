{
  lib,
  buildPythonApplication,
  setuptools,
  wheel,
  psutil,
  tabulate,
  rich,
  stringcase,
}: let
  pname = "pzl";
  version = (lib.importTOML ./pyproject.toml).project.version;
in buildPythonApplication {
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
