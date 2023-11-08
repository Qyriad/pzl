{
  buildPythonPackage,
  buildPythonApplication,
  fetchPypi,
  setuptools,
  wheel,
  psutil,
  tabulate,
  rich,
}:

let
  inherit (builtins) attrValues readFile fromTOML;

  pname = "pzl";
  version = (fromTOML (readFile ./pyproject.toml)).project.version;

in
  buildPythonApplication {
    inherit pname version;
    src = ./.;
    format = "pyproject";

    pythonImportsCheck = [
      pname
    ];

    nativeBuildInputs = [
      setuptools
      wheel
    ];

    propagatedBuildInputs = [
      psutil
      tabulate
      rich
    ];
  }
