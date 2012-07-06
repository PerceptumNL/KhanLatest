import time


def serializeMapCoords(lat, lng, zoom):
    return "%s:%s:%s:%s" % (lat, lng, zoom, int(time.time() * 1000))


def deserializeMapCoords(s=False):
    coords = {'lat': 0, 'lng': 0, 'zoom': 0, 'when': 0}
    if (not s):
        return coords

    try:
        rg = s.split(":")
        coords['lat'] = float(rg[0])
        coords['lng'] = float(rg[1])
        coords['zoom'] = int(rg[2])
        if len(rg) == 4:
            coords['when'] = int(rg[3])
        else:
            coords['when'] = 0
    except ValueError:
        return coords

    return coords
