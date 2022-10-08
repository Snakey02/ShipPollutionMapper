import numpy as np # linear algebra
import pandas as pd # data processing, CSV file I/O (e.g. pd.read_csv)
import folium
from folium.plugins import TimestampedGeoJson, HeatMapWithTime

AISDataDF = pd.read_csv("../input/aisdata/aisdk_20181103.csv") # Point to AIS Data File

"""
AIS Data File Pre-Processing
"""

# Drop extraneous columns from data file
AISDataDF.drop(columns=['Type of position fixing device', 'Data source type', 'A', 'B', 'C', 'D'], inplace=True)
# Drop rows with incomplete ship/location data
AISDataDF.dropna(subset=['Latitude', 'Longitude', 'Width', 'Length', 'MMSI'], inplace=True)
AISDataDF.dropna(how='all', subset=['ROT', 'SOG', 'COG', 'Heading'], inplace=True)

# Filter only Class A AIS System (Large Vessels)
AISDataDF = AISDataDF[(AISDataDF['Type of mobile'] == 'Class A')]
# Filter active vessels
AISDataDF = AISDataDF[(AISDataDF['Navigational status'] == 'Under way using engine') | (AISDataDF['Navigational status'] == 'Engaged in fishing') | (AISDataDF['Navigational status'] == 'Restricted maneuverability')]
# Filter large vessels
AISDataDF = AISDataDF[(AISDataDF['Ship type'] == 'Cargo') | (AISDataDF['Ship type'] == 'Fishing') | (AISDataDF['Ship type'] == 'Passenger') | (AISDataDF['Ship type'] == 'Tanker') | (AISDataDF['Ship type'] == 'Tug') | (AISDataDF['Ship type'] == 'Dredging') | (AISDataDF['Ship type'] == 'Military') | (AISDataDF['Ship type'] == 'Anti-pollution')]

# Format Timestamp column
AISDataDF['# Timestamp'] = pd.to_datetime(AISDataDF['# Timestamp'], format='%d/%m/%Y %H:%M:%S')

# Data info printing:
"""
print(AISDataDF['Ship type'].value_counts(dropna=False))
print(AISDataDF['Navigational status'].value_counts(dropna=False))
print(AISDataDF['Cargo type'].value_counts(dropna=False))
print(AISDataDF.head())
print(AISDataDF.info())
"""


"""
Calculate Predicted Pollution Weightings for Vessels
"""

# Assign predicted pollution weightings for each vessel type/activity
AISDataDF['ActivityWeighting'] = AISDataDF['Navigational status'].map({'Under way using engine': 50, 'Engaged in fishing': 30, 'Restricted maneuverability': 20,})
AISDataDF['ShipTypeWeighting'] = AISDataDF['Ship type'].map({'Tanker': 300, 'Cargo': 300, 'Military': 200, 'Fishing': 100, 'Dredging': 50, 'Passenger': 30, 'Tug': 20, 'Anti-pollution': 0})

# Min-Max Normalisation for vessel sizing
AISDataDF['WidthNormalised'] = (AISDataDF['Width'] - AISDataDF['Width'].min()) / (AISDataDF['Width'].max() - AISDataDF['Width'].min())
AISDataDF['LengthNormalised'] = (AISDataDF['Length'] - AISDataDF['Length'].min()) / (AISDataDF['Length'].max() - AISDataDF['Length'].min())
AISDataDF['SOGNormalised'] = (AISDataDF['SOG'] - AISDataDF['SOG'].min()) / (AISDataDF['SOG'].max() - AISDataDF['SOG'].min())

# Calculate a predicted weighted pollution value & normalise between 0-1
AISDataDF['emissions'] = ((AISDataDF['ActivityWeighting'] + AISDataDF['ShipTypeWeighting']) * (1 + AISDataDF['SOGNormalised'])) + ((75 * AISDataDF['WidthNormalised']) * (100 * AISDataDF['LengthNormalised']) * AISDataDF['SOGNormalised'])
AISDataDF['emissionsNormalised'] = (AISDataDF['emissions'] - AISDataDF['emissions'].min()) / (AISDataDF['emissions'].max() - AISDataDF['emissions'].min())

# Describe normalised pollution weighting values
print(AISDataDF['emissionsNormalised'].describe())


"""
Create Dataset of n Most Polluting Vessels
"""

# Groud AIS data entries, summing normalised emission value, per Ship ID
shipEmissions = pd.DataFrame(AISDataDF.groupby('MMSI')['emissionsNormalised'].sum())
shipEmissions.reset_index(inplace=True)

# Display n=6 most polluting ships
largestShipEmissions = shipEmissions.nlargest(6, 'emissionsNormalised', keep='first')

# Get AIS data for n=6 most polluting ships 
sortedLargestShipEmissions = pd.merge(largestShipEmissions,AISDataDF,how='left',left_on='MMSI',right_on='MMSI',suffixes=('Total',None))
shortLargestShipEmissions = sortedLargestShipEmissions.iloc[::5, :]


"""
Create Folium Map of Denmark (AIS Data Location) With n Most Polluting Vessels
"""

m = folium.Map(location=[56.0643315, 10.7940887], zoom_start=7, tiles="OpenStreetMap")

def create_geojson_features(df):
    features = []
    for lat,lan,time,MMSI,emissionsNormalised in zip(df['Latitude'],df['Longitude'],df['# Timestamp'],df['MMSI'],df['emissionsNormalised']): 
        time = str(time)
        if emissionsNormalised <= 0.3:
            feature = {
                'type': 'Feature',
                'geometry': {
                    'type':'Point', 
                    'coordinates':[lan,lat]
                },
                'properties': {
                    'time': time,
                    'popup': ("MMSI: " + str(MMSI) + " Emissions Multiplier: " + str(emissionsNormalised)),
                    'icon': 'marker',
                    'iconstyle':{
                        'iconSize': [20, 20],
                        'iconUrl': 'https://img.icons8.com/pastel-glyph/2x/4afa31/cargo-ship--v2.png',
                    }
                }
            }
        elif emissionsNormalised > 0.3 and emissionsNormalised <= 0.6:
            feature = {
                'type': 'Feature',
                'geometry': {
                    'type':'Point', 
                    'coordinates':[lan,lat]
                },
                'properties': {
                    'time': time,
                    'popup': ("MMSI: " + str(MMSI) + " Emissions Multiplier: " + str(emissionsNormalised)),
                    'icon': 'marker',
                    'iconstyle':{
                        'iconSize': [20, 20],
                        'iconUrl': 'https://img.icons8.com/pastel-glyph/2x/f98742/cargo-ship--v2.png',
                    }
                }
            }
        else:
            feature = {
                'type': 'Feature',
                'geometry': {
                    'type':'Point', 
                    'coordinates':[lan,lat]
                },
                'properties': {
                    'time': time,
                    'popup': ("MMSI: " + str(MMSI) + " Emissions Multiplier: " + str(emissionsNormalised)),
                    'icon': 'marker',
                    'iconstyle':{
                        'iconSize': [20, 20],
                        'iconUrl': 'https://img.icons8.com/pastel-glyph/2x/fa314a/cargo-ship--v2.png',
                    }
                }
            }
        try:
            update = features.index(MMSI)
        except ValueError:
            features.append(feature)
        else:
            features[update] = feature
            
    return features

features = create_geojson_features(shortLargestShipEmissions)

TimestampedGeoJson(
        {'type': 'FeatureCollection',
        'features': features}
        , period='PT2M'
        , duration='PT20S'
        , add_last_point=False
        , auto_play=False
        , loop=False
        , max_speed=10
        , loop_button=True
        , date_options='YYYY/MM/DD HH:mm:ss'
        , time_slider_drag_update=True
    ).add_to(m)

m


"""
Create Folium HeatMap of Vessel Pollution Around Denmark (AIS Data Location)
"""

AISDataDF['hour'] = [row.hour+1 for row in AISDataDF['# Timestamp']]

GroupedHourAISDataDF = pd.DataFrame(AISDataDF.groupby(['hour','MMSI'])['# Timestamp'].max())
GroupedHourAISDataDF.reset_index(inplace=True)

SortedHourAISDataDF = pd.merge(GroupedHourAISDataDF,AISDataDF,left_on=['hour','MMSI','# Timestamp'],right_on=['hour','MMSI','# Timestamp'])

index_list = [d.strftime('%d/%m/%Y %H:%M:%S') for d in pd.date_range(start=AISDataDF['# Timestamp'].min(), end=AISDataDF['# Timestamp'].max(), freq='H').round('min')]

lat_long_list = []
for i in range(1,25):
    temp=[]
    for index, instance in SortedHourAISDataDF[SortedHourAISDataDF['hour'] == i].iterrows():
        temp.append([instance['Latitude'],instance['Longitude']])
    lat_long_list.append(temp)

mp = folium.Map(location=[56.0643315, 10.7940887], zoom_start=7, tiles="OpenStreetMap")

HeatMapWithTime(lat_long_list, index=index_list, name='Ship Heatmap').add_to(mp)

mp

