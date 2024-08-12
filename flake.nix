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
          pkgs.python312
        ];
        env = {
          ANSIBLE_VAULT_PASSWORD_FILE = ".example_vault_pass.txt";
        };
      };
    };
}
