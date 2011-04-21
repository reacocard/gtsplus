
import struct
import namemaps

unpack  = lambda pkm, byte: struct.unpack("<B", pkm[byte])[0]
unpack2 = lambda pkm, begin, end: struct.unpack("<H", pkm[begin:end+1])[0]
unpack4 = lambda pkm, begin, end: struct.unpack("<I", pkm[begin:end+1])[0]
def unpackstr(begin, end):
    s = ""
    for i in pkm[begin:end+1]:
        if i == '\xff': break
        if i != '\x00': s += i
    return s


def pkmtodata(pkm):
    data = {}
    data['personality'] = pid = unpack4(pkm,0x00,0x03)
    data['species']     = unpack2(pkm,0x08,0x09)
    data['item']        = unpack2(pkm,0x0a,0x0b)
    data['otid']        = otid = unpack2(pkm,0x0c,0x0d)
    data['otsecret']    = otsec = unpack2(pkm,0x0e,0x0f)
    data['ability']     = unpack(pkm,0x15)
    data['attack1']     = unpack2(pkm,0x28,0x29)
    data['attack2']     = unpack2(pkm,0x2a,0x2b)
    data['attack3']     = unpack2(pkm,0x2c,0x2d)
    data['attack4']     = unpack2(pkm,0x2e,0x2f)
    data['isegg']       = ((unpack4(pkm,0x38,0x3b) & 0x20000000) / 0x20000000) == 1
    data['fateful']     = (unpack(pkm,0x40) & 0x01) == 1
    data['gender']      = (unpack(pkm,0x40) & 0x06) / 0x02  # 0 Male, 1 Female, 2 None
    data['forme']       = (unpack(pkm,0x40) & 0xf8) / 0x08
    data['nature']      = unpack(pkm,0x41)
    data['dreamworld']  = (unpack(pkm,0x42) & 0x01) == 1
    data['nickname']    = unpackstr(pkm,0x48,0x5d)
    data['otname']      = unpackstr(pkm,0x68,0x77)
    data['pokerus']     = unpack(pkm,0x82)
    data['pokeball']    = unpack(pkm,0x83)
    data['otgender']    = (unpack(pkm,0x84) & 0x80) / 0x80 # 0 - male, 1 - female
    data['level']       = unpack(pkm,0x8c)
    data['shiny']       = shiny(**data)
    return data

def rechecksum(pkm):
    """recalculate the checksum"""
    # Split the unencrypted data from offsets 0x08 to 0x87 into two-byte words,
    # Take the sum of the words, and truncate the sum to sixteen bits.
    checksum = sum([unpack2(pkm,x,x+2) for x in range(0x08, 0x87, 2)]) & 0xffff
    pkm = pkm[:0x06] + struct.pack("<H", checksum) + pkm[0x08:]
    return pkm

def check_pkm(pkm):
    """Check that a pokemon is possible within official rules.
        Checks are NOT perfect."""
    data = pkmtodata(pkm)
    return len(pkm) == 220 and \
           check_gender(**data) and \
           check_ability(**data) and \
           check_nature(**data) and \
           check_wurmple(**data) and \
           check_egg(**data)

def check_gender(pid, species, gender, **k):
    """
        Checks that the given gender is consistent with the personality value
    """
    ratio = namemaps.genderratio[species]
    if ratio == -1:
        return gender == 2
    thresh = namemaps.genderthreshholds[ratio]
    p = pid & 0xff
    return ((thresh - p) > 0) ^ gender

def check_ability(pid, species, dreamworld, ability, **k):
    abil = namemaps.ability[ability]
    sabilities = namemaps.species_abilities[species]
    abilidx = 2 if dreamworld else pid % 2
    return sabilities[abilidx] == abil

def check_nature(pid, nature, **k):
    return pid % 25 == nature

def shiny(pid, otid, otsec, **k):
    return ((otid^otsec) ^ ((pid >> 16)^(pid & 0xffff))) < 8

def unown_letter(pid, **k):
    val = (pid & 0x08000000 >> 3) + (pid & 0x00080000 >> 2) + (pid & 0x00000800 >> 1) + (pid & 0x00000008)
    return "abcdefghijklmnopqrstuvwxyz?!"[val%28]

# 1 means silcoon, 2 means cascoon
def wurmple_evo(pid, **k):
    return (pid & 0xffff) % 10 < 5

def check_wurmple(pid, species, **k):
    if 266 <= species <= 267:
        return wurmple_evo(pid) == 1
    elif 268 <= species <= 269:
        return wurmple_evo(pid) == 2
    else:
        return True

def check_egg(pid, level, isegg, **k):
    # TODO: check experience, EVs
    if isegg:
        return level == 1
    return True
