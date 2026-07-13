import math

from openglider.airfoil.generators.joukowsy import JoukowskyAirfoil


class VanDeVoorenAirfoil(JoukowskyAirfoil):
    def __init__(self, tau: float, epsilon: float, chord_length: float=2) -> None:
        self.tau = tau
        self.epsilon = epsilon
        self.chord_length = chord_length
        super(VanDeVoorenAirfoil, self).__init__(midpoint=0+0j)

    @property
    def k(self) -> float:
        '''SA p.138 6.66'''
        return 2 - self.tau / math.pi

    @property
    def radius(self) -> float:
        '''LSA p.138 (6.65)'''
        return 2 * self.chord_length * (1 + self.epsilon) ** (self.k - 1) * 2 ** (-self.k)

    def zeta(self, z: complex) -> complex:
        '''LSA p.137 (6.62)'''
        a = (z - self.radius) ** self.k
        b = (z - self.radius * self.epsilon) ** (self.k - 1)
        return a / b + self.chord_length

    def dz_dzeta(self, z: complex) -> complex:
        k = self.k
        e = self.epsilon
        a = self.radius
        dzeta_dz = k*(-a + z)**(-1 + k)*(-(a*e) + z)**(1 - k) +\
            ((1 - k)*(-a + z)**k)/(-(a*e) + z)**k
        dzeta_dz = 0.00000001 if dzeta_dz == 0 else dzeta_dz
        return 1 / dzeta_dz

    def z(self, zeta: complex) -> complex:
        '''not invertable'''
        raise NotImplementedError()