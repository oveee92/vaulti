{
  description = "Mainly intended to provide development dependencies";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-24.05";
  };

  outputs =
    { self, nixpkgs }:
    let
      pkgs = nixpkgs.legacyPackages.${system};
      system = "x86_64-linux";
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        buildInputs = [
          pkgs.poetry
          (pkgs.python312.withPackages (python-pkgs: [
            python-pkgs.python-lsp-server
            python-pkgs.black
            python-pkgs.mypy
            python-pkgs.pylint
          ]))
        ];
      };
    };
}
