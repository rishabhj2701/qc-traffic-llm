import os
import pandas as pd
from datetime import datetime
import glob

def parse_intersection_file(filepath):
    data = []
    with open(filepath, 'r') as f:
        lines = f.readlines()
        
    metadata = {}
    time_series_started = False
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line: continue
        parts = [p.strip('"') for p in line.split(',')]
        
        if parts[0] == "Station ID:": metadata['station_id'] = parts[1]
        elif parts[0] == "Station Name:": metadata['roadway'] = parts[1]
        elif parts[0] == "Date:": metadata['date'] = parts[1]
        
        if parts[0] == "ALL-VEHICLE VOLUMES":
            time_series_started = True
            continue
            
        if time_series_started:
            if parts[0] == "Time Period":
                header = parts
                total_idx = header.index("Total") if "Total" in header else -1
                continue
            if total_idx != -1 and parts[0] and parts[0] != '""':
                try:
                    time_period = parts[0]
                    total_vol = int(parts[total_idx]) if parts[total_idx] else 0
                    
                    date_str = f"{metadata.get('date', '')} {time_period}"
                    dt = pd.to_datetime(date_str, format="%b %d %Y %I:%M %p", errors='coerce')
                    
                    data.append({
                        'station_id': metadata.get('station_id', 'UNKNOWN'),
                        'date': dt,
                        'volume': total_vol,
                        'roadway': metadata.get('roadway', ''),
                        'qc_status': 'OK'
                    })
                except Exception as e:
                    pass
    return data

def parse_all(directory):
    all_data = []
    for f in glob.glob(os.path.join(directory, "*.csv")):
        all_data.extend(parse_intersection_file(f))
    return pd.DataFrame(all_data)

df = parse_all("/Users/rj/ISU/Spring2026/AI4CCEE/export_traffic_data_1775688038943")
print(df.head())
print("Total rows:", len(df))
