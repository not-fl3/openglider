import math

from openglider.airfoil.generators.joukowsy import JoukowskyAirfoil


class TrefftzKuttaAirfoil(JoukowskyAirfoil):
    '''http://en.wikipedia.org/wiki/Joukowsky_transform
       3. Trefftz_transform'''

    def __init__(self, midpoint: complex, tau: float) -> None:
        self.tau = tau
        super().__init__(midpoint)

    @property
    def n(self) -> float:
        return 2 - self.tau / math.pi

    def zeta(self, z: complex) -> complex:
        n = self.n
        a = (1 + 1 / z) ** n
        b = (1 - 1 / z) ** n
        return n * (a + b) / (a - b)

    def dz_dzeta(self, z: complex) -> complex:
        n = self.n
        a = (1 + 1 / z) ** n
        b = (1 - 1 / z) ** n
        if z ** 2 == 1 or a - b == 0:
            return 0
        dzeta_dz = 4 * n ** 2 / (z ** 2 - 1) * (a * b) / (a - b) ** 2
        dzeta_dz = 0.00000001 if dzeta_dz == 0 else dzeta_dz
        return 1 / dzeta_dz

    def velocity(self, z: complex, alpha: float) -> complex:
        '''return the complex velocity mapped to the zeta-plane of a point in the
           z-plane for a given angle of attack alpha'''
        min_size = 0.1 * 10 ** (-10)
        return self.z_velocity(z, alpha) * self.dz_dzeta(z)

    def z(self, zeta: complex) -> complex:
        '''not invertable'''
        raise NotImplementedError()
