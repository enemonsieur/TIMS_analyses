#!/usr/bin/env bash

# real-time kernel
git clone https://github.com/khalednasr/rpi5-6.14-rt-kernel.git
cd rpi5-6.14-rt-kernel
bash install.sh
cd ..
rm -rf rpi5-6.14-rt-kernel

# display server and window manager
sudo apt install -y lightdm openbox
sudo systemctl set-default graphical.target

# autologin
sudo sed -i "s/#autologin-user=/autologin-user=$USER/g" /etc/lightdm/lightdm.conf
sudo sed -i "s/#xserver-command=X/xserver-command=X -nocursor -s 0 dpms/g" /etc/lightdm/lightdm.conf

# boot config
sudo cp ~/tims/scripts/pi/cmdline.txt /boot/firmware/
sudo cp ~/tims/scripts/pi/config.txt /boot/firmware/

# bitstream
mkdir ~/tims_bin
cp ~/tims/fpga/vivado/bitstream/tims_fpga.bit ~/tims_bin

# FPGA loader
sudo apt install -y openfpgaloader

# egui
sudo apt install -y libxcb-render0-dev libxcb-shape0-dev libxcb-xfixes0-dev libxkbcommon-dev libssl-dev libxkbcommon-x11-0

# audio
sudo apt install -y libasound2-dev
