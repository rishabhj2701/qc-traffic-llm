import os
import pandas as pd
import glob

def debug_parse(dir_path):
    data_map = {}
    for filepath in glob.glob(os.path.join(dir_path, "*.csv")):
        print(f"File: {os.path.basename(filepath)}")
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        metadata = {}
        active_table = False
        table_type = None
        total_idx = -1
        for line in lines:
            line = line.strip()
            if not line: continue
            parts = [p.strip('"') for p in line.split(',')]
            if parts[0] == "Station ID:": metadata['station_id'] = parts[1]
            elif parts[0] == "Date:": metadata['date'] = parts[1]
            if any(v in parts[0] for v in ["ALL-VEHICLE VOLUMES", "HEAVY-VEHICLE VOLUMES", "PEDESTRIAN VOLUMES", "BICYCLE VOLUMES"]):
                active_table = True
                table_type = parts[0]
                total_idx = -1
                continue
            if active_table:
                if parts[0] == "Time Period":
                    total_idx = parts.index("Total") if "Total" in parts else -1
                    continue
                if parts[0] == "" or parts[0] == " ": continue
                if parts[0].isupper() and "VOLUMES" not in parts[0]:
                    active_table = False
                    continue
                if total_idx != -1:
                    date_str = f"{metadata.get('date', '')} {parts[0]}"
                    dt = pd.to_datetime(date_str, format="%b %d %Y %I:%M %p", errors='coerce')
                    if pd.notna(dt):
                        key = (metadata.get('station_id', 'UNK'), dt)
                        if key not in data_map:
                            data_map[key] = {'total':0, 'bike':0}
                        val = int(parts[total_idx]) if parts[total_idx] and parts[total_idx].isdigit() else 0
                        if "BICYCLE" in table_type: data_map[key]['bike'] = val
                        else: data_map[key]['total'] = val
    print(f"Total keys: {len(data_map)}")
    return data_map

debug_parse("/Users/rj/ISU/Spring2026/AI4CCEE/export_traffic_data_1777054660685")
