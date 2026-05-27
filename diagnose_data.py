import glob
import os
from qc_datapoint import QCDataPointAnalyzer

path = 'export_traffic_data_1777054660685'
print('path exists', os.path.isdir(path))
print('csv_count', len(glob.glob(os.path.join(path, '*.csv'))))
ids = set()
for filepath in glob.glob(os.path.join(path, '*.csv')):
    name = os.path.basename(filepath)
    if name.startswith('Intersection_'):
        parts = name[len('Intersection_'):].split('_')
        ids.add(parts[0])
print('station_ids discovered from filenames', len(ids))
print('station_ids sample', sorted(list(ids))[:30])

analyzer = QCDataPointAnalyzer()
df = analyzer.load_intersection_directory(path)
print('loaded rows', len(df))
print('station_count', df['station_id'].nunique())
print('station_ids sample', sorted(df['station_id'].unique())[:40])
print('qc_status values', df['qc_status'].value_counts().to_dict())
print('record count by station top 20')
print(df.groupby('station_id').size().sort_values(ascending=False).head(20).to_string())
print('date_range', df['date'].min(), df['date'].max())
print('top roadways', df['roadway'].value_counts().head(20).to_dict())
