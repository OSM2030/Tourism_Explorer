# app.py
import os
import uuid
from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

# Use Agg backend for matplotlib (non-GUI) to avoid macOS backend issues
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Flask app
app = Flask(__name__)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.path.join(APP_ROOT, "spots.csv")
CHART_DIR = os.path.join(APP_ROOT, "static", "charts")
os.makedirs(CHART_DIR, exist_ok=True)

# Load dataset
df = pd.read_csv(DATA_FILE)

# geolocator for place name -> lat/lon
geolocator = Nominatim(user_agent="tourism_explorer_demo")

def find_nearby_spots(user_lat, user_lon, radius_km=10):
    """Return dataframe filtered to spots within radius_km from user's location."""
    def dist(row):
        return geodesic((user_lat, user_lon), (row['lat'], row['lon'])).km
    df_local = df.copy()
    df_local['distance_km'] = df_local.apply(dist, axis=1)
    nearby = df_local[df_local['distance_km'] <= radius_km].sort_values('distance_km')
    return nearby

def make_map(user_lat, user_lon, spots_df):
    """Create folium map centered at user location with markers for spots_df."""
    m = folium.Map(location=[user_lat, user_lon], zoom_start=10, control_scale=True)
    folium.Marker([user_lat, user_lon], tooltip="Your location", icon=folium.Icon(color='red', icon='user')).add_to(m)
    marker_cluster = MarkerCluster().add_to(m)
    for _, row in spots_df.iterrows():
        popup_html = (
            f"<b>{row['name']}</b><br>"
            f"Visitors: {int(row['annual_visitors']):,}<br>"
            f"{row.get('description','')}<br>"
            f"Distance: {row['distance_km']:.2f} km"
        )
        folium.Marker([row['lat'], row['lon']], popup=popup_html).add_to(marker_cluster)
    return m

def make_bar_chart(spots_df, title="Visitors"):
    """Generate a bar chart of visitor counts for given spots_df and save PNG file path."""
    if spots_df.empty:
        return None
    plt.figure(figsize=(8,4))
    spots_df_sorted = spots_df.sort_values('annual_visitors', ascending=False)
    names = spots_df_sorted['name'].astype(str)
    visitors = spots_df_sorted['annual_visitors'].astype(int)
    plt.bar(names, visitors)
    plt.xticks(rotation=45, ha='right')
    plt.ylabel("Annual Visitors")
    plt.title(title)
    plt.tight_layout()
    fname = f"{uuid.uuid4().hex}.png"
    fpath = os.path.join(CHART_DIR, fname)
    plt.savefig(fpath, dpi=150)
    plt.close()
    return f"charts/{fname}"

@app.route("/", methods=["GET","POST"])
def index():
    if request.method == "POST":
        place = request.form.get("place", "").strip()
        lat = request.form.get("lat", "").strip()
        lon = request.form.get("lon", "").strip()
        radius = float(request.form.get("radius", 10))
        if lat and lon:
            try:
                user_lat = float(lat)
                user_lon = float(lon)
            except ValueError:
                return render_template("index.html", error="Invalid latitude/longitude.")
        elif place:
            # geocode place name
            location = geolocator.geocode(place)
            if location is None:
                return render_template("index.html", error="Could not geocode the place name. Try coordinates.")
            user_lat = location.latitude
            user_lon = location.longitude
        else:
            return render_template("index.html", error="Please enter a place name or latitude & longitude.")
        return redirect(url_for('map_view', lat=user_lat, lon=user_lon, radius=radius))
    return render_template("index.html")

@app.route("/map")
def map_view():
    try:
        user_lat = float(request.args.get("lat"))
        user_lon = float(request.args.get("lon"))
        radius = float(request.args.get("radius", 10))
    except (TypeError, ValueError):
        return redirect(url_for('index'))

    nearby = find_nearby_spots(user_lat, user_lon, radius)
    folium_map = make_map(user_lat, user_lon, nearby)
    map_html = folium_map._repr_html_()  # embed folium map HTML
    chart_path = make_bar_chart(nearby, title=f"Visitors within {radius} km")
    return render_template("map.html", map_html=map_html, chart_path=chart_path, count=len(nearby), radius=radius)

@app.route("/dashboard")
def dashboard():
    # Show top N overall attractions
    top = df.sort_values('annual_visitors', ascending=False).head(10)
    chart_path = make_bar_chart(top, title="Top 10 Attractions (sample dataset)")
    return render_template("dashboard.html", chart_path=chart_path)

if __name__ == "__main__":
    app.run(debug=True)
