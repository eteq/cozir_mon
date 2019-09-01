import analogio
import board

__all__ = ['get_battery_voltage']

def get_battery_voltage():
    a = analogio.AnalogIn(board.BATTERY)
    try:
        return a.reference_voltage * a.value * 2**-15  # 16-bit, then multiply by 2
    finally:
        a.deinit()