from itertools import chain

import framebuf
import machine


def scale(
    value: float, in_min: float, in_max: float, out_min: float, out_max: float
) -> float:
    """Scale a value."""
    return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


def _reverse_bits(byte: bytes) -> bytes:
    """Reverse bits in a byte."""
    result = 0

    # Iterate over each bit in the input byte
    for i in range(8):
        # Shift the result to the left
        result <<= 1

        # If the current bit is 1, set the least significant bit of the result to 1
        if byte & (1 << i):
            result |= 1

    return result


def _process_buffer(arr: bytearray) -> bytearray:
    """
    1. byte
    3. byte
    4. byte reversed
    2. byte reversed
    """
    # Split halves and zip them
    arr = list(zip(arr[0 : len(arr) // 2], arr[len(arr) // 2 : len(arr)]))
    arr = list(chain(*arr))

    new_arr = bytearray()

    for i in range(0, len(arr), 4):
        new_arr.append(arr[i])
        new_arr.append(arr[i + 2])
        new_arr.append(_reverse_bits(arr[i + 3]))
        new_arr.append(_reverse_bits(arr[i + 1]))

    return bytearray(reversed(new_arr))


class BusDisplay(framebuf.FrameBuffer):
    """Bustec BTM140.2 LED display class."""

    brightness_max = 40000
    brightness_min = 65535
    display_height = 16

    def __init__(
        self,
        sdi: int = 19,
        clk: int = 18,
        le: int = 21,
        oe: int = 20,
        width: int = 64,
        brightness: int = 100,
    ):
        """Initialize the display.
        
        Pins are interfacing MBI5039 LED driver.

        Args:
            sdi: (SDI) Data input pin.
            clk: Clock pin.
            le: Latch pin.
            oe: Output enable pin.
            width: Display width.
            brightness: Display brightness (0-100).
        """
        # Create buffer byte array.
        self.buffer = bytearray((self.display_height // 8) * width)

        super().__init__(
            memoryview(self.buffer), width, self.display_height, framebuf.MONO_VLSB
        )

        # Display parameters.
        self.brightness = int(
            scale(brightness, 0, 100, self.brightness_min, self.brightness_max)
        )

        # Pins configuration.
        self.le = machine.Pin(le, machine.Pin.OUT)
        self.oe = machine.PWM(machine.Pin(oe, machine.Pin.OUT))
        self.spi = machine.SPI(
            0,
            baudrate=1000000,
            polarity=1,
            phase=1,
            bits=8,
            firstbit=machine.SPI.MSB,
            sck=machine.Pin(clk),
            mosi=machine.Pin(sdi),
        )
        # PWM
        self.oe.freq(10000)  # original 1000
        self.oe.duty_u16(self.brightness_min)

    def set_brightness(self, value: int) -> None:
        """Brightness setter."""
        self.brightness = int(
            scale(value, 0, 100, self.brightness_min, self.brightness_max)
        )

    def on(self):
        """Set display ON."""
        self.oe.duty_u16(self.brightness)

    def off(self):
        """Set display OFF."""
        self.oe.duty_u16(65535)

    def write(self, show=True):
        """Writes data to the display."""

        self.spi.write(_process_buffer(self.buffer))

        # Tick the latch pin
        self.le.value(0)
        self.le.value(1)
        self.le.value(0)

        if show:
            self.on()
