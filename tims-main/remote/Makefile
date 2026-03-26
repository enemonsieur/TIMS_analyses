all:
	mkdir -p build
	cd build; \
	cmake .. -DCMAKE_TOOLCHAIN_FILE=../cmake/gcc-arm-none-eabi.cmake -DCMAKE_BUILD_TYPE=Release; \
	make

program:
	sudo dfu-util -a 0 -i 0 -s 0x08000000:leave -D build/remote.bin

monitor:
	sudo tio /dev/ttyACM0

clean:
	rm -rf build

