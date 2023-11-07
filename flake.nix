{
  inputs = {
    nixpkgs.url = "nixpkgs";
    flake-utils.url = "flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let

        pkgs = import nixpkgs { inherit system; };
        inherit (builtins) attrValues;

        pzl = pkgs.callPackage ./. { };

      in {
        packages.default = pzl;
        devShells.default = pkgs.mkShell {
          inputsFrom = [
            pzl
          ];

          packages = attrValues {
            inherit (pkgs)
              pyright
            ;
          };
        };
      }

    ) # eachDefaultSystem

  ;# outputs
}
