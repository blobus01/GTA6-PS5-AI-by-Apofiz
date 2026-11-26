import math
def semi(stick_sides, ms=1000, n=20):
    """Полукруг снизу вверх. stick_sides: {'left':-1 (через левую сторону), 'right':1 (через правую)}"""
    steps=[]
    for i in range(n+1):
        a=math.pi*i/n  # 0..pi: снизу (y=+1) вверх (y=-1)
        st={"ms":ms//n}
        for stick,side in stick_sides.items():
            st[stick]=[side*math.sin(a), math.cos(a)]
        steps.append(st)
    return steps
