VIVADO = vivado
SCP = scp
SSH = ssh
TARGET_IP = 192.168.14.5

SRC_FILES = $(wildcard ../*.sv)

all: ip rtl

ip: build/ip/proj/ip.xpr

rtl: ip build/rtl/rtl.xpr

build/rtl/rtl.xpr: $(SRC_FILES) ./tcl/build.tcl ./constraints/*.xdc
	mkdir -p build/logs
	$(VIVADO) -mode batch -nojournal -source ./tcl/build.tcl -log ./build/logs/build_log.txt

build/ip/proj/ip.xpr: ../config.sv tcl/create_ip.tcl
	mkdir -p build/logs
	$(VIVADO) -mode batch -nojournal -source ./tcl/create_ip.tcl -log ./build/logs/create_ip_log.txt

open_rtl_project: rtl
	$(VIVADO) -nojournal -nolog ./build/rtl/rtl.xpr

open_ip_project: ip
	$(VIVADO) -nojournal -nolog ./build/ip/proj/ip.xpr

program: all
	$(SCP) bitstream/tims_fpga.bit tims@$(TARGET_IP):/home/tims/data/bit/

clean:
	rm -rf build
	rm -rf .Xil

../config.sv: ../../config.py
	python ../../config.py
