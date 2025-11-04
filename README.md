# Path-Finding Analysis using OpenStreetMap

An interactive Streamlit web app that visualizes and compares real-world pathfinding algorithms — A*, Dijkstra, BFS, and Flood Fill — on OpenStreetMap road networks using OSMnx and NetworkX. The app is designed for learning, teaching, and demoing pathfinding and graph algorithms on real map data.

## Features

- Real-World Map Integration (via OSMnx)
  - Load road networks for cities worldwide or custom coordinates.
- Pathfinding Algorithms
  - A* — Heuristic search using geodesic distance
  - Dijkstra — Shortest path in weighted graphs
  - Breadth-First Search (BFS) — Level-wise exploration
  - Flood Fill (DFS-style) — Exhaustive exploration variant
- Performance Comparison Dashboard
  - Displays path length, explored nodes, efficiency %, and estimated travel time
  - Color-coded results table with automatic highlighting of best metrics
- Interactive Map Visualization (Folium + Leaflet)
  - Start/Goal markers and color-coded algorithm paths
  - Dynamic zoom to fit all routes and custom legend/tooltips
- Educational Insights
  - Explanations for each algorithm and visualization of exploration behavior
- Flexible Input Options
  - Use location names (e.g., "Andheri, Mumbai") or input latitude & longitude directly
- Simulated Map Mode
  - Activates when OSMnx is unavailable so the app works offline for demos/tests

## Tech Stack

- Frontend/UI: Streamlit
- Maps & Visualization: Folium + Leaflet
- Routing Data: OSMnx (OpenStreetMap)
- Graph Processing: NetworkX
- Geocoding & Distance: Geopy
- Geometry Handling: Shapely
- Data Display: Pandas + Styled Tables

## Installation

1. Clone the repository

```bash
git clone https://github.com/YashJha52/Path-Finding-Analysis-using-OpenStreetMaps.git
cd Path-Finding-Analysis-using-OpenStreetMaps
```

2. (Optional) Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
.\.venv\Scripts\activate  # Windows (PowerShell)
```

3. Install dependencies

```bash
pip install -r requirements.txt
# or install individually:
pip install streamlit folium osmnx networkx geopy shapely pandas streamlit-folium
```

4. Run the app

```bash
streamlit run app.py
```

## Usage

1. Select a city or enter custom coordinates.
2. Set Start and Goal locations (either by clicking on the map or entering coordinates).
3. Click "Run Algorithms" to compute and visualize routes.
4. Compare metrics in the performance table and view each algorithm's path on the map.

## Example Preview

_Add a screenshot of the app here (e.g., A* and Dijkstra paths visualized on OpenStreetMap)._ 

## Development Notes

- If OSMnx cannot download map data (e.g., offline), the app falls back to a simulated grid network for demonstrations.
- Performance metrics are computed from NetworkX path results and on-screen exploration statistics.
- Tweak map tile providers in the app for different visual styles.

## Contributing

Contributions are welcome. Please open issues or pull requests for bug reports, improvements, or feature requests.

## License

MIT License © 2025 — Open for educational and research use.
