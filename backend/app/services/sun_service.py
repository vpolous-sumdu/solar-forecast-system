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
    s0 = a1 + a2 * t0 + a3 * (t0**2) - a4 * (t0**3)
    
    nsec = (md - tint) * 86400.0
    ut1 = nsec * 366.2422 / 365.2422
    s0 = (s0 + ut1) / 3600.0 * 15.0
    
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

# --- Вбудований точний астрономічний модуль з sun_unit.py / unit2.py ---

def _time24(tt: float) -> float:
    res = tt
    if res >= 24.0:
        res -= 24.0
    if res < 0.0:
        res += 24.0
    return res

def _correction_day(year: int) -> Tuple[int, int]:
    md0 = _mj_data(2009, 1, 5, 0.0)
    md1 = _mj_data(year, 3, 31, 0.0)
    dm = abs(md1 - md0 + 1)
    day1 = int(math.trunc(int((dm / 7.0 - int(dm / 7.0)) * 7.0 + 0.5)))
    if md1 - md0 < 0:
        day1 = 7 - day1
    day1_fixed = (day1 + 1) % 7
    day_l = 31 - day1_fixed
    
    md1 = _mj_data(year, 10, 31, 0.0)
    dm = abs(md1 - md0 + 1)
    day1 = int(math.trunc(int((dm / 7.0 - int(dm / 7.0)) * 7.0 + 0.5)))
    if md1 - md0 < 0:
        day1 = 7 - day1
    day1_fixed = (day1 + 1) % 7
    day_z = 31 - day1_fixed
    return day_l, day_z

def _universal_time_md(time_m: float, watch: float, decret_time: float, year: int, mon: int, day: int) -> Tuple[float, float]:
    md0 = _mj_data(year, mon, day, 0.0)
    d_time = float(-watch - decret_time)
    md1 = md0 + (time_m + d_time) / 24.0
    day_l, day_z = _correction_day(year)
    t1 = _time24(2.0 + d_time)
    md_l = _mj_data(year, 3, day_l, 0.0) + t1 / 24.0
    t1 = _time24(3.0 + d_time)
    md_z = _mj_data(year, 10, day_z, 0.0) + t1 / 24.0
    if (md1 > md_l) and (md1 < md_z):
        d_time -= 1.0
    result = md0 + (time_m + d_time) / 24.0
    return result, d_time

def _sun_poz_unit(md: float) -> list[float]:
    t0 = (int(math.trunc(md)) - 51544.5) / 36525.0
    ut = (md - int(math.trunc(md))) * 24.0
    m = _mod2pi(357.528 + 35999.05 * t0 + 0.04107 * ut)
    l = 280.46 + 36000.772 * t0 + 0.04107 * ut
    m_rad = math.radians(m)
    l = _mod2pi(l + (1.915 - 0.0048 * t0) * math.sin(m_rad) + 0.02 * math.sin(2.0 * m_rad))
    l_rad = math.radians(l)
    hvect = [math.cos(l_rad), math.sin(l_rad), 0.0]
    eps = math.radians(23.439281)
    return [hvect[0], hvect[1] * math.cos(eps) - hvect[2] * math.sin(eps), hvect[1] * math.sin(eps) + hvect[2] * math.cos(eps)]

def _sun_rise_unit(latitude: float, ra_sun: list[float], dec_sun: list[float], sideral_time: float, d_time: float):
    st_ = 0
    mesg = [' ', ' ']
    time_rise = 0.0
    time_set = 0.0
    begin_sum = 0.0
    end_sum = 0.0
    sum_h = -6.0
    po = 51.0 / 60.0
    l_rad = math.radians(latitude)
    
    if dec_sun[0] >= 90.0 - latitude - po:
        return mesg, -1.0, -1.0, -1.0, -1.0, 1
    if dec_sun[0] <= -90.0 + latitude - po:
        return mesg, -1.0, -1.0, -1.0, -1.0, 2
    if dec_sun[0] >= 90.0 - latitude - po + sum_h:
        begin_sum = -1.0
        end_sum = -1.0
        
    ra_sun_1 = ra_sun[1]
    if ra_sun_1 < ra_sun[0]:
        ra_sun_1 += 360.0
    dra = (ra_sun_1 - ra_sun[0]) / 24.0
    ddec = (dec_sun[1] - dec_sun[0]) / 24.0
    th = sideral_time - ra_sun[0]
    trez = math.sin(l_rad) * math.sin(math.radians(0.0)) + math.cos(l_rad) * math.cos(math.radians(0.0)) * math.cos(math.radians(th))
    hh = 90.0 - math.degrees(math.acos(trez))
    stepi = 4
    
    for i in range(23 * stepi + stepi + 1):
        h_last = hh
        ra = ra_sun[0] + (i / float(stepi)) * dra
        dec = dec_sun[0] + (i / float(stepi)) * ddec
        st = sideral_time + (i / float(stepi)) * 15.0 * 1.002738
        th = st - ra
        trez = math.sin(l_rad) * math.sin(math.radians(dec)) + math.cos(l_rad) * math.cos(math.radians(dec)) * math.cos(math.radians(th))
        hh = 90.0 - math.degrees(math.acos(trez))
        h_refr = hh + po
        
        if (time_rise != -1.0) and (h_last < 0.0) and (hh > 0.0):
            time_rise = (i / float(stepi)) - h_refr / (hh - h_last) / float(stepi)
        if (time_rise != -1.0) and (h_last > 0.0) and (hh < 0.0):
            time_set = (i / float(stepi)) - h_refr / (hh - h_last) / float(stepi)
        if (begin_sum != -1.0) and (h_last <= sum_h) and (hh >= sum_h):
            begin_sum = (i / float(stepi)) + (sum_h - hh) / (hh - h_last) / float(stepi)
        if (end_sum != -1.0) and (h_last >= sum_h) and (hh <= sum_h):
            end_sum = (i / float(stepi)) + (sum_h - hh) / (hh - h_last) / float(stepi)
            
    if time_rise != -1.0: time_rise = _time24(time_rise - d_time)
    if time_set != -1.0: time_set = _time24(time_set - d_time)
    if begin_sum != -1.0: begin_sum = _time24(begin_sum - d_time)
    if end_sum != -1.0: end_sum = _time24(end_sum - d_time)
    return mesg, time_rise, time_set, begin_sum, end_sum, st_

def _sun_unit_main(year: int, mon: int, day: int, time_m: float, watch: float, decret_time: float, longitude: float, latitude: float):
    jul_dat, d_time = _universal_time_md(time_m, watch, decret_time, year, mon, day)
    md = int(math.trunc(jul_dat))
    sideral_time = _jd_sideral_grinvich(md) + longitude
    ra_sun = [0.0, 0.0]
    dec_sun = [0.0, 0.0]
    sun1 = _sun_poz_unit(md)
    ra_sun[0], dec_sun[0] = _angles_from_vector(sun1)
    sun2 = _sun_poz_unit(md + 1.0)
    ra_sun[1], dec_sun[1] = _angles_from_vector(sun2)
    mesg, time_rise, time_set, begin_sum, end_sum, st_ = _sun_rise_unit(latitude, ra_sun, dec_sun, sideral_time, d_time)
    return {'TimeRise': time_rise, 'TimeSet': time_set, 'BeginSum': begin_sum, 'EndSum': end_sum, 'st_': st_, 'dTime': d_time}

def _state_illuminance_d4(hh: float, hv: float, hz: float, hns: float, hks: float) -> int:
    if hh < hns: return 0
    if hh > hns and hh < hv: return 1
    if hh > hv and hh < hz: return 2
    if hh > hz and hh < hks: return 3
    if hh > hks: return 4
    return 100

def _illuminance_diff(h1: float, h2: float, hv: float, hz: float, hns: float, hks: float) -> Tuple[int, float]:
    dh3 = 0.0
    if h1 > h2: h1, h2 = h2, h1
    st_h1 = _state_illuminance_d4(h1, hv, hz, hns, hks)
    if st_h1 == 100: return 100, dh3
    st_h2 = _state_illuminance_d4(h2, hv, hz, hns, hks)
    if st_h2 == 100: return 100, dh3
    dh0 = h2 - h1
    
    def case_st1(st_val, h_val):
        if st_val == 0: return hns - h_val
        elif st_val == 1: return hv - h_val
        elif st_val == 2: return hz - h_val
        elif st_val == 3: return hks - h_val
        elif st_val == 4: return 24.0 - h_val
        return 0.0
        
    def case_st2(st_val, h_val):
        if st_val == 0: return h_val - 0.0
        elif st_val == 1: return h_val - hns
        elif st_val == 2: return h_val - hv
        elif st_val == 3: return h_val - hv
        elif st_val == 4: return h_val - hks
        return 0.0

    if abs(st_h2 - st_h1) == 1:
        dh1 = case_st1(st_h1, h1); dh2 = case_st2(st_h2, h2)
        pc1 = dh1 / dh0 if dh0 != 0 else 0; pc2 = dh2 / dh0 if dh0 != 0 else 0
        return (st_h1 if pc1 > pc2 else st_h2), dh3

    if abs(st_h2 - st_h1) == 2:
        dh1 = case_st1(st_h1, h1); dh2 = case_st2(st_h2, h2); dh3 = 0.0
        if st_h1 == 0 and st_h2 == 2: dh3 = hv - hns
        elif st_h1 == 1 and st_h2 == 3: dh3 = hz - hv
        elif st_h1 == 2 and st_h2 == 4: dh3 = hks - hz
        pc1 = dh1 / dh0 if dh0 != 0 else 0; pc2 = dh2 / dh0 if dh0 != 0 else 0; pc3 = dh3 / dh0 if dh0 != 0 else 0
        result = st_h1 if pc1 > pc2 else st_h2
        if pc3 > max(pc1, pc2): result = (st_h2 + st_h1) // 2
        return result, dh3

    if st_h2 == st_h1:
        result = st_h1
        if result == 2: dh3 = dh0
        return result, dh3
    return 100, dh3

def _calck_state_sun_native(year: int, mon: int, day: int, hh_in: float, hh_out: float, longitude: float, latitude: float, watch: float = 3.0, decret_time: float = 0.0) -> Tuple[int, float]:
    res = _sun_unit_main(year, mon, day, 12.0, watch, decret_time, longitude, latitude)
    hv = res['TimeRise']
    hz = res['TimeSet']
    hns = res['BeginSum']
    hks = res['EndSum']
    st_day = res['st_']
    
    if st_day == 1:
        hv = -0.1; hz = 24.01; hns = hv; hks = hz
    elif st_day == 2:
        hv = 24.01; hz = 24.01; hns = hv; hks = hz
    elif st_day == 3:
        hns = -0.1; hks = 24.01
        
    st, dh_svet = _illuminance_diff(hh_in, hh_out, hv, hz, hns, hks)
    if dh_svet < 0:
        dh_svet = 24.0 + dh_svet
    if dh_svet > (hh_out - hh_in):
        dh_svet = hh_out - hh_in
        
    if st in [0, 4]:
        st = 0
    elif st in [1, 3]:
        st = 1
    elif st == 2:
        st = 2
    else:
        st = 100
        
    return st, dh_svet

def calculate_sun_position(latitude: float, longitude: float, dt_local: datetime, watch: float = 3.0) -> Dict[str, Any]:
    """
    Обчислює астрономічні позиції сонця 1-в-1 з еталоном (sun_unit.py / unit4.py / unit2.py):
    - azimuth: Азимут сонця (градуси)
    - elevation: Висота сонця над горизонтом (градуси)
    - st_s: Стан доби (0 - ніч, 1 - сутінки, 2 - день)
    - h_svetl: Тривалість світлового дня в годинах для 1h інтервалу
    """
    ut = (dt_local.hour + 0.5) - watch
    md = _mj_data(dt_local.year, dt_local.month, dt_local.day, ut)
    sideral_time = _jd_sideral_grinvich(md) + longitude
    
    sun = _sun_coordinate(md)
    r_obs = _coord_eci_ellipse(latitude, sideral_time, 0.0)
    r_top = _substr_vector(sun, r_obs)
    
    ra_sun, dec_sun = _angles_from_vector(r_top)
    th_sun = sideral_time - ra_sun
    
    az, h = _azimutal_coordinate(th_sun, dec_sun, latitude)
    
    hh_in = float(dt_local.hour)
    hh_out = float(dt_local.hour + 1)
    st_s, h_svetl_interval = _calck_state_sun_native(
        dt_local.year, dt_local.month, dt_local.day, hh_in, hh_out, longitude, latitude, watch=watch
    )
    
    return {
        "azimuth": round(az, 4),
        "elevation": round(h, 4),
        "st_s": st_s,
        "is_day": 1 if st_s == 2 else 0,
        "h_svetl": round(h_svetl_interval, 4)
    }
