{
  inputs = {
    nixpkgs.url = "nixpkgs";
    flake-utils.url = "flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = import nixpkgs { inherit system; };

      pzl = pkgs.callPackage ./package.nix { };

    in {
      packages.default = pzl;

      devShells.default = pkgs.mkShell {
        inputsFrom = [ pzl ];

        packages = [
          pkgs.pyright
          pkgs.python3Packages.black
        ];
      };

    }) # eachDefaultSystem

  ;# outputs
}
