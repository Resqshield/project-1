import os
import glob
import xml.etree.ElementTree as ET
import pandas as pd
from pathlib import Path
import json

EXTRACTED_DIR = Path("data_real/admin/raw/lgd_extracted")
OUT_DIR = Path("data_real/admin/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)
NS = {'ss': 'urn:schemas-microsoft-com:office:spreadsheet'}

def parse_xml_table(filepath):
    tree = ET.parse(filepath)
    root = tree.getroot()
    rows = root.findall('.//ss:Row', namespaces=NS)
    data = []
    
    for row in rows:
        cells = row.findall('ss:Cell', namespaces=NS)
        row_data = []
        for cell in cells:
            data_tag = cell.find('ss:Data', namespaces=NS)
            if data_tag is not None and data_tag.text is not None:
                row_data.append(data_tag.text.strip())
            else:
                row_data.append("")
        data.append(row_data)
        
    return data

def main():
    print("Parsing LGD XML files...")
    
    # 1. State
    states = pd.DataFrame([{"StateLGDCode": 5, "StateName": "Uttarakhand"}])
    
    # 2. Districts
    dist_file = glob.glob(str(EXTRACTED_DIR / "districtofSpecificState*.xls"))[0]
    dist_data = parse_xml_table(dist_file)
    dist_header = [c for c in dist_data[3]]
    dist_rows = dist_data[5:]
    dist_df = pd.DataFrame([r for r in dist_rows if len(r) == len(dist_header)], columns=dist_header)
    districts = pd.DataFrame({
        "StateLGDCode": 5,
        "DistrictLGDCode": pd.to_numeric(dist_df.iloc[:, 1], errors="coerce"),
        "DistrictName": dist_df.iloc[:, 3]
    }).dropna(subset=["DistrictLGDCode"])
    districts["DistrictLGDCode"] = districts["DistrictLGDCode"].astype(int)
    
    # 3. Subdistricts
    subd_file = glob.glob(str(EXTRACTED_DIR / "subDistrictofSpecificState*.xls"))[0]
    subd_data = parse_xml_table(subd_file)
    subd_header = [c for c in subd_data[3]]
    subd_rows = subd_data[5:]
    subd_df = pd.DataFrame([r for r in subd_rows if len(r) == len(subd_header)], columns=subd_header)
    subdistricts = pd.DataFrame({
        "DistrictLGDCode": pd.to_numeric(subd_df.iloc[:, 1], errors="coerce"),
        "SubdistrictLGDCode": pd.to_numeric(subd_df.iloc[:, 3], errors="coerce"),
        "SubdistrictName": subd_df.iloc[:, 5]
    }).dropna(subset=["SubdistrictLGDCode"])
    subdistricts["DistrictLGDCode"] = subdistricts["DistrictLGDCode"].astype(int)
    subdistricts["SubdistrictLGDCode"] = subdistricts["SubdistrictLGDCode"].astype(int)

    # 4. Villages
    vill_file = glob.glob(str(EXTRACTED_DIR / "villageofSpecificState*.xls"))[0]
    vill_data = parse_xml_table(vill_file)
    vill_header = [c for c in vill_data[3]]
    vill_rows = vill_data[5:]
    vill_df = pd.DataFrame([r for r in vill_rows if len(r) == len(vill_header)], columns=vill_header)
    villages = pd.DataFrame({
        "SubdistrictLGDCode": pd.to_numeric(vill_df.iloc[:, 3], errors="coerce"),
        "VillageLGDCode": pd.to_numeric(vill_df.iloc[:, 5], errors="coerce"),
        "VillageName": vill_df.iloc[:, 7],
        "Status": vill_df.iloc[:, 9]
    }).dropna(subset=["VillageLGDCode"])
    villages["SubdistrictLGDCode"] = villages["SubdistrictLGDCode"].astype(int)
    villages["VillageLGDCode"] = villages["VillageLGDCode"].astype(int)

    # Save to CSV
    states.to_csv(OUT_DIR / "states.csv", index=False)
    districts.to_csv(OUT_DIR / "districts.csv", index=False)
    subdistricts.to_csv(OUT_DIR / "subdistricts.csv", index=False)
    villages.to_csv(OUT_DIR / "villages.csv", index=False)
    
    print(f"Saved {len(states)} states, {len(districts)} districts, {len(subdistricts)} subdistricts, {len(villages)} villages.")

    # Write status JSON
    status = {
        "status": "PARTIAL",
        "state_count": len(states),
        "district_count": len(districts),
        "subdistrict_count": len(subdistricts),
        "village_count": len(villages),
        "note": "Uttarakhand LGD hierarchy parsed successfully from tabular XML. No geometries available."
    }
    with open(OUT_DIR / "lgd_status.json", "w") as f:
        json.dump(status, f, indent=2)
    print("Done.")

if __name__ == "__main__":
    main()
