#!/usr/bin/env bash

# For wired ethernet internet sharing
sudo nmcli c m "Wired connection 1" ipv4.method auto
