"""IMU (Inertial Measurement Unit) drivers.

This package contains drivers for various IMU sensors used in robot navigation
and orientation tracking.

Supported IMUs:
    - BNO085: 9-DOF absolute orientation sensor with sensor fusion
"""

from .bno085 import BNO085Driver, IMUData

__all__ = ['BNO085Driver', 'IMUData']
