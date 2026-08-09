import importlib.util, random, collections
spec=importlib.util.spec_from_file_location("am","/home/doctor/projects/carcassone/scripts/jcz_mining/analyze_mining.py")
AM=importlib.util.module_from_spec(spec); spec.loader.exec_module(AM)
SD=4.3; T=4000

def power(nA, effect):
    N={'A':nA,'B':nA,'C':2*nA}
    rng=random.Random(20260809); hit=0; g1=0
    for _ in range(T):
        st={}
        for L,n in N.items():
            mu = effect if L=='A' else 0.0
            rows=[{"delta":rng.gauss(mu,SD),"root_id":f"{L}{i}","game_label":f"{L}{i}"} for i in range(n)]
            st[L]=AM.stratum_stats(rows,L)
        d=AM.decide(st,25,None)
        if "CONVICT" in str(d["per_stratum"].get("A","")): hit+=1
        if d["global_branch"]=="G1": g1+=1
    return 100*hit/T, 100*g1/T

print("POWER of the A-CONVICT branch (T=4000 draws, sd=4.3 pts/position)")
print(f"{'n/stratum':>10} {'positions':>10} " + "".join(f"{e:>10}" for e in ("+1.0","+1.4","+2.0","+3.0")))
for nA in (40, 55, 74, 100):
    tot = nA+nA+2*nA
    cells=[]
    for e in (1.0,1.4,2.0,3.0):
        p,_=power(nA,e); cells.append(f"{p:9.0f}%")
    print(f"{nA:>10} {tot:>10} " + "".join(cells))
print()
p,g1 = power(40,1.4)
print(f"At the SHIPPED design (n=40): power {p:.0f}% at +1.4 pts, and G1 'all wash' still fires {g1:.0f}% of the time when A truly has that effect.")
