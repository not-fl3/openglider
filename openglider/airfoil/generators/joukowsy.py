from typing import List
import cmath
import math

class JoukowskyAirfoil:
    '''the joukowsky airfoil is created by applieng the joukowsky transformation
       1 + 1 / z at a circle which passes 1 + 0j and has the center point in the
       second quatrant of the complex-plane.
       the joukowsky airfoil is used to get an analytic solution to the potential
       flow problem and is useful for the comparison to numeric methodes.'''

    def __init__(self, midpoint: complex) -> None:
        self.midpoint = midpoint

    def circle(self, num: int=100) -> list[complex]:
        '''A circle with center midpoint and passing 0j + 1'''

        def circle_val(phi: float) -> complex:
            math
            return self.midpoint + self.radius * math.e ** ((phi - self.beta) * 1j)

        phis = [2*math.pi*(i/(num-1)) for i in range(num)]
        return [circle_val(phi) for phi in phis]

    @property
    def radius(self) -> float:
        return abs(1 - self.midpoint)

    @property
    def beta(self) -> float:
        '''the angle between 0j + 1, the midpoint and a horizontal line'''
        return math.asin(self.midpoint.imag / self.radius)

    def zeta(self, z: complex) -> complex:
        '''maps a complex number z to the zeta-plane'''
        return z + 1 / z

    def dz_dzeta(self, z: complex) -> complex:
        '''d_z / d_zeta'''
        dzeta_dz = (1 - 1 / z**2)
        return 1. if dzeta_dz == 0 else 1 / dzeta_dz

    def z(self, zeta: complex) -> complex:
        '''maps a complex number zeta to the z-plane'''
        z = (zeta + cmath.sqrt(zeta ** 2 - 4)) / 2
        # if the point is inside the object
        mid = self.midpoint.imag / (1 - self.midpoint.real) * 1j
        if abs(z - mid) < abs(mid + 1):
            z = (zeta - cmath.sqrt(zeta ** 2 - 4)) / 2
        return z

    def coordinates(self, num: int=100) -> list[tuple[float, float]]:
        '''maps the z-circle to the zeta-plane which results in a joukowsky airfoil'''

        complex_coords = list(map(self.zeta, self.circle(num)))

        return [(c.real, c.imag) for c in complex_coords]

    def gamma(self, alpha: float) -> float:
        '''return the strength of the circulation to satisfy the kutta-condition
           for a given angle of attack alpha'''
        return 4 * math.pi * self.radius * math.sin(alpha + self.beta)

    def potential(self, z: complex, alpha: float) -> complex:
        '''return the potential of any point in the complex z-plane for a given
           angle of attack alpha'''
        W_inf = math.e ** (-1j * alpha) * (z - self.midpoint)
        W_dip = self.radius ** 2 * math.e ** (1j * alpha) * (1 / (z - self.midpoint))
        W_vort = 1j * self.gamma(alpha) / 2 / math.pi * cmath.log(z - self.midpoint)
        return W_inf + W_dip + W_vort

    def z_velocity(self, z: complex, alpha: float) -> complex:
        '''return the complex velocity of any point in the complex z-plane for
           a given angle of attack alpha'''
        Q_inf = math.e ** (-1j * alpha)
        Q_dip = - self.radius ** 2 * math.e ** (1j * alpha) * (1 / ((z - self.midpoint) ** 2))
        Q_vort = 1j * self.gamma(alpha) / (2 * math.pi) / (z - self.midpoint)
        return (Q_inf + Q_dip + Q_vort)

    def velocity(self, z: complex, alpha: float) -> complex:
        '''return the complex velocity mapped to the zeta-plane of a point in the
           z-plane for a given angle of attack alpha'''
        min_size = 0.1 * 10 ** (-10)
        if abs(z - 1) < min_size:
            return (math.e ** (-1j * alpha) * math.e ** (1j * 2 * self.beta) *
                   math.cos(alpha + self.beta) / self.radius)
        return self.z_velocity(z, alpha) * self.dz_dzeta(z)

    def surface_velocity(self, alpha: float, num: int=100) -> List[complex]:
        '''return the complex velocity for a given angle of attack alpha'''
        return [self.velocity(z, alpha) for z in self.circle(num)]

    def surface_cp(self, alpha: float, num: int=100) -> List[float]:
        '''return the presure coefficient cp on the surface of the airfoil
           for a given angle of attack alpha'''
        return [1 - (v.real ** 2 + v.imag ** 2) for v in self.surface_velocity(alpha, num)]

    def x(self, num: int=100) -> list[float]:
        return [p[0] for p in self.coordinates(num)]
