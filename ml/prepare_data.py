# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

"""
ResQ Shield — Phase 9: Expanded Master Dataset (~350 locations)
================================================================
Generates data/processed/master_dataset.csv

IMPORTANT DISCLAIMER:
    All environmental feature values (rainfall, river_level, soil_moisture,
    slope, elevation, flood_history, landslide_history) are SYNTHETIC /
    artificially generated for demonstration purposes only.

    These values are NOT real-time measurements, satellite data, IMD/CWC
    observations, or any official source.

    Latitude/longitude coordinates are real approximate centroids.
    All other fields are approximated for geographic plausibility only.

    DO NOT use this data for actual disaster preparedness or policy decisions.

Author: ResQ Shield Team
Phase:  9 — Expanded Static Dataset (~350 locations nationwide)
"""

import os
import pandas as pd
import numpy as np

# ─────────────────────────────────────────────
# Reproducibility
# ─────────────────────────────────────────────
np.random.seed(42)

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT_PATH  = os.path.join(PROJECT_ROOT, "data", "processed", "master_dataset.csv")


# ─────────────────────────────────────────────────────────────────────────────
# Location definitions
# Tuple: (district, state, lat, lon, profile_dict)
#
# Profile keys:
#   rainfall      : (min,max) mm/month — monsoon season average
#   river_level   : (min,max) 0–10 SYNTHETIC NORMALIZED INDEX (not metres)
#   soil_moisture : (min,max) 0–1 fraction
#   slope         : (min,max) degrees
#   elevation     : (min,max) metres ASL
#   flood_p       : probability used to stochastically generate flood_history (0/1)
#   ls_p          : probability for landslide_history (0/1)
# ─────────────────────────────────────────────────────────────────────────────

LOCATIONS = [

    # ══════════════════════════════════════════════════════════════════════════
    # UTTARAKHAND  (~25 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Dehradun",       "Uttarakhand",  30.3165, 78.0322,
     dict(rainfall=(180,260), river_level=(5,8),  soil_moisture=(0.55,0.75),
          slope=(5,18),  elevation=(620,700),   flood_p=0.70, ls_p=0.45)),
    ("Haridwar",       "Uttarakhand",  29.9457, 78.1642,
     dict(rainfall=(160,240), river_level=(6,9),  soil_moisture=(0.60,0.80),
          slope=(2,10),  elevation=(295,330),   flood_p=0.80, ls_p=0.30)),
    ("Rishikesh",      "Uttarakhand",  30.0869, 78.2676,
     dict(rainfall=(170,250), river_level=(5,8),  soil_moisture=(0.55,0.75),
          slope=(8,22),  elevation=(360,410),   flood_p=0.72, ls_p=0.50)),
    ("Mussoorie",      "Uttarakhand",  30.4598, 78.0664,
     dict(rainfall=(200,320), river_level=(3,6),  soil_moisture=(0.60,0.80),
          slope=(22,38), elevation=(1880,2060),  flood_p=0.30, ls_p=0.75)),
    ("Nainital",       "Uttarakhand",  29.3803, 79.4636,
     dict(rainfall=(180,280), river_level=(4,7),  soil_moisture=(0.60,0.78),
          slope=(20,35), elevation=(1980,2110),  flood_p=0.35, ls_p=0.72)),
    ("Haldwani",       "Uttarakhand",  29.2183, 79.5130,
     dict(rainfall=(160,240), river_level=(5,8),  soil_moisture=(0.55,0.73),
          slope=(3,10),  elevation=(420,470),   flood_p=0.65, ls_p=0.28)),
    ("Almora",         "Uttarakhand",  29.5892, 79.6467,
     dict(rainfall=(170,260), river_level=(3,6),  soil_moisture=(0.55,0.75),
          slope=(20,32), elevation=(1580,1680),  flood_p=0.30, ls_p=0.68)),
    ("Pithoragarh",    "Uttarakhand",  29.5826, 80.2181,
     dict(rainfall=(160,250), river_level=(4,7),  soil_moisture=(0.55,0.75),
          slope=(22,38), elevation=(1800,1920),  flood_p=0.32, ls_p=0.72)),
    ("Bageshwar",      "Uttarakhand",  29.8350, 79.7725,
     dict(rainfall=(170,260), river_level=(4,7),  soil_moisture=(0.58,0.76),
          slope=(20,34), elevation=(1000,1100),  flood_p=0.42, ls_p=0.70)),
    ("Champawat",      "Uttarakhand",  29.3333, 80.0917,
     dict(rainfall=(165,250), river_level=(3,6),  soil_moisture=(0.55,0.73),
          slope=(18,30), elevation=(1600,1720),  flood_p=0.30, ls_p=0.65)),
    ("Chamoli",        "Uttarakhand",  30.4021, 79.3239,
     dict(rainfall=(150,240), river_level=(5,8),  soil_moisture=(0.55,0.75),
          slope=(25,40), elevation=(1400,1600),  flood_p=0.50, ls_p=0.82)),
    ("Joshimath",      "Uttarakhand",  30.5584, 79.5637,
     dict(rainfall=(130,210), river_level=(4,7),  soil_moisture=(0.50,0.70),
          slope=(28,42), elevation=(1850,2000),  flood_p=0.38, ls_p=0.85)),
    ("Badrinath",      "Uttarakhand",  30.7433, 79.4938,
     dict(rainfall=(100,180), river_level=(4,7),  soil_moisture=(0.45,0.65),
          slope=(28,42), elevation=(3050,3200),  flood_p=0.30, ls_p=0.72)),
    ("Rudraprayag",    "Uttarakhand",  30.2862, 78.9814,
     dict(rainfall=(160,250), river_level=(5,8),  soil_moisture=(0.58,0.76),
          slope=(25,40), elevation=(900,1020),   flood_p=0.55, ls_p=0.80)),
    ("Uttarkashi",     "Uttarakhand",  30.7268, 78.4354,
     dict(rainfall=(140,230), river_level=(4,7),  soil_moisture=(0.52,0.72),
          slope=(25,40), elevation=(1100,1260),  flood_p=0.45, ls_p=0.78)),
    ("Gangotri",       "Uttarakhand",  30.9939, 78.9398,
     dict(rainfall=(90,160),  river_level=(3,6),  soil_moisture=(0.40,0.60),
          slope=(30,44), elevation=(3000,3200),  flood_p=0.25, ls_p=0.68)),
    ("Tehri Garhwal",  "Uttarakhand",  30.3749, 78.4804,
     dict(rainfall=(155,240), river_level=(5,8),  soil_moisture=(0.55,0.75),
          slope=(22,36), elevation=(770,900),    flood_p=0.60, ls_p=0.78)),
    ("New Tehri",      "Uttarakhand",  30.3927, 78.4835,
     dict(rainfall=(155,240), river_level=(5,8),  soil_moisture=(0.55,0.75),
          slope=(20,34), elevation=(820,940),    flood_p=0.55, ls_p=0.75)),
    ("Pauri",          "Uttarakhand",  29.8756, 78.7791,
     dict(rainfall=(160,250), river_level=(3,6),  soil_moisture=(0.55,0.73),
          slope=(20,34), elevation=(1680,1820),  flood_p=0.30, ls_p=0.70)),
    ("Srinagar Garhwal","Uttarakhand", 30.2231, 78.7808,
     dict(rainfall=(150,240), river_level=(5,8),  soil_moisture=(0.55,0.75),
          slope=(18,32), elevation=(550,640),    flood_p=0.60, ls_p=0.72)),
    ("Kotdwar",        "Uttarakhand",  29.7469, 78.5250,
     dict(rainfall=(170,260), river_level=(5,8),  soil_moisture=(0.58,0.76),
          slope=(10,22), elevation=(395,445),    flood_p=0.68, ls_p=0.55)),
    ("Devprayag",      "Uttarakhand",  30.1490, 78.5986,
     dict(rainfall=(155,245), river_level=(5,8),  soil_moisture=(0.56,0.74),
          slope=(22,36), elevation=(475,560),    flood_p=0.60, ls_p=0.76)),
    ("Karnaprayag",    "Uttarakhand",  30.2643, 79.2257,
     dict(rainfall=(145,235), river_level=(5,8),  soil_moisture=(0.55,0.73),
          slope=(24,38), elevation=(790,880),    flood_p=0.52, ls_p=0.78)),
    ("Gopeshwar",      "Uttarakhand",  30.4107, 79.3177,
     dict(rainfall=(150,240), river_level=(4,7),  soil_moisture=(0.54,0.72),
          slope=(22,36), elevation=(1320,1440),  flood_p=0.40, ls_p=0.76)),
    ("Lansdowne",      "Uttarakhand",  29.8409, 78.6850,
     dict(rainfall=(175,265), river_level=(3,6),  soil_moisture=(0.58,0.76),
          slope=(18,30), elevation=(1680,1820),  flood_p=0.30, ls_p=0.68)),

    # ══════════════════════════════════════════════════════════════════════════
    # HIMACHAL PRADESH  (~18 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Shimla",         "Himachal Pradesh", 31.1048, 77.1734,
     dict(rainfall=(160,250), river_level=(3,6),  soil_moisture=(0.55,0.73),
          slope=(22,36), elevation=(2180,2300),  flood_p=0.28, ls_p=0.72)),
    ("Kullu",          "Himachal Pradesh", 31.9592, 77.1089,
     dict(rainfall=(130,220), river_level=(4,7),  soil_moisture=(0.52,0.70),
          slope=(25,40), elevation=(1200,1350),  flood_p=0.40, ls_p=0.78)),
    ("Manali",         "Himachal Pradesh", 32.2432, 77.1892,
     dict(rainfall=(110,200), river_level=(4,7),  soil_moisture=(0.48,0.68),
          slope=(28,42), elevation=(2050,2200),  flood_p=0.38, ls_p=0.80)),
    ("Mandi",          "Himachal Pradesh", 31.7089, 76.9320,
     dict(rainfall=(140,230), river_level=(5,8),  soil_moisture=(0.55,0.73),
          slope=(20,34), elevation=(850,980),    flood_p=0.55, ls_p=0.72)),
    ("Dharamsala",     "Himachal Pradesh", 32.2190, 76.3234,
     dict(rainfall=(190,310), river_level=(4,7),  soil_moisture=(0.60,0.80),
          slope=(20,34), elevation=(1380,1500),  flood_p=0.35, ls_p=0.78)),
    ("Kangra",         "Himachal Pradesh", 32.0998, 76.2691,
     dict(rainfall=(180,280), river_level=(5,8),  soil_moisture=(0.58,0.76),
          slope=(15,28), elevation=(620,720),    flood_p=0.55, ls_p=0.65)),
    ("Chamba",         "Himachal Pradesh", 32.5534, 76.1258,
     dict(rainfall=(150,240), river_level=(4,7),  soil_moisture=(0.52,0.72),
          slope=(25,40), elevation=(900,1020),   flood_p=0.42, ls_p=0.78)),
    ("Kinnaur",        "Himachal Pradesh", 31.5925, 78.2730,
     dict(rainfall=(80,150),  river_level=(3,6),  soil_moisture=(0.38,0.58),
          slope=(28,42), elevation=(2300,2600),  flood_p=0.30, ls_p=0.72)),
    ("Solan",          "Himachal Pradesh", 30.9045, 77.0967,
     dict(rainfall=(150,230), river_level=(3,5),  soil_moisture=(0.52,0.70),
          slope=(18,30), elevation=(1340,1440),  flood_p=0.28, ls_p=0.65)),
    ("Bilaspur",       "Himachal Pradesh", 31.3393, 76.7575,
     dict(rainfall=(140,220), river_level=(4,7),  soil_moisture=(0.52,0.70),
          slope=(12,24), elevation=(660,760),    flood_p=0.48, ls_p=0.55)),
    ("Hamirpur",       "Himachal Pradesh", 31.6862, 76.5215,
     dict(rainfall=(140,220), river_level=(3,6),  soil_moisture=(0.50,0.68),
          slope=(10,22), elevation=(680,780),    flood_p=0.42, ls_p=0.50)),
    ("Una",            "Himachal Pradesh", 31.4685, 76.2688,
     dict(rainfall=(140,220), river_level=(4,6),  soil_moisture=(0.50,0.68),
          slope=(5,15),  elevation=(370,440),    flood_p=0.45, ls_p=0.35)),
    ("Palampur",       "Himachal Pradesh", 32.1098, 76.5341,
     dict(rainfall=(180,280), river_level=(4,7),  soil_moisture=(0.60,0.78),
          slope=(15,28), elevation=(1220,1340),  flood_p=0.38, ls_p=0.68)),
    ("Nahan",          "Himachal Pradesh", 30.5593, 77.2950,
     dict(rainfall=(160,250), river_level=(3,6),  soil_moisture=(0.55,0.73),
          slope=(18,30), elevation=(900,1020),   flood_p=0.32, ls_p=0.65)),
    ("Keylong",        "Himachal Pradesh", 32.5745, 77.0355,
     dict(rainfall=(50,110),  river_level=(2,5),  soil_moisture=(0.25,0.45),
          slope=(25,40), elevation=(3080,3200),  flood_p=0.20, ls_p=0.55)),
    ("Kaza",           "Himachal Pradesh", 32.2269, 78.0686,
     dict(rainfall=(20,60),   river_level=(1,3),  soil_moisture=(0.10,0.25),
          slope=(20,35), elevation=(3650,3800),  flood_p=0.10, ls_p=0.42)),
    ("Reckong Peo",    "Himachal Pradesh", 31.5328, 78.2730,
     dict(rainfall=(70,140),  river_level=(3,5),  soil_moisture=(0.32,0.52),
          slope=(26,40), elevation=(2290,2420),  flood_p=0.25, ls_p=0.68)),
    ("Dalhousie",      "Himachal Pradesh", 32.5383, 75.9745,
     dict(rainfall=(180,280), river_level=(3,6),  soil_moisture=(0.58,0.76),
          slope=(22,36), elevation=(2020,2160),  flood_p=0.25, ls_p=0.72)),

    # ══════════════════════════════════════════════════════════════════════════
    # JAMMU & KASHMIR  (~15 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Srinagar",       "Jammu & Kashmir", 34.0837, 74.7973,
     dict(rainfall=(80,140),  river_level=(4,7),  soil_moisture=(0.45,0.65),
          slope=(5,18),  elevation=(1580,1640),  flood_p=0.55, ls_p=0.40)),
    ("Jammu",          "Jammu & Kashmir", 32.7266, 74.8570,
     dict(rainfall=(120,200), river_level=(4,7),  soil_moisture=(0.48,0.68),
          slope=(8,20),  elevation=(320,400),    flood_p=0.58, ls_p=0.45)),
    ("Anantnag",       "Jammu & Kashmir", 33.7311, 75.1487,
     dict(rainfall=(90,160),  river_level=(4,7),  soil_moisture=(0.48,0.68),
          slope=(15,28), elevation=(1800,1920),  flood_p=0.48, ls_p=0.62)),
    ("Baramulla",      "Jammu & Kashmir", 34.1985, 74.3431,
     dict(rainfall=(90,160),  river_level=(4,7),  soil_moisture=(0.48,0.68),
          slope=(18,32), elevation=(1550,1680),  flood_p=0.48, ls_p=0.65)),
    ("Pulwama",        "Jammu & Kashmir", 33.8748, 74.8985,
     dict(rainfall=(85,150),  river_level=(3,6),  soil_moisture=(0.45,0.65),
          slope=(10,24), elevation=(1620,1740),  flood_p=0.42, ls_p=0.55)),
    ("Shopian",        "Jammu & Kashmir", 33.7152, 74.8330,
     dict(rainfall=(85,155),  river_level=(3,6),  soil_moisture=(0.45,0.65),
          slope=(12,26), elevation=(1600,1720),  flood_p=0.40, ls_p=0.58)),
    ("Kupwara",        "Jammu & Kashmir", 34.5218, 74.2606,
     dict(rainfall=(100,175), river_level=(4,7),  soil_moisture=(0.50,0.70),
          slope=(20,34), elevation=(1610,1750),  flood_p=0.45, ls_p=0.68)),
    ("Pahalgam",       "Jammu & Kashmir", 34.0160, 75.3158,
     dict(rainfall=(100,180), river_level=(4,7),  soil_moisture=(0.50,0.70),
          slope=(22,36), elevation=(2130,2250),  flood_p=0.38, ls_p=0.72)),
    ("Udhampur",       "Jammu & Kashmir", 32.9084, 75.1413,
     dict(rainfall=(120,200), river_level=(3,6),  soil_moisture=(0.48,0.68),
          slope=(15,28), elevation=(720,840),    flood_p=0.45, ls_p=0.60)),
    ("Kathua",         "Jammu & Kashmir", 32.3803, 75.5152,
     dict(rainfall=(120,200), river_level=(4,7),  soil_moisture=(0.50,0.70),
          slope=(10,22), elevation=(380,460),    flood_p=0.52, ls_p=0.48)),
    ("Rajouri",        "Jammu & Kashmir", 33.3812, 74.3094,
     dict(rainfall=(110,185), river_level=(3,6),  soil_moisture=(0.45,0.65),
          slope=(18,32), elevation=(860,980),    flood_p=0.42, ls_p=0.62)),
    ("Poonch",         "Jammu & Kashmir", 33.7748, 74.0932,
     dict(rainfall=(115,195), river_level=(3,6),  soil_moisture=(0.46,0.66),
          slope=(20,34), elevation=(1000,1120),  flood_p=0.40, ls_p=0.65)),
    ("Kishtwar",       "Jammu & Kashmir", 33.3128, 75.7717,
     dict(rainfall=(110,190), river_level=(4,7),  soil_moisture=(0.48,0.68),
          slope=(28,42), elevation=(1650,1800),  flood_p=0.42, ls_p=0.78)),
    ("Doda",           "Jammu & Kashmir", 33.1483, 75.5472,
     dict(rainfall=(115,195), river_level=(4,7),  soil_moisture=(0.48,0.68),
          slope=(25,40), elevation=(1080,1200),  flood_p=0.42, ls_p=0.72)),
    ("Ramban",         "Jammu & Kashmir", 33.2408, 75.2315,
     dict(rainfall=(120,200), river_level=(4,7),  soil_moisture=(0.50,0.70),
          slope=(28,42), elevation=(820,940),    flood_p=0.45, ls_p=0.80)),

    # ══════════════════════════════════════════════════════════════════════════
    # LADAKH  (~6 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Leh",            "Ladakh",  34.1526, 77.5771,
     dict(rainfall=(8,20),    river_level=(1,3),  soil_moisture=(0.05,0.15),
          slope=(5,18),  elevation=(3490,3570),  flood_p=0.12, ls_p=0.20)),
    ("Kargil",         "Ladakh",  34.5551, 76.1349,
     dict(rainfall=(10,25),   river_level=(1,3),  soil_moisture=(0.06,0.16),
          slope=(8,22),  elevation=(2650,2760),  flood_p=0.12, ls_p=0.25)),
    ("Drass",          "Ladakh",  34.4314, 75.7556,
     dict(rainfall=(15,35),   river_level=(1,3),  soil_moisture=(0.08,0.20),
          slope=(18,32), elevation=(3240,3360),  flood_p=0.15, ls_p=0.32)),
    ("Diskit",         "Ladakh",  34.7130, 77.5863,
     dict(rainfall=(5,15),    river_level=(1,2),  soil_moisture=(0.04,0.12),
          slope=(10,24), elevation=(3100,3200),  flood_p=0.10, ls_p=0.18)),
    ("Nubra",          "Ladakh",  34.6630, 77.5590,
     dict(rainfall=(5,15),    river_level=(1,2),  soil_moisture=(0.04,0.12),
          slope=(12,26), elevation=(3000,3150),  flood_p=0.10, ls_p=0.20)),
    ("Padum",          "Ladakh",  33.4686, 77.2739,
     dict(rainfall=(12,28),   river_level=(1,3),  soil_moisture=(0.06,0.18),
          slope=(18,32), elevation=(3490,3620),  flood_p=0.12, ls_p=0.30)),

    # ══════════════════════════════════════════════════════════════════════════
    # SIKKIM  (~5 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Gangtok",        "Sikkim",  27.3314, 88.6138,
     dict(rainfall=(250,380), river_level=(4,7),  soil_moisture=(0.70,0.88),
          slope=(25,38), elevation=(1580,1700),  flood_p=0.40, ls_p=0.85)),
    ("Namchi",         "Sikkim",  27.1663, 88.3640,
     dict(rainfall=(240,360), river_level=(3,6),  soil_moisture=(0.68,0.86),
          slope=(25,38), elevation=(1380,1500),  flood_p=0.38, ls_p=0.82)),
    ("Gyalshing",      "Sikkim",  27.2833, 88.2583,
     dict(rainfall=(230,350), river_level=(3,6),  soil_moisture=(0.68,0.86),
          slope=(28,40), elevation=(1780,1900),  flood_p=0.35, ls_p=0.82)),
    ("Mangan",         "Sikkim",  27.5096, 88.5316,
     dict(rainfall=(260,390), river_level=(4,7),  soil_moisture=(0.72,0.90),
          slope=(28,42), elevation=(1330,1460),  flood_p=0.42, ls_p=0.88)),
    ("Rangpo",         "Sikkim",  27.1765, 88.5364,
     dict(rainfall=(240,360), river_level=(5,8),  soil_moisture=(0.68,0.86),
          slope=(18,32), elevation=(330,400),    flood_p=0.58, ls_p=0.75)),

    # ══════════════════════════════════════════════════════════════════════════
    # ARUNACHAL PRADESH  (~9 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Itanagar",       "Arunachal Pradesh", 27.0844, 93.6053,
     dict(rainfall=(280,420), river_level=(5,8),  soil_moisture=(0.72,0.90),
          slope=(20,34), elevation=(320,420),    flood_p=0.68, ls_p=0.80)),
    ("Tawang",         "Arunachal Pradesh", 27.5859, 91.8594,
     dict(rainfall=(180,280), river_level=(3,6),  soil_moisture=(0.58,0.78),
          slope=(28,42), elevation=(2680,2820),  flood_p=0.30, ls_p=0.78)),
    ("Bomdila",        "Arunachal Pradesh", 27.2653, 92.4181,
     dict(rainfall=(220,340), river_level=(4,7),  soil_moisture=(0.65,0.83),
          slope=(25,38), elevation=(2220,2360),  flood_p=0.35, ls_p=0.80)),
    ("Pasighat",       "Arunachal Pradesh", 28.0665, 95.3314,
     dict(rainfall=(300,450), river_level=(6,9),  soil_moisture=(0.75,0.92),
          slope=(12,25), elevation=(145,200),    flood_p=0.80, ls_p=0.60)),
    ("Ziro",           "Arunachal Pradesh", 27.5451, 93.8198,
     dict(rainfall=(250,380), river_level=(4,7),  soil_moisture=(0.70,0.88),
          slope=(15,28), elevation=(1580,1700),  flood_p=0.48, ls_p=0.72)),
    ("Aalo",           "Arunachal Pradesh", 28.1668, 94.8027,
     dict(rainfall=(280,420), river_level=(5,8),  soil_moisture=(0.72,0.90),
          slope=(18,32), elevation=(280,380),    flood_p=0.70, ls_p=0.70)),
    ("Tezu",           "Arunachal Pradesh", 27.9167, 96.1667,
     dict(rainfall=(260,390), river_level=(5,8),  soil_moisture=(0.70,0.88),
          slope=(8,22),  elevation=(200,280),    flood_p=0.72, ls_p=0.58)),
    ("Roing",          "Arunachal Pradesh", 28.1394, 95.8441,
     dict(rainfall=(260,380), river_level=(5,8),  soil_moisture=(0.70,0.88),
          slope=(12,26), elevation=(300,400),    flood_p=0.68, ls_p=0.62)),
    ("Seppa",          "Arunachal Pradesh", 26.9058, 92.9847,
     dict(rainfall=(270,400), river_level=(5,8),  soil_moisture=(0.72,0.90),
          slope=(20,34), elevation=(360,460),    flood_p=0.70, ls_p=0.75)),

    # ══════════════════════════════════════════════════════════════════════════
    # ASSAM  (~16 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Guwahati",       "Assam", 26.1445, 91.7362,
     dict(rainfall=(260,380), river_level=(6,9),  soil_moisture=(0.72,0.90),
          slope=(5,15),  elevation=(50,80),      flood_p=0.82, ls_p=0.35)),
    ("Dibrugarh",      "Assam", 27.4728, 94.9120,
     dict(rainfall=(280,420), river_level=(7,9),  soil_moisture=(0.75,0.92),
          slope=(3,10),  elevation=(100,140),    flood_p=0.88, ls_p=0.28)),
    ("Jorhat",         "Assam", 26.7509, 94.2037,
     dict(rainfall=(270,400), river_level=(6,9),  soil_moisture=(0.72,0.90),
          slope=(2,8),   elevation=(85,120),     flood_p=0.85, ls_p=0.22)),
    ("Silchar",        "Assam", 24.8333, 92.7789,
     dict(rainfall=(300,450), river_level=(6,9),  soil_moisture=(0.75,0.92),
          slope=(3,10),  elevation=(30,65),      flood_p=0.85, ls_p=0.40)),
    ("Tezpur",         "Assam", 26.6338, 92.7926,
     dict(rainfall=(270,400), river_level=(6,9),  soil_moisture=(0.72,0.90),
          slope=(3,10),  elevation=(65,100),     flood_p=0.85, ls_p=0.30)),
    ("Dhemaji",        "Assam", 27.4790, 94.5617,
     dict(rainfall=(290,430), river_level=(7,9),  soil_moisture=(0.78,0.95),
          slope=(1,5),   elevation=(90,125),     flood_p=0.92, ls_p=0.15)),
    ("Lakhimpur",      "Assam", 27.2362, 94.1029,
     dict(rainfall=(280,420), river_level=(7,9),  soil_moisture=(0.76,0.93),
          slope=(2,8),   elevation=(80,120),     flood_p=0.90, ls_p=0.18)),
    ("Majuli",         "Assam", 26.9500, 94.1667,
     dict(rainfall=(290,440), river_level=(7,9),  soil_moisture=(0.80,0.97),
          slope=(0,3),   elevation=(85,110),     flood_p=0.95, ls_p=0.08)),
    ("Goalpara",       "Assam", 26.1671, 90.6222,
     dict(rainfall=(260,380), river_level=(6,9),  soil_moisture=(0.72,0.90),
          slope=(2,8),   elevation=(40,75),      flood_p=0.82, ls_p=0.30)),
    ("Dhubri",         "Assam", 26.0236, 89.9834,
     dict(rainfall=(260,380), river_level=(7,9),  soil_moisture=(0.76,0.93),
          slope=(0,4),   elevation=(30,60),      flood_p=0.90, ls_p=0.15)),
    ("Tinsukia",       "Assam", 27.4892, 95.3631,
     dict(rainfall=(280,420), river_level=(6,9),  soil_moisture=(0.74,0.91),
          slope=(3,10),  elevation=(110,150),    flood_p=0.85, ls_p=0.25)),
    ("Sivasagar",      "Assam", 26.9870, 94.6373,
     dict(rainfall=(270,400), river_level=(6,9),  soil_moisture=(0.72,0.90),
          slope=(2,8),   elevation=(90,125),     flood_p=0.82, ls_p=0.22)),
    ("Nagaon",         "Assam", 26.3471, 92.6862,
     dict(rainfall=(265,390), river_level=(6,9),  soil_moisture=(0.72,0.90),
          slope=(1,6),   elevation=(60,90),      flood_p=0.85, ls_p=0.20)),
    ("Barpeta",        "Assam", 26.3222, 91.0056,
     dict(rainfall=(260,380), river_level=(6,9),  soil_moisture=(0.72,0.90),
          slope=(1,5),   elevation=(40,70),      flood_p=0.88, ls_p=0.18)),
    ("Bongaigaon",     "Assam", 26.4810, 90.5582,
     dict(rainfall=(255,375), river_level=(6,9),  soil_moisture=(0.70,0.88),
          slope=(2,8),   elevation=(45,80),      flood_p=0.82, ls_p=0.25)),
    ("Karimganj",      "Assam", 24.8665, 92.3602,
     dict(rainfall=(290,430), river_level=(6,9),  soil_moisture=(0.74,0.91),
          slope=(3,12),  elevation=(20,55),      flood_p=0.85, ls_p=0.38)),

    # ══════════════════════════════════════════════════════════════════════════
    # MEGHALAYA  (~6 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Shillong",       "Meghalaya", 25.5788, 91.8933,
     dict(rainfall=(300,480), river_level=(4,7),  soil_moisture=(0.75,0.92),
          slope=(18,32), elevation=(1490,1620),  flood_p=0.42, ls_p=0.82)),
    ("Cherrapunji",    "Meghalaya", 25.2844, 91.7033,
     dict(rainfall=(800,1200),river_level=(5,8),  soil_moisture=(0.88,0.99),
          slope=(22,36), elevation=(1280,1400),  flood_p=0.55, ls_p=0.88)),
    ("Mawsynram",      "Meghalaya", 25.2976, 91.5835,
     dict(rainfall=(850,1200),river_level=(5,8),  soil_moisture=(0.90,0.99),
          slope=(20,34), elevation=(1380,1480),  flood_p=0.52, ls_p=0.88)),
    ("Tura",           "Meghalaya", 25.5151, 90.2132,
     dict(rainfall=(320,480), river_level=(5,8),  soil_moisture=(0.76,0.93),
          slope=(20,34), elevation=(310,420),    flood_p=0.65, ls_p=0.80)),
    ("Jowai",          "Meghalaya", 25.4518, 92.2043,
     dict(rainfall=(310,460), river_level=(4,7),  soil_moisture=(0.75,0.92),
          slope=(18,32), elevation=(1310,1440),  flood_p=0.45, ls_p=0.82)),
    ("Nongpoh",        "Meghalaya", 25.9055, 92.0002,
     dict(rainfall=(290,440), river_level=(4,7),  soil_moisture=(0.73,0.90),
          slope=(15,28), elevation=(820,940),    flood_p=0.50, ls_p=0.78)),

    # ══════════════════════════════════════════════════════════════════════════
    # MIZORAM  (~4 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Aizawl",         "Mizoram", 23.7307, 92.7173,
     dict(rainfall=(280,420), river_level=(3,6),  soil_moisture=(0.70,0.88),
          slope=(25,38), elevation=(1100,1200),  flood_p=0.38, ls_p=0.82)),
    ("Lunglei",        "Mizoram", 22.8894, 92.7340,
     dict(rainfall=(280,420), river_level=(3,6),  soil_moisture=(0.70,0.88),
          slope=(28,40), elevation=(1040,1160),  flood_p=0.38, ls_p=0.82)),
    ("Champhai",       "Mizoram", 23.4724, 93.3262,
     dict(rainfall=(250,380), river_level=(3,6),  soil_moisture=(0.68,0.86),
          slope=(25,38), elevation=(1450,1580),  flood_p=0.32, ls_p=0.78)),
    ("Kolasib",        "Mizoram", 24.2249, 92.6791,
     dict(rainfall=(270,400), river_level=(3,6),  soil_moisture=(0.70,0.88),
          slope=(22,36), elevation=(640,740),    flood_p=0.42, ls_p=0.78)),

    # ══════════════════════════════════════════════════════════════════════════
    # NAGALAND  (~5 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Kohima",         "Nagaland", 25.6751, 94.1086,
     dict(rainfall=(240,360), river_level=(3,6),  soil_moisture=(0.68,0.86),
          slope=(22,36), elevation=(1440,1560),  flood_p=0.32, ls_p=0.78)),
    ("Dimapur",        "Nagaland", 25.9066, 93.7264,
     dict(rainfall=(240,360), river_level=(5,8),  soil_moisture=(0.68,0.86),
          slope=(5,15),  elevation=(230,290),    flood_p=0.68, ls_p=0.45)),
    ("Mokokchung",     "Nagaland", 26.3260, 94.5147,
     dict(rainfall=(230,350), river_level=(3,6),  soil_moisture=(0.66,0.84),
          slope=(20,34), elevation=(1280,1400),  flood_p=0.32, ls_p=0.72)),
    ("Mon",            "Nagaland", 26.7266, 95.0212,
     dict(rainfall=(220,340), river_level=(3,6),  soil_moisture=(0.65,0.83),
          slope=(18,32), elevation=(880,1000),   flood_p=0.35, ls_p=0.68)),
    ("Wokha",          "Nagaland", 26.1011, 94.2618,
     dict(rainfall=(230,350), river_level=(3,6),  soil_moisture=(0.66,0.84),
          slope=(20,34), elevation=(1280,1400),  flood_p=0.32, ls_p=0.72)),

    # ══════════════════════════════════════════════════════════════════════════
    # MANIPUR  (~5 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Imphal",         "Manipur", 24.8170, 93.9368,
     dict(rainfall=(200,310), river_level=(4,7),  soil_moisture=(0.65,0.83),
          slope=(5,18),  elevation=(780,860),    flood_p=0.60, ls_p=0.50)),
    ("Churachandpur",  "Manipur", 24.3333, 93.6833,
     dict(rainfall=(210,320), river_level=(3,6),  soil_moisture=(0.65,0.83),
          slope=(20,34), elevation=(900,1020),   flood_p=0.42, ls_p=0.70)),
    ("Ukhrul",         "Manipur", 25.0969, 94.3575,
     dict(rainfall=(210,320), river_level=(3,6),  soil_moisture=(0.65,0.83),
          slope=(22,36), elevation=(1750,1880),  flood_p=0.32, ls_p=0.75)),
    ("Senapati",       "Manipur", 25.2677, 94.0150,
     dict(rainfall=(210,320), river_level=(3,6),  soil_moisture=(0.65,0.83),
          slope=(18,32), elevation=(1440,1580),  flood_p=0.35, ls_p=0.72)),
    ("Thoubal",        "Manipur", 24.6416, 93.9951,
     dict(rainfall=(200,310), river_level=(4,7),  soil_moisture=(0.65,0.83),
          slope=(3,12),  elevation=(780,860),    flood_p=0.65, ls_p=0.42)),

    # ══════════════════════════════════════════════════════════════════════════
    # TRIPURA  (~4 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Agartala",       "Tripura", 23.8315, 91.2868,
     dict(rainfall=(240,360), river_level=(5,8),  soil_moisture=(0.70,0.88),
          slope=(5,15),  elevation=(12,40),      flood_p=0.78, ls_p=0.40)),
    ("Dharmanagar",    "Tripura", 24.3780, 92.1680,
     dict(rainfall=(240,360), river_level=(4,7),  soil_moisture=(0.68,0.86),
          slope=(8,20),  elevation=(30,70),      flood_p=0.72, ls_p=0.48)),
    ("Udaipur",        "Tripura", 23.5369, 91.4882,
     dict(rainfall=(240,360), river_level=(4,7),  soil_moisture=(0.68,0.86),
          slope=(5,15),  elevation=(15,45),      flood_p=0.75, ls_p=0.42)),
    ("Kailashahar",    "Tripura", 24.3320, 92.0090,
     dict(rainfall=(240,360), river_level=(4,7),  soil_moisture=(0.68,0.86),
          slope=(5,15),  elevation=(25,60),      flood_p=0.72, ls_p=0.45)),

    # ══════════════════════════════════════════════════════════════════════════
    # WEST BENGAL  (~13 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Kolkata",        "West Bengal", 22.5726, 88.3639,
     dict(rainfall=(200,300), river_level=(6,9),  soil_moisture=(0.70,0.88),
          slope=(0,3),   elevation=(5,20),       flood_p=0.82, ls_p=0.08)),
    ("Howrah",         "West Bengal", 22.5958, 88.2636,
     dict(rainfall=(200,300), river_level=(6,9),  soil_moisture=(0.70,0.88),
          slope=(0,3),   elevation=(8,22),       flood_p=0.82, ls_p=0.08)),
    ("Siliguri",       "West Bengal", 26.7271, 88.3953,
     dict(rainfall=(280,420), river_level=(6,9),  soil_moisture=(0.72,0.90),
          slope=(5,15),  elevation=(120,170),    flood_p=0.80, ls_p=0.40)),
    ("Darjeeling",     "West Bengal", 27.0360, 88.2627,
     dict(rainfall=(280,430), river_level=(3,6),  soil_moisture=(0.72,0.90),
          slope=(28,42), elevation=(2040,2180),  flood_p=0.30, ls_p=0.88)),
    ("Kalimpong",      "West Bengal", 27.0660, 88.4688,
     dict(rainfall=(260,400), river_level=(3,6),  soil_moisture=(0.70,0.88),
          slope=(26,40), elevation=(1220,1360),  flood_p=0.32, ls_p=0.85)),
    ("Jalpaiguri",     "West Bengal", 26.5433, 88.7275,
     dict(rainfall=(280,420), river_level=(6,9),  soil_moisture=(0.74,0.91),
          slope=(2,8),   elevation=(75,115),     flood_p=0.85, ls_p=0.28)),
    ("Alipurduar",     "West Bengal", 26.4920, 89.5280,
     dict(rainfall=(290,440), river_level=(6,9),  soil_moisture=(0.75,0.92),
          slope=(2,8),   elevation=(65,100),     flood_p=0.88, ls_p=0.25)),
    ("Malda",          "West Bengal", 25.0108, 88.1434,
     dict(rainfall=(200,300), river_level=(6,9),  soil_moisture=(0.68,0.86),
          slope=(0,4),   elevation=(25,50),      flood_p=0.82, ls_p=0.12)),
    ("Murshidabad",    "West Bengal", 24.1834, 88.2490,
     dict(rainfall=(180,270), river_level=(6,9),  soil_moisture=(0.66,0.84),
          slope=(0,3),   elevation=(20,45),      flood_p=0.82, ls_p=0.10)),
    ("Durgapur",       "West Bengal", 23.5204, 87.3119,
     dict(rainfall=(170,250), river_level=(5,8),  soil_moisture=(0.58,0.76),
          slope=(2,8),   elevation=(50,90),      flood_p=0.68, ls_p=0.12)),
    ("Asansol",        "West Bengal", 23.6843, 86.9944,
     dict(rainfall=(170,250), river_level=(5,8),  soil_moisture=(0.58,0.76),
          slope=(3,10),  elevation=(100,150),    flood_p=0.62, ls_p=0.15)),
    ("Digha",          "West Bengal", 21.6281, 87.5052,
     dict(rainfall=(180,280), river_level=(6,8),  soil_moisture=(0.68,0.86),
          slope=(0,3),   elevation=(4,15),       flood_p=0.78, ls_p=0.08)),
    ("Cooch Behar",    "West Bengal", 26.3274, 89.4451,
     dict(rainfall=(280,420), river_level=(6,9),  soil_moisture=(0.74,0.91),
          slope=(1,5),   elevation=(45,80),      flood_p=0.88, ls_p=0.18)),

    # ══════════════════════════════════════════════════════════════════════════
    # BIHAR  (~14 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Patna",          "Bihar", 25.5941, 85.1376,
     dict(rainfall=(160,240), river_level=(7,9),  soil_moisture=(0.65,0.83),
          slope=(0,3),   elevation=(50,70),      flood_p=0.85, ls_p=0.05)),
    ("Muzaffarpur",    "Bihar", 26.1209, 85.3647,
     dict(rainfall=(170,250), river_level=(7,9),  soil_moisture=(0.68,0.86),
          slope=(0,3),   elevation=(52,72),      flood_p=0.88, ls_p=0.05)),
    ("Darbhanga",      "Bihar", 26.1542, 85.8918,
     dict(rainfall=(170,255), river_level=(7,9),  soil_moisture=(0.70,0.88),
          slope=(0,2),   elevation=(45,65),      flood_p=0.90, ls_p=0.04)),
    ("Sitamarhi",      "Bihar", 26.5917, 85.4799,
     dict(rainfall=(175,260), river_level=(7,9),  soil_moisture=(0.70,0.88),
          slope=(0,2),   elevation=(58,78),      flood_p=0.90, ls_p=0.04)),
    ("Madhubani",      "Bihar", 26.3530, 86.0726,
     dict(rainfall=(175,260), river_level=(7,9),  soil_moisture=(0.72,0.90),
          slope=(0,2),   elevation=(50,70),      flood_p=0.92, ls_p=0.04)),
    ("Supaul",         "Bihar", 26.1227, 86.5989,
     dict(rainfall=(175,260), river_level=(7,9),  soil_moisture=(0.72,0.90),
          slope=(0,2),   elevation=(47,67),      flood_p=0.90, ls_p=0.04)),
    ("Saharsa",        "Bihar", 25.8810, 86.5966,
     dict(rainfall=(170,250), river_level=(7,9),  soil_moisture=(0.68,0.86),
          slope=(0,2),   elevation=(40,60),      flood_p=0.88, ls_p=0.04)),
    ("Purnia",         "Bihar", 25.7771, 87.4753,
     dict(rainfall=(185,270), river_level=(7,9),  soil_moisture=(0.70,0.88),
          slope=(0,3),   elevation=(36,58),      flood_p=0.88, ls_p=0.05)),
    ("Katihar",        "Bihar", 25.5400, 87.5700,
     dict(rainfall=(185,270), river_level=(7,9),  soil_moisture=(0.70,0.88),
          slope=(0,3),   elevation=(30,55),      flood_p=0.88, ls_p=0.05)),
    ("Bhagalpur",      "Bihar", 25.2425, 86.9842,
     dict(rainfall=(170,255), river_level=(6,9),  soil_moisture=(0.65,0.83),
          slope=(0,3),   elevation=(40,65),      flood_p=0.82, ls_p=0.05)),
    ("Begusarai",      "Bihar", 25.4182, 86.1272,
     dict(rainfall=(165,245), river_level=(6,9),  soil_moisture=(0.65,0.83),
          slope=(0,3),   elevation=(40,60),      flood_p=0.82, ls_p=0.05)),
    ("Samastipur",     "Bihar", 25.8625, 85.7812,
     dict(rainfall=(165,245), river_level=(7,9),  soil_moisture=(0.67,0.85),
          slope=(0,2),   elevation=(44,64),      flood_p=0.85, ls_p=0.04)),
    ("Gopalganj",      "Bihar", 26.4678, 84.4343,
     dict(rainfall=(165,245), river_level=(6,9),  soil_moisture=(0.65,0.83),
          slope=(0,2),   elevation=(62,82),      flood_p=0.82, ls_p=0.04)),
    ("Motihari",       "Bihar", 26.6503, 84.9175,
     dict(rainfall=(170,250), river_level=(6,9),  soil_moisture=(0.65,0.83),
          slope=(0,2),   elevation=(72,92),      flood_p=0.82, ls_p=0.04)),

    # ══════════════════════════════════════════════════════════════════════════
    # UTTAR PRADESH  (~16 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Lucknow",        "Uttar Pradesh", 26.8467, 80.9462,
     dict(rainfall=(150,220), river_level=(5,8),  soil_moisture=(0.50,0.70),
          slope=(0,2),   elevation=(110,130),    flood_p=0.60, ls_p=0.05)),
    ("Varanasi",       "Uttar Pradesh", 25.3176, 82.9739,
     dict(rainfall=(150,200), river_level=(6,9),  soil_moisture=(0.55,0.75),
          slope=(0,3),   elevation=(75,95),      flood_p=0.70, ls_p=0.05)),
    ("Prayagraj",      "Uttar Pradesh", 25.4358, 81.8463,
     dict(rainfall=(140,200), river_level=(6,9),  soil_moisture=(0.55,0.75),
          slope=(0,3),   elevation=(90,115),     flood_p=0.70, ls_p=0.05)),
    ("Agra",           "Uttar Pradesh", 27.1767, 78.0081,
     dict(rainfall=(90,140),  river_level=(3,6),  soil_moisture=(0.35,0.55),
          slope=(0,2),   elevation=(165,185),    flood_p=0.35, ls_p=0.05)),
    ("Kanpur",         "Uttar Pradesh", 26.4499, 80.3319,
     dict(rainfall=(130,190), river_level=(5,8),  soil_moisture=(0.50,0.70),
          slope=(0,2),   elevation=(120,145),    flood_p=0.58, ls_p=0.05)),
    ("Gorakhpur",      "Uttar Pradesh", 26.7606, 83.3732,
     dict(rainfall=(175,260), river_level=(7,9),  soil_moisture=(0.65,0.83),
          slope=(0,2),   elevation=(75,95),      flood_p=0.85, ls_p=0.05)),
    ("Ayodhya",        "Uttar Pradesh", 26.7922, 82.1998,
     dict(rainfall=(160,240), river_level=(6,9),  soil_moisture=(0.60,0.78),
          slope=(0,2),   elevation=(95,115),     flood_p=0.78, ls_p=0.05)),
    ("Ballia",         "Uttar Pradesh", 25.7531, 84.1467,
     dict(rainfall=(165,245), river_level=(7,9),  soil_moisture=(0.65,0.83),
          slope=(0,2),   elevation=(55,75),      flood_p=0.85, ls_p=0.05)),
    ("Bahraich",       "Uttar Pradesh", 27.5741, 81.5960,
     dict(rainfall=(175,260), river_level=(6,9),  soil_moisture=(0.62,0.80),
          slope=(0,3),   elevation=(115,140),    flood_p=0.80, ls_p=0.05)),
    ("Gonda",          "Uttar Pradesh", 27.1346, 81.9600,
     dict(rainfall=(165,245), river_level=(6,9),  soil_moisture=(0.60,0.78),
          slope=(0,2),   elevation=(108,130),    flood_p=0.78, ls_p=0.05)),
    ("Kushinagar",     "Uttar Pradesh", 26.7393, 83.8897,
     dict(rainfall=(175,260), river_level=(6,9),  soil_moisture=(0.65,0.83),
          slope=(0,2),   elevation=(74,94),      flood_p=0.82, ls_p=0.05)),
    ("Mathura",        "Uttar Pradesh", 27.4924, 77.6737,
     dict(rainfall=(90,140),  river_level=(3,6),  soil_moisture=(0.35,0.55),
          slope=(0,2),   elevation=(170,190),    flood_p=0.38, ls_p=0.05)),
    ("Bareilly",       "Uttar Pradesh", 28.3670, 79.4304,
     dict(rainfall=(130,200), river_level=(4,7),  soil_moisture=(0.50,0.70),
          slope=(0,3),   elevation=(170,200),    flood_p=0.55, ls_p=0.05)),
    ("Meerut",         "Uttar Pradesh", 28.9845, 77.7064,
     dict(rainfall=(110,180), river_level=(4,7),  soil_moisture=(0.45,0.65),
          slope=(0,3),   elevation=(220,250),    flood_p=0.50, ls_p=0.05)),
    ("Noida",          "Uttar Pradesh", 28.5355, 77.3910,
     dict(rainfall=(100,160), river_level=(4,7),  soil_moisture=(0.42,0.62),
          slope=(0,2),   elevation=(195,220),    flood_p=0.48, ls_p=0.05)),
    ("Basti",          "Uttar Pradesh", 26.8004, 82.7181,
     dict(rainfall=(165,245), river_level=(6,9),  soil_moisture=(0.62,0.80),
          slope=(0,2),   elevation=(90,115),     flood_p=0.78, ls_p=0.05)),

    # ══════════════════════════════════════════════════════════════════════════
    # JHARKHAND  (~6 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Ranchi",         "Jharkhand", 23.3441, 85.3096,
     dict(rainfall=(180,270), river_level=(4,7),  soil_moisture=(0.55,0.73),
          slope=(5,15),  elevation=(620,700),    flood_p=0.55, ls_p=0.28)),
    ("Jamshedpur",     "Jharkhand", 22.8046, 86.2029,
     dict(rainfall=(190,280), river_level=(5,8),  soil_moisture=(0.58,0.76),
          slope=(5,15),  elevation=(135,175),    flood_p=0.65, ls_p=0.25)),
    ("Dhanbad",        "Jharkhand", 23.7957, 86.4304,
     dict(rainfall=(175,260), river_level=(4,7),  soil_moisture=(0.55,0.73),
          slope=(5,15),  elevation=(220,280),    flood_p=0.60, ls_p=0.25)),
    ("Deoghar",        "Jharkhand", 24.4800, 86.6946,
     dict(rainfall=(165,245), river_level=(4,7),  soil_moisture=(0.52,0.70),
          slope=(5,15),  elevation=(240,300),    flood_p=0.55, ls_p=0.22)),
    ("Hazaribagh",     "Jharkhand", 23.9925, 85.3614,
     dict(rainfall=(175,260), river_level=(4,7),  soil_moisture=(0.54,0.72),
          slope=(8,20),  elevation=(600,680),    flood_p=0.52, ls_p=0.30)),
    ("Bokaro",         "Jharkhand", 23.6693, 86.1511,
     dict(rainfall=(175,260), river_level=(4,7),  soil_moisture=(0.55,0.73),
          slope=(5,15),  elevation=(210,265),    flood_p=0.58, ls_p=0.22)),

    # ══════════════════════════════════════════════════════════════════════════
    # ODISHA  (~8 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Bhubaneswar",    "Odisha", 20.2961, 85.8245,
     dict(rainfall=(210,320), river_level=(5,8),  soil_moisture=(0.62,0.80),
          slope=(0,5),   elevation=(42,65),      flood_p=0.68, ls_p=0.15)),
    ("Cuttack",        "Odisha", 20.4625, 85.8830,
     dict(rainfall=(220,330), river_level=(6,9),  soil_moisture=(0.65,0.83),
          slope=(0,4),   elevation=(22,45),      flood_p=0.80, ls_p=0.10)),
    ("Puri",           "Odisha", 19.8135, 85.8312,
     dict(rainfall=(220,340), river_level=(5,8),  soil_moisture=(0.65,0.83),
          slope=(0,3),   elevation=(5,20),       flood_p=0.78, ls_p=0.08)),
    ("Paradip",        "Odisha", 20.3165, 86.6096,
     dict(rainfall=(230,350), river_level=(6,8),  soil_moisture=(0.70,0.88),
          slope=(0,2),   elevation=(4,15),       flood_p=0.80, ls_p=0.08)),
    ("Balasore",       "Odisha", 21.4942, 86.9336,
     dict(rainfall=(230,350), river_level=(6,9),  soil_moisture=(0.68,0.86),
          slope=(0,3),   elevation=(20,40),      flood_p=0.82, ls_p=0.10)),
    ("Bhadrak",        "Odisha", 21.0575, 86.5153,
     dict(rainfall=(225,340), river_level=(6,9),  soil_moisture=(0.68,0.86),
          slope=(0,3),   elevation=(18,38),      flood_p=0.82, ls_p=0.10)),
    ("Gopalpur",       "Odisha", 19.2588, 84.8979,
     dict(rainfall=(200,310), river_level=(4,7),  soil_moisture=(0.60,0.78),
          slope=(0,4),   elevation=(8,22),       flood_p=0.70, ls_p=0.12)),
    ("Berhampur",      "Odisha", 19.3149, 84.7941,
     dict(rainfall=(200,310), river_level=(4,7),  soil_moisture=(0.60,0.78),
          slope=(2,8),   elevation=(30,60),      flood_p=0.68, ls_p=0.15)),

    # ══════════════════════════════════════════════════════════════════════════
    # ANDHRA PRADESH  (~10 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Visakhapatnam",  "Andhra Pradesh", 17.6868, 83.2185,
     dict(rainfall=(180,280), river_level=(4,7),  soil_moisture=(0.55,0.73),
          slope=(2,10),  elevation=(18,55),      flood_p=0.65, ls_p=0.22)),
    ("Vijayawada",     "Andhra Pradesh", 16.5062, 80.6480,
     dict(rainfall=(140,220), river_level=(6,9),  soil_moisture=(0.58,0.76),
          slope=(0,5),   elevation=(24,55),      flood_p=0.78, ls_p=0.10)),
    ("Kakinada",       "Andhra Pradesh", 16.9891, 82.2475,
     dict(rainfall=(180,280), river_level=(5,8),  soil_moisture=(0.62,0.80),
          slope=(0,4),   elevation=(6,22),       flood_p=0.78, ls_p=0.10)),
    ("Rajahmundry",    "Andhra Pradesh", 17.0005, 81.8040,
     dict(rainfall=(175,270), river_level=(6,9),  soil_moisture=(0.60,0.78),
          slope=(0,4),   elevation=(18,45),      flood_p=0.80, ls_p=0.10)),
    ("Machilipatnam",  "Andhra Pradesh", 16.1875, 81.1389,
     dict(rainfall=(170,260), river_level=(5,8),  soil_moisture=(0.60,0.78),
          slope=(0,3),   elevation=(4,18),       flood_p=0.78, ls_p=0.08)),
    ("Nellore",        "Andhra Pradesh", 14.4426, 79.9865,
     dict(rainfall=(140,220), river_level=(4,7),  soil_moisture=(0.52,0.70),
          slope=(0,5),   elevation=(15,40),      flood_p=0.65, ls_p=0.12)),
    ("Tirupati",       "Andhra Pradesh", 13.6288, 79.4192,
     dict(rainfall=(130,210), river_level=(3,6),  soil_moisture=(0.48,0.68),
          slope=(5,18),  elevation=(155,220),    flood_p=0.50, ls_p=0.30)),
    ("Srikakulam",     "Andhra Pradesh", 18.2949, 83.8938,
     dict(rainfall=(190,290), river_level=(5,8),  soil_moisture=(0.60,0.78),
          slope=(2,8),   elevation=(20,50),      flood_p=0.70, ls_p=0.18)),
    ("Kurnool",        "Andhra Pradesh", 15.8281, 78.0373,
     dict(rainfall=(110,180), river_level=(3,6),  soil_moisture=(0.42,0.62),
          slope=(2,8),   elevation=(270,320),    flood_p=0.42, ls_p=0.15)),
    ("Guntur",         "Andhra Pradesh", 16.3067, 80.4365,
     dict(rainfall=(130,210), river_level=(5,8),  soil_moisture=(0.55,0.73),
          slope=(0,4),   elevation=(25,55),      flood_p=0.68, ls_p=0.10)),

    # ══════════════════════════════════════════════════════════════════════════
    # TELANGANA  (~5 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Hyderabad",      "Telangana", 17.3850, 78.4867,
     dict(rainfall=(100,165), river_level=(3,6),  soil_moisture=(0.38,0.58),
          slope=(0,5),   elevation=(505,540),    flood_p=0.38, ls_p=0.08)),
    ("Warangal",       "Telangana", 17.9784, 79.5941,
     dict(rainfall=(110,180), river_level=(4,7),  soil_moisture=(0.42,0.62),
          slope=(0,5),   elevation=(270,310),    flood_p=0.45, ls_p=0.10)),
    ("Khammam",        "Telangana", 17.2473, 80.1514,
     dict(rainfall=(130,210), river_level=(4,7),  soil_moisture=(0.48,0.68),
          slope=(2,8),   elevation=(125,175),    flood_p=0.55, ls_p=0.12)),
    ("Nizamabad",      "Telangana", 18.6725, 78.0941,
     dict(rainfall=(105,175), river_level=(3,6),  soil_moisture=(0.40,0.60),
          slope=(0,5),   elevation=(380,420),    flood_p=0.40, ls_p=0.08)),
    ("Karimnagar",     "Telangana", 18.4386, 79.1288,
     dict(rainfall=(110,180), river_level=(3,6),  soil_moisture=(0.40,0.60),
          slope=(2,8),   elevation=(285,325),    flood_p=0.42, ls_p=0.10)),

    # ══════════════════════════════════════════════════════════════════════════
    # KARNATAKA  (~12 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Bengaluru",      "Karnataka", 12.9716, 77.5946,
     dict(rainfall=(95,155),  river_level=(2,5),  soil_moisture=(0.35,0.55),
          slope=(0,5),   elevation=(890,935),    flood_p=0.28, ls_p=0.08)),
    ("Mysuru",         "Karnataka", 12.2958, 76.6394,
     dict(rainfall=(100,165), river_level=(3,6),  soil_moisture=(0.40,0.60),
          slope=(2,8),   elevation=(760,820),    flood_p=0.32, ls_p=0.12)),
    ("Mangaluru",      "Karnataka", 12.9141, 74.8560,
     dict(rainfall=(320,520), river_level=(4,7),  soil_moisture=(0.78,0.94),
          slope=(5,18),  elevation=(20,65),      flood_p=0.68, ls_p=0.65)),
    ("Udupi",          "Karnataka", 13.3409, 74.7421,
     dict(rainfall=(320,520), river_level=(4,7),  soil_moisture=(0.78,0.94),
          slope=(8,22),  elevation=(25,80),      flood_p=0.65, ls_p=0.68)),
    ("Karwar",         "Karnataka", 14.8139, 74.1339,
     dict(rainfall=(300,480), river_level=(4,7),  soil_moisture=(0.75,0.92),
          slope=(8,22),  elevation=(18,60),      flood_p=0.65, ls_p=0.65)),
    ("Madikeri",       "Karnataka", 12.4244, 75.7382,
     dict(rainfall=(280,450), river_level=(3,6),  soil_moisture=(0.78,0.94),
          slope=(22,36), elevation=(1020,1150),  flood_p=0.38, ls_p=0.82)),
    ("Chikkamagaluru", "Karnataka", 13.3161, 75.7720,
     dict(rainfall=(250,400), river_level=(3,6),  soil_moisture=(0.72,0.90),
          slope=(18,32), elevation=(900,1020),   flood_p=0.38, ls_p=0.78)),
    ("Shivamogga",     "Karnataka", 13.9299, 75.5681,
     dict(rainfall=(220,360), river_level=(4,7),  soil_moisture=(0.68,0.86),
          slope=(10,24), elevation=(570,650),    flood_p=0.55, ls_p=0.62)),
    ("Belagavi",       "Karnataka", 15.8497, 74.4977,
     dict(rainfall=(130,210), river_level=(3,6),  soil_moisture=(0.48,0.68),
          slope=(2,10),  elevation=(750,820),    flood_p=0.40, ls_p=0.22)),
    ("Hubballi",       "Karnataka", 15.3647, 75.1240,
     dict(rainfall=(110,180), river_level=(2,5),  soil_moisture=(0.38,0.58),
          slope=(0,5),   elevation=(650,720),    flood_p=0.30, ls_p=0.10)),
    ("Davanagere",     "Karnataka", 14.4644, 75.9218,
     dict(rainfall=(120,195), river_level=(3,6),  soil_moisture=(0.42,0.62),
          slope=(0,5),   elevation=(565,620),    flood_p=0.35, ls_p=0.10)),
    ("Hassan",         "Karnataka", 13.0069, 76.0993,
     dict(rainfall=(140,230), river_level=(3,6),  soil_moisture=(0.50,0.70),
          slope=(5,15),  elevation=(920,1010),   flood_p=0.38, ls_p=0.32)),

    # ══════════════════════════════════════════════════════════════════════════
    # KERALA  (~12 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Thiruvananthapuram","Kerala", 8.5241, 76.9366,
     dict(rainfall=(210,340), river_level=(4,7),  soil_moisture=(0.65,0.83),
          slope=(2,10),  elevation=(12,45),      flood_p=0.60, ls_p=0.25)),
    ("Kollam",         "Kerala",  8.8932, 76.6141,
     dict(rainfall=(220,350), river_level=(4,7),  soil_moisture=(0.68,0.86),
          slope=(2,10),  elevation=(10,40),      flood_p=0.62, ls_p=0.28)),
    ("Alappuzha",      "Kerala",  9.4981, 76.3388,
     dict(rainfall=(280,440), river_level=(6,9),  soil_moisture=(0.78,0.95),
          slope=(0,3),   elevation=(1,10),       flood_p=0.88, ls_p=0.08)),
    ("Kochi",          "Kerala",  9.9312, 76.2673,
     dict(rainfall=(280,430), river_level=(5,8),  soil_moisture=(0.75,0.92),
          slope=(0,5),   elevation=(4,22),       flood_p=0.80, ls_p=0.12)),
    ("Thrissur",       "Kerala",  10.5276, 76.2144,
     dict(rainfall=(260,400), river_level=(4,7),  soil_moisture=(0.70,0.88),
          slope=(2,10),  elevation=(2,30),       flood_p=0.72, ls_p=0.22)),
    ("Kozhikode",      "Kerala",  11.2588, 75.7804,
     dict(rainfall=(300,480), river_level=(4,7),  soil_moisture=(0.75,0.92),
          slope=(5,15),  elevation=(10,45),      flood_p=0.68, ls_p=0.35)),
    ("Kannur",         "Kerala",  11.8745, 75.3704,
     dict(rainfall=(300,480), river_level=(4,7),  soil_moisture=(0.75,0.92),
          slope=(5,15),  elevation=(8,40),       flood_p=0.68, ls_p=0.35)),
    ("Wayanad",        "Kerala",  11.6854, 76.1320,
     dict(rainfall=(320,520), river_level=(4,7),  soil_moisture=(0.80,0.96),
          slope=(18,32), elevation=(700,900),    flood_p=0.48, ls_p=0.88)),
    ("Idukki",         "Kerala",  9.8616, 77.1021,
     dict(rainfall=(300,500), river_level=(3,6),  soil_moisture=(0.78,0.95),
          slope=(22,38), elevation=(780,980),    flood_p=0.38, ls_p=0.88)),
    ("Munnar",         "Kerala",  10.0893, 77.0595,
     dict(rainfall=(320,540), river_level=(3,6),  soil_moisture=(0.80,0.97),
          slope=(25,40), elevation=(1550,1700),  flood_p=0.30, ls_p=0.90)),
    ("Pathanamthitta", "Kerala",  9.2648, 76.7870,
     dict(rainfall=(280,450), river_level=(4,7),  soil_moisture=(0.75,0.92),
          slope=(8,22),  elevation=(35,100),     flood_p=0.62, ls_p=0.58)),
    ("Kottayam",       "Kerala",  9.5916, 76.5222,
     dict(rainfall=(270,430), river_level=(4,7),  soil_moisture=(0.73,0.91),
          slope=(3,12),  elevation=(4,30),       flood_p=0.70, ls_p=0.30)),

    # ══════════════════════════════════════════════════════════════════════════
    # TAMIL NADU  (~12 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Chennai",        "Tamil Nadu", 13.0827, 80.2707,
     dict(rainfall=(140,220), river_level=(3,6),  soil_moisture=(0.45,0.65),
          slope=(0,3),   elevation=(6,22),       flood_p=0.62, ls_p=0.08)),
    ("Coimbatore",     "Tamil Nadu", 11.0168, 76.9558,
     dict(rainfall=(80,140),  river_level=(2,5),  soil_moisture=(0.32,0.52),
          slope=(2,8),   elevation=(420,480),    flood_p=0.28, ls_p=0.15)),
    ("Madurai",        "Tamil Nadu", 9.9252, 78.1198,
     dict(rainfall=(75,135),  river_level=(2,5),  soil_moisture=(0.28,0.48),
          slope=(0,5),   elevation=(101,135),    flood_p=0.25, ls_p=0.08)),
    ("Cuddalore",      "Tamil Nadu", 11.7480, 79.7714,
     dict(rainfall=(160,250), river_level=(4,7),  soil_moisture=(0.52,0.72),
          slope=(0,3),   elevation=(5,20),       flood_p=0.68, ls_p=0.08)),
    ("Nagapattinam",   "Tamil Nadu", 10.7672, 79.8449,
     dict(rainfall=(175,280), river_level=(4,7),  soil_moisture=(0.58,0.76),
          slope=(0,3),   elevation=(3,15),       flood_p=0.72, ls_p=0.08)),
    ("Thoothukudi",    "Tamil Nadu", 8.7642, 78.1348,
     dict(rainfall=(80,140),  river_level=(2,4),  soil_moisture=(0.28,0.48),
          slope=(0,3),   elevation=(12,35),      flood_p=0.30, ls_p=0.08)),
    ("Rameswaram",     "Tamil Nadu", 9.2881, 79.3129,
     dict(rainfall=(70,130),  river_level=(2,4),  soil_moisture=(0.28,0.48),
          slope=(0,2),   elevation=(5,18),       flood_p=0.30, ls_p=0.05)),
    ("Kanyakumari",    "Tamil Nadu", 8.0883, 77.5385,
     dict(rainfall=(160,260), river_level=(3,6),  soil_moisture=(0.55,0.73),
          slope=(2,10),  elevation=(6,30),       flood_p=0.52, ls_p=0.18)),
    ("Salem",          "Tamil Nadu", 11.6643, 78.1460,
     dict(rainfall=(90,150),  river_level=(2,5),  soil_moisture=(0.32,0.52),
          slope=(2,8),   elevation=(280,340),    flood_p=0.28, ls_p=0.15)),
    ("Vellore",        "Tamil Nadu", 12.9165, 79.1325,
     dict(rainfall=(110,180), river_level=(2,5),  soil_moisture=(0.38,0.58),
          slope=(2,8),   elevation=(200,250),    flood_p=0.32, ls_p=0.15)),
    ("Tirunelveli",    "Tamil Nadu", 8.7139, 77.7567,
     dict(rainfall=(80,150),  river_level=(2,5),  soil_moisture=(0.28,0.48),
          slope=(2,8),   elevation=(40,80),      flood_p=0.28, ls_p=0.12)),
    ("Ooty",           "Tamil Nadu", 11.4102, 76.6950,
     dict(rainfall=(180,290), river_level=(2,5),  soil_moisture=(0.62,0.80),
          slope=(22,36), elevation=(2200,2350),  flood_p=0.25, ls_p=0.78)),

    # ══════════════════════════════════════════════════════════════════════════
    # GOA  (~2 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Panaji",         "Goa", 15.4909, 73.8278,
     dict(rainfall=(280,450), river_level=(4,7),  soil_moisture=(0.72,0.90),
          slope=(2,10),  elevation=(10,45),      flood_p=0.62, ls_p=0.30)),
    ("Margao",         "Goa", 15.2832, 73.9862,
     dict(rainfall=(280,450), river_level=(4,7),  soil_moisture=(0.72,0.90),
          slope=(2,10),  elevation=(8,38),       flood_p=0.60, ls_p=0.28)),

    # ══════════════════════════════════════════════════════════════════════════
    # MAHARASHTRA  (~15 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Mumbai",         "Maharashtra", 19.0760, 72.8777,
     dict(rainfall=(280,430), river_level=(4,7),  soil_moisture=(0.72,0.90),
          slope=(0,5),   elevation=(10,30),      flood_p=0.78, ls_p=0.15)),
    ("Thane",          "Maharashtra", 19.2183, 72.9781,
     dict(rainfall=(280,430), river_level=(4,7),  soil_moisture=(0.72,0.90),
          slope=(2,10),  elevation=(8,40),       flood_p=0.75, ls_p=0.18)),
    ("Pune",           "Maharashtra", 18.5204, 73.8567,
     dict(rainfall=(140,220), river_level=(3,6),  soil_moisture=(0.48,0.68),
          slope=(3,12),  elevation=(555,620),    flood_p=0.42, ls_p=0.22)),
    ("Nagpur",         "Maharashtra", 21.1458, 79.0882,
     dict(rainfall=(130,210), river_level=(3,6),  soil_moisture=(0.45,0.65),
          slope=(0,5),   elevation=(315,350),    flood_p=0.42, ls_p=0.10)),
    ("Nashik",         "Maharashtra", 19.9975, 73.7898,
     dict(rainfall=(150,240), river_level=(4,7),  soil_moisture=(0.50,0.70),
          slope=(5,15),  elevation=(565,640),    flood_p=0.50, ls_p=0.25)),
    ("Kolhapur",       "Maharashtra", 16.7050, 74.2433,
     dict(rainfall=(180,290), river_level=(5,8),  soil_moisture=(0.60,0.78),
          slope=(3,12),  elevation=(555,630),    flood_p=0.60, ls_p=0.28)),
    ("Ratnagiri",      "Maharashtra", 16.9944, 73.3003,
     dict(rainfall=(300,500), river_level=(4,7),  soil_moisture=(0.78,0.95),
          slope=(10,24), elevation=(12,60),      flood_p=0.65, ls_p=0.72)),
    ("Sindhudurg",     "Maharashtra", 16.3479, 73.5692,
     dict(rainfall=(300,490), river_level=(4,7),  soil_moisture=(0.78,0.95),
          slope=(10,24), elevation=(10,55),      flood_p=0.65, ls_p=0.70)),
    ("Chiplun",        "Maharashtra", 17.5333, 73.5167,
     dict(rainfall=(300,500), river_level=(5,8),  soil_moisture=(0.78,0.95),
          slope=(12,26), elevation=(20,80),      flood_p=0.68, ls_p=0.72)),
    ("Satara",         "Maharashtra", 17.6805, 74.0183,
     dict(rainfall=(170,270), river_level=(4,7),  soil_moisture=(0.55,0.73),
          slope=(5,18),  elevation=(680,780),    flood_p=0.52, ls_p=0.38)),
    ("Sangli",         "Maharashtra", 16.8524, 74.5815,
     dict(rainfall=(110,180), river_level=(4,7),  soil_moisture=(0.42,0.62),
          slope=(0,5),   elevation=(545,610),    flood_p=0.50, ls_p=0.10)),
    ("Aurangabad",     "Maharashtra", 19.8762, 75.3433,
     dict(rainfall=(100,165), river_level=(2,5),  soil_moisture=(0.35,0.55),
          slope=(0,5),   elevation=(560,620),    flood_p=0.32, ls_p=0.08)),
    ("Amravati",       "Maharashtra", 20.9320, 77.7523,
     dict(rainfall=(115,190), river_level=(3,6),  soil_moisture=(0.40,0.60),
          slope=(0,5),   elevation=(340,390),    flood_p=0.38, ls_p=0.08)),
    ("Navi Mumbai",    "Maharashtra", 19.0330, 73.0297,
     dict(rainfall=(280,430), river_level=(4,7),  soil_moisture=(0.72,0.90),
          slope=(0,8),   elevation=(5,35),       flood_p=0.72, ls_p=0.20)),
    ("Lonavala",       "Maharashtra", 18.7481, 73.4072,
     dict(rainfall=(280,460), river_level=(3,6),  soil_moisture=(0.72,0.90),
          slope=(20,34), elevation=(620,720),    flood_p=0.38, ls_p=0.70)),

    # ══════════════════════════════════════════════════════════════════════════
    # GUJARAT  (~12 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Ahmedabad",      "Gujarat", 23.0225, 72.5714,
     dict(rainfall=(70,130),  river_level=(2,5),  soil_moisture=(0.25,0.45),
          slope=(0,3),   elevation=(50,75),      flood_p=0.28, ls_p=0.05)),
    ("Surat",          "Gujarat", 21.1702, 72.8311,
     dict(rainfall=(130,210), river_level=(4,7),  soil_moisture=(0.48,0.68),
          slope=(0,3),   elevation=(10,30),      flood_p=0.62, ls_p=0.08)),
    ("Vadodara",       "Gujarat", 22.3072, 73.1812,
     dict(rainfall=(90,160),  river_level=(3,6),  soil_moisture=(0.35,0.55),
          slope=(0,3),   elevation=(35,60),      flood_p=0.45, ls_p=0.05)),
    ("Rajkot",         "Gujarat", 22.3039, 70.8022,
     dict(rainfall=(60,110),  river_level=(1,4),  soil_moisture=(0.20,0.40),
          slope=(0,3),   elevation=(120,155),    flood_p=0.20, ls_p=0.05)),
    ("Bhuj",           "Gujarat", 23.2419, 69.6669,
     dict(rainfall=(30,75),   river_level=(0,3),  soil_moisture=(0.10,0.28),
          slope=(0,5),   elevation=(80,120),     flood_p=0.15, ls_p=0.05)),
    ("Jamnagar",       "Gujarat", 22.4707, 70.0577,
     dict(rainfall=(50,100),  river_level=(1,4),  soil_moisture=(0.15,0.35),
          slope=(0,3),   elevation=(20,55),      flood_p=0.18, ls_p=0.05)),
    ("Porbandar",      "Gujarat", 21.6417, 69.6293,
     dict(rainfall=(40,90),   river_level=(1,4),  soil_moisture=(0.15,0.32),
          slope=(0,3),   elevation=(4,28),       flood_p=0.18, ls_p=0.05)),
    ("Veraval",        "Gujarat", 20.9143, 70.3623,
     dict(rainfall=(50,100),  river_level=(2,4),  soil_moisture=(0.18,0.38),
          slope=(0,3),   elevation=(6,25),       flood_p=0.22, ls_p=0.05)),
    ("Bhavnagar",      "Gujarat", 21.7645, 72.1519,
     dict(rainfall=(60,120),  river_level=(2,4),  soil_moisture=(0.20,0.40),
          slope=(0,3),   elevation=(10,40),      flood_p=0.25, ls_p=0.05)),
    ("Bharuch",        "Gujarat", 21.7051, 72.9959,
     dict(rainfall=(90,165),  river_level=(4,7),  soil_moisture=(0.40,0.60),
          slope=(0,3),   elevation=(12,38),      flood_p=0.55, ls_p=0.05)),
    ("Valsad",         "Gujarat", 20.5992, 72.9342,
     dict(rainfall=(150,250), river_level=(4,7),  soil_moisture=(0.55,0.73),
          slope=(2,8),   elevation=(8,30),       flood_p=0.65, ls_p=0.15)),
    ("Gandhinagar",    "Gujarat", 23.2156, 72.6369,
     dict(rainfall=(70,130),  river_level=(2,5),  soil_moisture=(0.25,0.45),
          slope=(0,2),   elevation=(80,110),     flood_p=0.28, ls_p=0.05)),

    # ══════════════════════════════════════════════════════════════════════════
    # RAJASTHAN  (~10 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Jaipur",         "Rajasthan", 26.9124, 75.7873,
     dict(rainfall=(50,100),  river_level=(1,4),  soil_moisture=(0.15,0.35),
          slope=(0,4),   elevation=(420,460),    flood_p=0.15, ls_p=0.08)),
    ("Jodhpur",        "Rajasthan", 26.2389, 73.0243,
     dict(rainfall=(20,60),   river_level=(0,2),  soil_moisture=(0.05,0.20),
          slope=(0,3),   elevation=(230,270),    flood_p=0.08, ls_p=0.05)),
    ("Bikaner",        "Rajasthan", 28.0229, 73.3119,
     dict(rainfall=(15,50),   river_level=(0,1),  soil_moisture=(0.05,0.15),
          slope=(0,2),   elevation=(240,275),    flood_p=0.06, ls_p=0.04)),
    ("Jaisalmer",      "Rajasthan", 26.9157, 70.9083,
     dict(rainfall=(8,30),    river_level=(0,1),  soil_moisture=(0.03,0.10),
          slope=(0,2),   elevation=(220,260),    flood_p=0.04, ls_p=0.03)),
    ("Udaipur",        "Rajasthan", 24.5854, 73.7125,
     dict(rainfall=(70,130),  river_level=(2,5),  soil_moisture=(0.25,0.45),
          slope=(5,15),  elevation=(580,640),    flood_p=0.25, ls_p=0.18)),
    ("Kota",           "Rajasthan", 25.2138, 75.8648,
     dict(rainfall=(60,120),  river_level=(2,5),  soil_moisture=(0.22,0.42),
          slope=(0,5),   elevation=(260,300),    flood_p=0.28, ls_p=0.08)),
    ("Ajmer",          "Rajasthan", 26.4499, 74.6399,
     dict(rainfall=(40,90),   river_level=(1,3),  soil_moisture=(0.12,0.30),
          slope=(2,8),   elevation=(445,510),    flood_p=0.12, ls_p=0.10)),
    ("Barmer",         "Rajasthan", 25.7452, 71.3942,
     dict(rainfall=(10,35),   river_level=(0,1),  soil_moisture=(0.04,0.12),
          slope=(0,2),   elevation=(225,265),    flood_p=0.05, ls_p=0.03)),
    ("Alwar",          "Rajasthan", 27.5530, 76.6346,
     dict(rainfall=(50,100),  river_level=(1,4),  soil_moisture=(0.18,0.38),
          slope=(2,8),   elevation=(270,330),    flood_p=0.18, ls_p=0.12)),
    ("Mount Abu",      "Rajasthan", 24.5926, 72.7156,
     dict(rainfall=(100,180), river_level=(2,5),  soil_moisture=(0.40,0.62),
          slope=(18,30), elevation=(1220,1350),  flood_p=0.28, ls_p=0.55)),

    # ══════════════════════════════════════════════════════════════════════════
    # MADHYA PRADESH  (~8 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Bhopal",         "Madhya Pradesh", 23.2599, 77.4126,
     dict(rainfall=(110,180), river_level=(3,6),  soil_moisture=(0.40,0.60),
          slope=(0,5),   elevation=(520,580),    flood_p=0.35, ls_p=0.08)),
    ("Indore",         "Madhya Pradesh", 22.7196, 75.8577,
     dict(rainfall=(95,160),  river_level=(2,5),  soil_moisture=(0.35,0.55),
          slope=(2,8),   elevation=(548,620),    flood_p=0.28, ls_p=0.10)),
    ("Jabalpur",       "Madhya Pradesh", 23.1815, 79.9864,
     dict(rainfall=(130,210), river_level=(4,7),  soil_moisture=(0.45,0.65),
          slope=(2,8),   elevation=(415,480),    flood_p=0.48, ls_p=0.12)),
    ("Gwalior",        "Madhya Pradesh", 26.2183, 78.1828,
     dict(rainfall=(80,145),  river_level=(2,5),  soil_moisture=(0.28,0.48),
          slope=(0,5),   elevation=(200,250),    flood_p=0.25, ls_p=0.08)),
    ("Ujjain",         "Madhya Pradesh", 23.1765, 75.7885,
     dict(rainfall=(95,160),  river_level=(2,5),  soil_moisture=(0.35,0.55),
          slope=(0,4),   elevation=(490,545),    flood_p=0.28, ls_p=0.08)),
    ("Rewa",           "Madhya Pradesh", 24.5362, 81.2962,
     dict(rainfall=(120,195), river_level=(3,6),  soil_moisture=(0.42,0.62),
          slope=(3,10),  elevation=(340,410),    flood_p=0.40, ls_p=0.12)),
    ("Satna",          "Madhya Pradesh", 24.5697, 80.8317,
     dict(rainfall=(115,190), river_level=(3,6),  soil_moisture=(0.40,0.60),
          slope=(2,8),   elevation=(305,380),    flood_p=0.38, ls_p=0.10)),
    ("Sagar",          "Madhya Pradesh", 23.8388, 78.7378,
     dict(rainfall=(115,190), river_level=(3,6),  soil_moisture=(0.40,0.60),
          slope=(2,8),   elevation=(520,590),    flood_p=0.35, ls_p=0.10)),

    # ══════════════════════════════════════════════════════════════════════════
    # CHHATTISGARH  (~6 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Raipur",         "Chhattisgarh", 21.2514, 81.6296,
     dict(rainfall=(150,240), river_level=(4,7),  soil_moisture=(0.52,0.72),
          slope=(0,5),   elevation=(285,330),    flood_p=0.50, ls_p=0.10)),
    ("Bilaspur",       "Chhattisgarh", 22.0796, 82.1409,
     dict(rainfall=(155,245), river_level=(4,7),  soil_moisture=(0.52,0.72),
          slope=(0,5),   elevation=(265,310),    flood_p=0.52, ls_p=0.10)),
    ("Jagdalpur",      "Chhattisgarh", 19.0742, 82.0174,
     dict(rainfall=(180,280), river_level=(4,7),  soil_moisture=(0.58,0.76),
          slope=(3,10),  elevation=(550,620),    flood_p=0.55, ls_p=0.18)),
    ("Ambikapur",      "Chhattisgarh", 23.1188, 83.1958,
     dict(rainfall=(150,240), river_level=(3,6),  soil_moisture=(0.50,0.70),
          slope=(3,10),  elevation=(590,660),    flood_p=0.45, ls_p=0.15)),
    ("Korba",          "Chhattisgarh", 22.3455, 82.7062,
     dict(rainfall=(155,245), river_level=(4,7),  soil_moisture=(0.52,0.72),
          slope=(2,8),   elevation=(265,320),    flood_p=0.50, ls_p=0.12)),
    ("Durg",           "Chhattisgarh", 21.1904, 81.2849,
     dict(rainfall=(145,230), river_level=(3,6),  soil_moisture=(0.50,0.70),
          slope=(0,4),   elevation=(290,330),    flood_p=0.45, ls_p=0.08)),

    # ══════════════════════════════════════════════════════════════════════════
    # DELHI  (1 location)
    # ══════════════════════════════════════════════════════════════════════════
    ("Delhi",          "Delhi", 28.6139, 77.2090,
     dict(rainfall=(120,180), river_level=(4,7),  soil_moisture=(0.45,0.65),
          slope=(0,3),   elevation=(200,230),    flood_p=0.55, ls_p=0.05)),

    # ══════════════════════════════════════════════════════════════════════════
    # HARYANA  (~4 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Gurugram",       "Haryana", 28.4595, 77.0266,
     dict(rainfall=(100,160), river_level=(3,6),  soil_moisture=(0.40,0.60),
          slope=(0,3),   elevation=(210,240),    flood_p=0.45, ls_p=0.05)),
    ("Faridabad",      "Haryana", 28.4089, 77.3178,
     dict(rainfall=(100,150), river_level=(3,6),  soil_moisture=(0.40,0.60),
          slope=(0,2),   elevation=(195,220),    flood_p=0.40, ls_p=0.05)),
    ("Ambala",         "Haryana", 30.3782, 76.7767,
     dict(rainfall=(120,200), river_level=(4,7),  soil_moisture=(0.45,0.65),
          slope=(0,3),   elevation=(270,305),    flood_p=0.50, ls_p=0.08)),
    ("Hisar",          "Haryana", 29.1509, 75.7221,
     dict(rainfall=(50,100),  river_level=(1,4),  soil_moisture=(0.18,0.38),
          slope=(0,2),   elevation=(210,245),    flood_p=0.18, ls_p=0.05)),

    # ══════════════════════════════════════════════════════════════════════════
    # PUNJAB  (~5 locations)
    # ══════════════════════════════════════════════════════════════════════════
    ("Amritsar",       "Punjab", 31.6340, 74.8723,
     dict(rainfall=(90,160),  river_level=(3,6),  soil_moisture=(0.40,0.60),
          slope=(0,3),   elevation=(232,265),    flood_p=0.42, ls_p=0.05)),
    ("Ludhiana",       "Punjab", 30.9010, 75.8573,
     dict(rainfall=(90,160),  river_level=(3,6),  soil_moisture=(0.40,0.60),
          slope=(0,2),   elevation=(250,280),    flood_p=0.40, ls_p=0.05)),
    ("Jalandhar",      "Punjab", 31.3260, 75.5762,
     dict(rainfall=(90,155),  river_level=(3,6),  soil_moisture=(0.40,0.60),
          slope=(0,2),   elevation=(228,258),    flood_p=0.40, ls_p=0.05)),
    ("Patiala",        "Punjab", 30.3398, 76.3869,
     dict(rainfall=(100,165), river_level=(3,6),  soil_moisture=(0.42,0.62),
          slope=(0,2),   elevation=(248,278),    flood_p=0.42, ls_p=0.05)),
    ("Bathinda",       "Punjab", 30.2070, 74.9455,
     dict(rainfall=(60,120),  river_level=(1,4),  soil_moisture=(0.22,0.42),
          slope=(0,2),   elevation=(200,235),    flood_p=0.20, ls_p=0.05)),

    # ══════════════════════════════════════════════════════════════════════════
    # CHANDIGARH
    # ══════════════════════════════════════════════════════════════════════════
    ("Chandigarh",     "Chandigarh", 30.7333, 76.7794,
     dict(rainfall=(110,180), river_level=(3,6),  soil_moisture=(0.42,0.62),
          slope=(0,3),   elevation=(310,345),    flood_p=0.42, ls_p=0.08)),

    # ══════════════════════════════════════════════════════════════════════════
    # ANDAMAN & NICOBAR  (1)
    # ══════════════════════════════════════════════════════════════════════════
    ("Port Blair",     "Andaman & Nicobar", 11.6234, 92.7265,
     dict(rainfall=(300,500), river_level=(3,6),  soil_moisture=(0.78,0.95),
          slope=(5,18),  elevation=(18,75),      flood_p=0.58, ls_p=0.48)),

    # ══════════════════════════════════════════════════════════════════════════
    # PUDUCHERRY  (1)
    # ══════════════════════════════════════════════════════════════════════════
    ("Puducherry",     "Puducherry", 11.9416, 79.8083,
     dict(rainfall=(120,200), river_level=(3,6),  soil_moisture=(0.45,0.65),
          slope=(0,3),   elevation=(5,20),       flood_p=0.52, ls_p=0.08)),
]


# ─────────────────────────────────────────────────────────────────────────────
# Helper: assign risk label
# ─────────────────────────────────────────────────────────────────────────────
def assign_risk(probability: float) -> str:
    """Convert a 0–1 probability into Low / Medium / High risk label."""
    if probability >= 0.65:
        return "High"
    elif probability >= 0.35:
        return "Medium"
    else:
        return "Low"


# ─────────────────────────────────────────────────────────────────────────────
# Build dataset row by row
# ─────────────────────────────────────────────────────────────────────────────
def build_dataset(locations: list) -> pd.DataFrame:
    rows = []
    for entry in locations:
        district, state, lat, lon, p = entry

        rainfall      = round(float(np.random.uniform(*p["rainfall"])), 1)
        river_level   = round(float(np.random.uniform(*p["river_level"])), 2)
        soil_moisture = round(float(np.random.uniform(*p["soil_moisture"])), 3)
        slope         = round(float(np.random.uniform(*p["slope"])), 1)
        elevation     = round(float(np.random.uniform(*p["elevation"])), 1)

        # Binary history flags driven by geographic probability
        flood_history     = int(np.random.random() < p["flood_p"])
        landslide_history = int(np.random.random() < p["ls_p"])

        # Flood synthetic risk probability
        flood_prob_raw = (
            0.30 * min(rainfall / 400.0, 1.0)
            + 0.20 * (river_level / 10.0)
            + 0.15 * soil_moisture
            + 0.10 * max(0.0, (1.0 - elevation / 3000.0))
            + 0.25 * flood_history
            + np.random.normal(0, 0.04)
        )
        flood_prob_raw = float(np.clip(flood_prob_raw, 0.0, 1.0))

        # Landslide synthetic risk probability
        ls_prob_raw = (
            0.20 * min(rainfall / 400.0, 1.0)
            + 0.20 * soil_moisture
            + 0.25 * min(slope / 45.0, 1.0)
            + 0.10 * max(0.0, (elevation / 3000.0))
            + 0.25 * landslide_history
            + np.random.normal(0, 0.04)
        )
        ls_prob_raw = float(np.clip(ls_prob_raw, 0.0, 1.0))

        flood_risk     = assign_risk(flood_prob_raw)
        landslide_risk = assign_risk(ls_prob_raw)

        rows.append({
            "district":           district,
            "state":              state,
            "latitude":           lat,
            "longitude":          lon,
            "rainfall":           rainfall,
            "river_level":        river_level,
            "soil_moisture":      soil_moisture,
            "slope":              slope,
            "elevation":          elevation,
            "flood_history":      flood_history,
            "landslide_history":  landslide_history,
            "flood_risk":         flood_risk,
            "landslide_risk":     landslide_risk,
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("ResQ Shield — Phase 9: Generating Expanded Master Dataset")
    print("=" * 65)
    print()
    print("[!] DISCLAIMER: ALL feature values are SYNTHETIC / DEMO DATA.")
    print("    Not real-time measurements or official observations.")
    print()

    df = build_dataset(LOCATIONS)

    # Duplicate check
    dups = df[df.duplicated(subset=["district", "state"], keep=False)]
    if len(dups) > 0:
        print(f"[WARN] {len(dups)} duplicate district/state pairs found:")
        print(dups[["district", "state"]].to_string())
    df = df.drop_duplicates(subset=["district", "state"]).reset_index(drop=True)

    # Coordinate validation
    invalid_lat = df[(df["latitude"] < 5) | (df["latitude"] > 40)]
    invalid_lon = df[(df["longitude"] < 65) | (df["longitude"] > 100)]
    if len(invalid_lat) > 0:
        print(f"[WARN] {len(invalid_lat)} rows with suspicious latitude")
    if len(invalid_lon) > 0:
        print(f"[WARN] {len(invalid_lon)} rows with suspicious longitude")

    # Save
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    # ── Detailed summary ──────────────────────────────────────────────────────
    print(f"[OK] Dataset saved: {OUTPUT_PATH}")
    print(f"     Rows    : {len(df)}")
    print(f"     Columns : {list(df.columns)}")
    print()

    print("── State coverage ──────────────────────────────────────────")
    sc = df.groupby("state").size().sort_values(ascending=False)
    for state, cnt in sc.items():
        print(f"  {cnt:3d}  {state}")
    print(f"  ---")
    print(f"  {len(sc)} unique states/UTs")
    print()

    print("── Risk Distribution ───────────────────────────────────────")
    print("Flood Risk:")
    print(df["flood_risk"].value_counts().to_string())
    print()
    print("Landslide Risk:")
    print(df["landslide_risk"].value_counts().to_string())
    print()

    print("── Coordinate ranges ───────────────────────────────────────")
    print(f"  Latitude  : {df['latitude'].min():.2f} to {df['latitude'].max():.2f}")
    print(f"  Longitude : {df['longitude'].min():.2f} to {df['longitude'].max():.2f}")
    print()

    print("── Feature ranges ──────────────────────────────────────────")
    for col in ["rainfall","river_level","soil_moisture","slope","elevation"]:
        print(f"  {col:20s}: {df[col].min():.2f} – {df[col].max():.2f}")
    print()

    print("── 5 Sample Rows ───────────────────────────────────────────")
    cols = ["district","state","rainfall","elevation","flood_risk","landslide_risk"]
    print(df[cols].head(5).to_string(index=False))
    print()
    print("Done.")


if __name__ == "__main__":
    main()
