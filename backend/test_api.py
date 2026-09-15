# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from backend.main import app

DIV  = "=" * 64
DIV2 = "-" * 64
results = []

def ae(a, b):   assert a == b,      f"expected {b!r} got {a!r}"
def ai(k, d):   assert k in d,      f"key {k!r} missing"
def agt(a, b):  assert a > b,       f"expected > {b} got {a}"
def alge(d, n): assert len(d) >= n, f"expected len>={n} got {len(d)}"

def check(label, resp, exp=200, fn=None):
    ok = resp.status_code == exp
    detail = ""
    if ok and fn:
        try: fn(resp.json())
        except AssertionError as e: ok = False; detail = str(e)
    results.append(ok)
    tag = "[PASS]" if ok else "[FAIL]"
    print(f"  {tag}  {label:<55} HTTP {resp.status_code}")
    if not ok and detail: print(f"         >> {detail}")
    return resp

# Use context manager to trigger lifespan startup
with TestClient(app) as client:
    print(); print(DIV)
    print("  ResQ Shield - Phase 9 API Test Suite (Dynamic)")
    print(DIV)

    # ── 1. Health ─────────────────────────────────────────────────────────────
    print(f"\n{DIV2}\n  HEALTH ENDPOINTS\n{DIV2}")
    r = check("GET /", client.get("/"),
        fn=lambda d: (ae(d["status"],"ok"), ae(d["data_type"],"synthetic_demo"),
                      ai("disclaimer",d), agt(d["locations"],0)))
    d = r.json(); print(f"    locations={d['locations']}  states={d['states']}")
    check("GET /health", client.get("/health"), fn=lambda d: ae(d["project"],"ResQ Shield"))

    # ── 2. /api/locations ─────────────────────────────────────────────────────
    print(f"\n{DIV2}\n  /api/locations\n{DIV2}")
    r = check("GET /api/locations (all)", client.get("/api/locations"), fn=lambda d: alge(d, 100))
    all_locs = r.json(); print(f"    returned {len(all_locs)} locations (expect >100)")

    r = check("GET /api/locations?state=Uttarakhand", client.get("/api/locations?state=Uttarakhand"),
        fn=lambda d: (alge(d, 10), [ae(x["state"],"Uttarakhand") for x in d]))
    uk = r.json(); print(f"    Uttarakhand ({len(uk)}): {[x['district'] for x in uk]}")

    r = check("GET /api/locations?state=Ladakh", client.get("/api/locations?state=Ladakh"), fn=lambda d: alge(d,1))
    print(f"    Ladakh: {[x['district'] for x in r.json()]}")

    r = check("GET /api/locations?landslide_risk=High", client.get("/api/locations?landslide_risk=High"),
        fn=lambda d: [ae(x["landslide_risk"],"High") for x in d])
    ls_high = r.json(); print(f"    LS=High ({len(ls_high)}): {[x['district'] for x in ls_high[:6]]}...")

    r = check("GET /api/locations?flood_risk=High", client.get("/api/locations?flood_risk=High"),
        fn=lambda d: [ae(x["flood_risk"],"High") for x in d])
    fl_high = r.json(); print(f"    Flood=High ({len(fl_high)}): {[x['district'] for x in fl_high[:6]]}...")

    r = check("GET /api/locations?flood_risk=Low", client.get("/api/locations?flood_risk=Low"),
        fn=lambda d: [ae(x["flood_risk"],"Low") for x in d])
    print(f"    Flood=Low ({len(r.json())})")

    r = check("GET ?state=Uttarakhand&landslide_risk=High",
        client.get("/api/locations?state=Uttarakhand&landslide_risk=High"))
    combo = r.json(); print(f"    UK+LS=High ({len(combo)}): {[x['district'] for x in combo]}")

    r = check("GET ?flood_risk=high (lowercase ok)", client.get("/api/locations?flood_risk=high"),
        fn=lambda d: [ae(x["flood_risk"],"High") for x in d])
    print(f"    lowercase 'high' accepted: {len(r.json())} results")

    # ── 3. Invalid filters ────────────────────────────────────────────────────
    print(f"\n{DIV2}\n  INVALID FILTER VALIDATION\n{DIV2}")
    r = check("?flood_risk=extreme (expect 400)", client.get("/api/locations?flood_risk=extreme"), exp=400)
    print(f"    detail: {r.json().get('detail','')[:80]}")
    r = check("?landslide_risk=extreme (expect 400)", client.get("/api/locations?landslide_risk=extreme"), exp=400)
    print(f"    detail: {r.json().get('detail','')[:80]}")

    # ── 4. Search ─────────────────────────────────────────────────────────────
    print(f"\n{DIV2}\n  /api/search\n{DIV2}")
    r = check("GET /api/search?q=dehradun", client.get("/api/search?q=dehradun"), fn=lambda d: alge(d,1))
    print(f"    'dehradun' -> {[x['district'] for x in r.json()]}")
    r = check("GET /api/search?q=deh (partial)", client.get("/api/search?q=deh"), fn=lambda d: alge(d,1))
    print(f"    'deh' -> {[x['district'] for x in r.json()]}")
    r = check("GET /api/search?q=uttarakhand", client.get("/api/search?q=uttarakhand"), fn=lambda d: alge(d,5))
    print(f"    'uttarakhand' -> {len(r.json())} results")
    r = check("GET /api/search?q=shim", client.get("/api/search?q=shim"), fn=lambda d: alge(d,1))
    print(f"    'shim' -> {[x['district'] for x in r.json()]}")
    r = check("GET /api/search?q=leh", client.get("/api/search?q=leh"))
    print(f"    'leh' -> {[(x['district'],x['flood_risk'],x['landslide_risk']) for x in r.json()]}")
    r = check("GET /api/search?q=guwahati", client.get("/api/search?q=guwahati"))
    print(f"    'guwahati' -> {[(x['district'],x['flood_risk']) for x in r.json()]}")
    r = check("GET /api/search?q=assam", client.get("/api/search?q=assam"))
    print(f"    'assam' -> {[x['district'] for x in r.json()]}")

    # ── 5. Single location ────────────────────────────────────────────────────
    print(f"\n{DIV2}\n  /api/location/{{district}}\n{DIV2}")
    # Risk expectations marked None = don't assert (retrained model may differ)
    locs = [
        ("Dehradun",     "Uttarakhand",         None, None),
        ("Chamoli",      "Uttarakhand",         None, None),
        ("Rudraprayag",  "Uttarakhand",         None, None),
        ("Uttarkashi",   "Uttarakhand",         None, None),
        ("Shimla",       "Himachal Pradesh",    None, None),
        ("Leh",          "Ladakh",              None, None),
        ("Gangtok",      "Sikkim",              None, None),
        ("Tawang",       "Arunachal Pradesh",   None, None),
        ("Darjeeling",   "West Bengal",         None, None),
        # Phase 9 — newly added locations
        ("Joshimath",    "Uttarakhand",         None, None),
        ("Mussoorie",    "Uttarakhand",         None, None),
        ("Dhemaji",      "Assam",               None, None),
        ("Cherrapunji",  "Meghalaya",           None, None),
        ("Munnar",       "Kerala",              None, None),
        ("Madikeri",     "Karnataka",           None, None),
        ("Pahalgam",     "Jammu & Kashmir",     None, None),
        ("Kaza",         "Himachal Pradesh",    None, None),
        ("Gorakhpur",    "Uttar Pradesh",       None, None),
        ("Darbhanga",    "Bihar",               None, None),
        ("Ratnagiri",    "Maharashtra",         None, None),
        ("Wayanad",      "Kerala",              None, None),
        ("Jaisalmer",    "Rajasthan",           None, None),
    ]
    for district, state, exp_f, exp_l in locs:
        r = client.get(f"/api/location/{district}")
        if r.status_code == 200:
            d = r.json()
            f_ok = (exp_f is None) or (d["flood_risk"] == exp_f)
            l_ok = (exp_l is None) or (d["landslide_risk"] == exp_l)
            ok = f_ok and l_ok
            results.append(ok)
            tag = "[PASS]" if ok else "[FAIL]"
            note = "" if ok else f"  <- expected F:{exp_f} L:{exp_l}"
            print(f"  {tag}  {district:<20} {state:<22} F:{d['flood_risk']}({d['flood_probability']:.0f}%)  LS:{d['landslide_risk']}({d['landslide_probability']:.0f}%){note}")
        else:
            results.append(False)
            print(f"  [FAIL]  {district:<20} HTTP {r.status_code}")

    r = client.get("/api/location/Dehradun"); d = r.json()
    ok = "source_flood_risk" not in d and "source_landslide_risk" not in d
    results.append(ok); print(f"  {'[PASS]' if ok else '[FAIL]'}  Internal audit fields excluded from public response")

    # ── 6. 404 ────────────────────────────────────────────────────────────────
    print(f"\n{DIV2}\n  404 NOT FOUND\n{DIV2}")
    r = check("GET /api/location/NotARealPlace (expect 404)", client.get("/api/location/NotARealPlace"), exp=404)
    print(f"    detail: {r.json().get('detail','')[:80]}")
    r = check("GET /api/location/Dehradun?state=Tamil Nadu (expect 404)",
        client.get("/api/location/Dehradun?state=Tamil Nadu"), exp=404)
    print(f"    detail: {r.json().get('detail','')[:80]}")

    # ── 7. States ─────────────────────────────────────────────────────────────
    print(f"\n{DIV2}\n  /api/states\n{DIV2}")
    r = check("GET /api/states", client.get("/api/states"), fn=lambda d: alge(d,20))
    states = r.json(); print(f"    {len(states)} states:")
    for s in states: print(f"      {s}")

    # ── 8. Summary ────────────────────────────────────────────────────────────
    print(f"\n{DIV2}\n  /api/summary\n{DIV2}")
    r = check("GET /api/summary", client.get("/api/summary"),
        fn=lambda d: (ai("flood",d), ai("landslide",d), ae(d["data_type"],"synthetic_demo")))
    s = r.json()
    print(f"    total_locations : {s['total_locations']}")
    print(f"    total_states    : {s['total_states']}")
    print(f"    flood           : {s['flood']}")
    print(f"    landslide       : {s['landslide']}")
    print(f"    data_type       : {s['data_type']}")
    print(f"    disclaimer      : {s['disclaimer']}")

    # ── 9. Mountain locations ─────────────────────────────────────────────────
    print(f"\n{DIV2}\n  /api/mountain-locations\n{DIV2}")
    r = check("GET /api/mountain-locations", client.get("/api/mountain-locations"), fn=lambda d: alge(d,20))
    mtn = r.json()
    print(f"    {len(mtn)} mountain locations:")
    for loc in mtn:
        print(f"      {loc['district']:<22} {loc['state']:<24} F:{loc['flood_risk']:<8} LS:{loc['landslide_risk']}")

# ── Final score ───────────────────────────────────────────────────────────────
print(); print(DIV)
passed = sum(results); total = len(results)
print(f"  RESULTS: {passed}/{total} tests passed")
print(f"  {'ALL TESTS PASSED' if passed == total else str(total-passed)+' TESTS FAILED'}")
print(DIV)
