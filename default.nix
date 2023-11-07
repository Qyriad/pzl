{ python3Packages }:

let
  inherit (builtins) attrValues readFile fromTOML;

  pname = "pzl";
  version = (fromTOML (readFile ./pyproject.toml)).project.version;
in
  python3Packages.buildPythonApplication {
    inherit pname version;
    src = ./.;
    format = "pyproject";

    checkImports = [
      pname
    ];

    nativeBuildInputs = attrValues {
      inherit (python3Packages)
        setuptools
        wheel
      ;
    };

    propagatedBuildInputs = attrValues {
      inherit (python3Packages)
        psutil
      ;
    };
  }
