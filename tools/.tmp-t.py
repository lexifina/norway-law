import sys; sys.path.insert(0, '.'); import lovdata as L
L.CHAPNUM = True
for t in ['§ 1-1 første ledd', '§§ 1-1 til 1-3 oppheves', 'lov 17. juni 2005 nr. 62', 'LOV-2005-06-17-62', '2006-01-01', '§ 12-5 a', '1-3 år', '§ 15-11']:
    print(t, '->', L.norm(t), '->', L.dec(L.norm(t)))
print(L.para_key('1-1'), L.para_key('12-5 a'), L.para_key('901001'))
L.CHAPNUM = False
print(L.norm('§§ 77-79'), L.para_key('75'))
