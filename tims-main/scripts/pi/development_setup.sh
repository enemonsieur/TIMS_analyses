#!/usr/bin/env bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

sudo apt update

# snap packages
sudo apt install -y snapd
sudo snap install nvim --classic --edge

# shell and configuration
sudo apt install -y fish
chsh -s /usr/bin/fish
gh repo clone config ~/config
mkdir -p ~/.config
cp -r ~/config/* ~/.config/
cp -r ~/config/.* ~/.config/
rm -rf ~/config

# python
sudo apt install -y python3-pip
sudo apt install -y python3-numpy python3-scipy
pip install bitstring --break-system-packages

# rust
curl --proto '=https' --tlsv1.2 https://sh.rustup.rs -sSf | sh
source "$HOME/.cargo/env.fish"
rustup component add rust-analyzer

bash $SCRIPT_DIR/deployment_setup.sh
