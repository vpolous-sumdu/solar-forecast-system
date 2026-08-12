import math
from datetime import datetime, timezone
from typing import Tuple, Dict, Any

def _mjd_from_date(year: int, mon: int, day: int) -> Tuple[float, float]:
    """Обчислює модифікований юліанський день (MJD) та юліанську дату (JD)."""
    year1 = int(year)
    mon1 = int(mon)
    
    var1 = 10000 * year1 + 100 * mon1 + day
    
    if mon1 <= 2:
        mon1 += 12
        year1 -= 1
        
    if var1 <= 15821004:
        b = -2 + ((year1 + 4716) // 4) - 1179
    else:
        b = (year1 // 400) - (year1 // 100) + (year1 // 4)
        
    var1 = 365 * year1 - 679004
    md = float(var1 + b + (306001 * (mon1 + 1) // 10000) + day)
    jd0 = md + 2400000.5
    return md, jd0

def _mj_data(year: int, mon: int, day: int, ut: float) -> float:
    """Обчислює MJD з урахуванням часу (UT в годинах)."""
    mjd, _ = _mjd_from_date(year, mon, day)
    return mjd + ut / 24.0

def _jd_sideral_grinvich(md: float) -> float:
    """Розрахунок зоряного часу в Гринвічі у градусах."""
    a1 = 24110.54841
    a2 = 8640184.812
    a3 = 0.093104
    a4 = 0.0000062
    
    tint = int(math.trunc(md))
    t0 = (tint - 51544.5) / 36525.0
    s0 = a1 + a2 * t0 + a3 * (t0**2) - a4 * t0 * (t0**2)
    
    nsec = (md - tint) * 86400.0
    ut1 = nsec * 366.2422 / 365.2422
    s0 = s0 + ut1
    s0 = s0 / 3600.0
    s0 = s0 * 15.0
    
    while s0 >= 360.0:
        s0 -= 360.0
        
    return s0

def _mod2pi(x: float) -> float:
    """Нормалізує кут у межах [0, 360) градусів."""
    res = x
    while res < 0.0:
        res += 360.0
    while res >= 360.0:
        res -= 360.0
    return res

def _true_anomaly(m: float, e: float) -> float:
    """Обчислює справжню аномалію орбіти."""
    eps = math.radians(1.0 / 360.0 / 3600.0)
    m0 = math.radians(m)
    e1 = m0 + e * math.sin(m0) * (1.0 + e * math.cos(m0))
    dd = 1.0
    k = 0
    ee = e1
    
    while dd > eps and k < 300:
        k += 1
        ee = e1 - (e1 - e * math.sin(e1) - m0) / (1.0 - e * math.cos(e1))
        dd = abs(ee - e1)
        e1 = ee
        
    ean = ee
    return math.degrees(2.0 * math.atan(math.sqrt((1.0 + e) / (1.0 - e)) * math.tan(ean / 2.0)))

def _ellipt_r(a: float, e: float, v: float) -> float:
    return a * (1.0 - e**2) / (1.0 + e * math.cos(math.radians(v)))

def _xyz_helio(r: float, i: float, om: float, w: float, v: float) -> Tuple[float, float, float]:
    u = w + v - om
    u_rad = math.radians(u)
    om_rad = math.radians(om)
    i_rad = math.radians(i)
    
    x = r * (math.cos(u_rad) * math.cos(om_rad) - math.sin(u_rad) * math.sin(om_rad) * math.cos(i_rad))
    y = r * (math.cos(u_rad) * math.sin(om_rad) + math.sin(u_rad) * math.cos(om_rad) * math.cos(i_rad))
    z = r * math.sin(u_rad) * math.sin(i_rad)
    return x, y, z

def _earth_coordinate(md: float) -> list[float]:
    cy = (md - 51544.5) / 36525.0
    a = 1.00000011 - 0.00000005 * cy
    e = 0.01671022 - 0.00003804 * cy
    i = 0.00005 - 46.94 * cy / 3600.0
    om = -11.26064 - 18228.25 * cy / 3600.0
    w = 102.94719 + 1198.28 * cy / 3600.0
    l = _mod2pi(100.46435 + 129597740.63 * cy / 3600.0)
    
    m = l - w
    v = _true_anomaly(m, e)
    r = _ellipt_r(a, e, v)
    x, y, z = _xyz_helio(r, i, om, w, v)
    return [x, y, z]

def _ecliptic_equatorial(r1: list[float], epsilon: float) -> list[float]:
    eps = math.radians(epsilon)
    return [
        r1[0],
        r1[1] * math.cos(eps) - r1[2] * math.sin(eps),
        r1[1] * math.sin(eps) + r1[2] * math.cos(eps)
    ]

def _sun_coordinate(md: float) -> list[float]:
    ae = 149597892.1111
    earth = _earth_coordinate(md)
    epsilon = 23.439281
    ecv_r = _ecliptic_equatorial(earth, epsilon)
    return [-ecv_r[0] * ae, -ecv_r[1] * ae, -ecv_r[2] * ae]

def _coord_eci_ellipse(lati: float, teta: float, h: float) -> list[float]:
    re = 6378.155
    f = 1.0 / 298.26
    c = 1.0 / math.sqrt(1.0 + f * (f - 2.0) * (math.sin(math.radians(lati))**2))
    s = ((1.0 - f)**2) * c
    return [
        (re * c + h) * math.cos(math.radians(lati)) * math.cos(math.radians(teta)),
        (re * c + h) * math.sin(math.radians(teta)) * math.cos(math.radians(lati)),
        (re * s + h) * math.sin(math.radians(lati))
    ]

def _substr_vector(a: list[float], b: list[float]) -> list[float]:
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]

def _angles_from_vector(r: list[float]) -> Tuple[float, float]:
    ra = math.degrees(math.atan2(r[1], r[0]))
    dec = math.degrees(math.atan2(r[2], math.hypot(r[0], r[1])))
    if ra < 0.0:
        ra += 360.0
    return ra, dec

def _azimutal_coordinate(th: float, dec: float, latit: float) -> Tuple[float, float]:
    cos_z = math.sin(math.radians(latit)) * math.sin(math.radians(dec)) + math.cos(math.radians(latit)) * math.cos(math.radians(dec)) * math.cos(math.radians(th))
    try:
        z = math.atan(-cos_z / math.sqrt(-cos_z * cos_z + 1.0)) + 2.0 * math.atan(1.0)
    except (ValueError, ZeroDivisionError):
        z = math.acos(cos_z)
        
    z = math.degrees(z)
    h = 90.0 - z
    
    sin_az = math.sin(math.radians(th)) * math.cos(math.radians(dec)) * math.cos(math.radians(latit))
    cos_az = (math.sin(math.radians(h)) * math.sin(math.radians(latit)) - math.sin(math.radians(dec)))
    
    az = math.degrees(math.atan2(sin_az, cos_az)) + 180.0
    if az < 0.0:
        az += 360.0
    return az, h

def calculate_sun_position(latitude: float, longitude: float, dt_utc: datetime) -> Dict[str, Any]:
    """
    Обчислює астрономічні позиції сонця (азимут, висота над горизонтом та стан світанку/ночі)
    на основі географічних координат та часу у форматі UTC.
    
    Повертає словник:
    {
        "azimuth": float (градуси),
        "elevation": float (градуси),
        "is_day": int (1 - сонце вище горизонту, 0 - ніч)
    }
    """
    ut = dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0
    md = _mj_data(dt_utc.year, dt_utc.month, dt_utc.day, ut)
    sideral_time = _jd_sideral_grinvich(md) + longitude
    
    sun = _sun_coordinate(md)
    r_obs = _coord_eci_ellipse(latitude, sideral_time, 0.0)
    r_top = _substr_vector(sun, r_obs)
    
    ra_sun, dec_sun = _angles_from_vector(r_top)
    th_sun = sideral_time - ra_sun
    
    az, h = _azimutal_coordinate(th_sun, dec_sun, latitude)
    
    return {
        "azimuth": round(az, 4),
        "elevation": round(h, 4),
        "is_day": 1 if h > 0 else 0
    }
