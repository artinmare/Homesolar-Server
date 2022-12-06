import numpy as np
from scipy import interpolate

# Status MOSFET saat Discharge
MOSFET_Discharge_St = ["OFF", "ON", "Cell Overdischarge", "Overcurrent", "4-Unknown", "Pack Overdischarge",
                       "Battery Overheat", "MOSFET Overheat", "Abnormal Current", "Battery Not Detected",
                       "PCB Overheat", "Charge MOSFET Turned On", "Shortcircuit", "Discharge MOSFET Abnormality",
                       "Start exception", "Manual OFF"]
# Status MOSFET saat Charge
MOSFET_Charge_St = ["OFF", "ON", "Cell Overcharge", "Overcurrent", "Battery Full", "Pack Overvoltage",
                    "Battery Overheat", "MOSFET Overheat", "Abnormal Current", "Battery Not Detected",
                    "PCB Overheat", "11-Unknown", "12-Unknown", "Discharge MOSFET Abnormality", "14", "Manual OFF"]
# Status Balancing
Bal_St = ["OFF", "Exceeding Trigger Limit", "Voltage Diff Too High", "Overheat", "ACTIVE",
          "5-Unknown", "6-Unknown", "7-Unknown", "8-Unknown", "9-Unknown", "PCB Overheat"]


def find_nearest(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return idx


class ManualSoC:
    y = [2.8, 3.6, 3.7, 3.72, 3.75, 3.78, 3.8, 3.9, 3.95, 4.0, 4.2]
    x = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

    xarr = np.array(x)
    yarr = np.array(y)

    splines = interpolate.splrep(xarr, yarr)
    x_vals = np.linspace(xarr.min(), xarr.max(), 101 * 10)
    y_vals = interpolate.splev(x_vals, splines)

    def get_soc(self, volt):
        x = find_nearest(self.y_vals, volt)
        return self.x_vals[x]
