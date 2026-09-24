"""Fixed worker-only guide representations; recordings remain immutable."""
PRESETS={'none':0,'material-draw':1}


def validate_guide(name):
    if type(name) is not str or name not in PRESETS:
        raise ValueError('unknown guide preset')
    return PRESETS[name]


def material_type(row,name):
    ident=validate_guide(name)
    if not ident or not row[23]: return row[11]
    return ((int(row[23])-1)%4)/3
