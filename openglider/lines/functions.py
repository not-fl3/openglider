#! /usr/bin/python2
#
# (c) 2013 booya (http://booya.at)
#
# This file is part of the OpenGlider project.
#
# OpenGlider is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# OpenGlider is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenGlider.  If not, see <http://www.gnu.org/licenses/>.

import logging
import openglider.rs

logger = logging.getLogger(__name__)


def proj_force(force: openglider.rs.vector.Vector3D, vec: openglider.rs.vector.Vector3D) -> float | None:
    projection = vec.dot(force)
    
    if projection**2 < 0.00001:
        logger.warning(f"singular force projection: direction: {vec}, force: {force} => {projection}")
        return None
    return force.dot(force) / projection


def proj_to_surface(vec: openglider.rs.vector.Vector3D, n_vec: openglider.rs.vector.Vector3D) -> openglider.rs.vector.Vector3D:
    return vec - n_vec * n_vec.dot(vec) / n_vec.dot(n_vec)
