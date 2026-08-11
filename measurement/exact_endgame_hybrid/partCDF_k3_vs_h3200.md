### exact:3 vs h3200 (n=400)
- games **400** | **211W / 8D / 181L** | winrate **0.537** (z=+1.50) | Elo **+26.1** (±17.4)
- avg score margin (A−B) **+1.70** | **paired margin +1.698** (z=**+1.55**, 200 decks)
- seat split: A@seat0 wr 0.507 (n=200), A@seat1 wr 0.568 (n=200)
- A exact: exact-moves/game 3.00 (range 2-4); solver 89.45s/game (max 3140.7s); nodes/game 12797; timeouts 0 over 400; latched 400/400; K@latch dist {2: 200, 3: 200}

#### Part D slices (paired margin within slice; n=decks w/ both seats)
  - **by K@latch**
    - K@latch=2: n=200 wr=0.507 paired=None (z=None, 0 decks)
    - K@latch=3: n=200 wr=0.568 paired=None (z=None, 0 decks)
  - **by seat**
    - seat=0: n=200 wr=0.507 paired=None (z=None, 0 decks)
    - seat=1: n=200 wr=0.568 paired=None (z=None, 0 decks)
  - **by margin@latch**
    - margin@latch=ahead(>3): n=189 wr=0.857 paired=19.54 (z=11.47, 40 decks)
    - margin@latch=behind(<-3): n=168 wr=0.170 paired=-13.88 (z=-5.95, 28 decks)
    - margin@latch=close(-3..3): n=43 wr=0.570 paired=0.17 (z=0.02, 3 decks)
  - **by meeples@latch**
    - meeples@latch=0-1: n=381 wr=0.531 paired=1.08 (z=0.95, 181 decks)
    - meeples@latch=2-3: n=18 wr=0.639 paired=None (z=None, 0 decks)
    - meeples@latch=4+: n=1 wr=1.000 paired=None (z=None, 0 decks)
  - **by legal@latch**
    - legal@latch=hi(>45): n=125 wr=0.516 paired=-2.0 (z=-0.6, 23 decks)
    - legal@latch=lo(<20): n=14 wr=0.393 paired=None (z=None, 0 decks)
    - legal@latch=mid(20-45): n=261 wr=0.556 paired=2.7 (z=1.69, 87 decks)
  - **by game**
    - game=blowout(|d|>=20): n=160 wr=0.556 paired=3.62 (z=0.99, 36 decks)
    - game=close(|d|<20): n=240 wr=0.525 paired=0.14 (z=0.16, 76 decks)
  - **by timeout**
    - timeout=clean: n=400 wr=0.537 paired=1.7 (z=1.55, 200 decks)
  - **by solver_nodes**
    - solver_nodes=1k-5k: n=152 wr=0.493 paired=-1.33 (z=-0.19, 9 decks)
    - solver_nodes=<1k: n=87 wr=0.580 paired=-14.25 (z=-57.0, 2 decks)
    - solver_nodes=>5k: n=161 wr=0.556 paired=-14.38 (z=-3.48, 4 decks)

#### Part F — paired Δ vs baseline (same decks, same opponent; isolates the exact tail)
- overlapping games: 400 (200 decks w/ both seats) — baseline = RoD1-vs-h3200 cached
- mean per-game Δ(margin) +1.260; **paired Δ margin +1.260 (z=**+7.29**)**
  (Δ>0 ⇒ the exact tail improves RoD1's margin vs this opponent on these decks)
