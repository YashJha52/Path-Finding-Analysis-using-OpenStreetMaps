🗺️ Path-Finding-Analysis-using-OpenStreetMaps
An interactive Streamlit web app that visualizes and compares real-world pathfinding algorithms — A*, Dijkstra, BFS, and Flood Fill — on actual OpenStreetMap road networks using OSMnx, NetworkX, and Folium.
🌟 Features
🌍 Real-World Map Integration (via OSMnx)
Load live road networks for cities worldwide or custom coordinates.
🧭 Pathfinding Algorithms
A* – Heuristic search using geodesic distance
Dijkstra’s Algorithm – Shortest path in weighted graphs
Breadth-First Search (BFS) – Level-wise exploration
Flood Fill (DFS-style) – Randomized exhaustive exploration
🧮 Performance Comparison Dashboard
Displays path length, explored nodes, efficiency %, and estimated travel time
Color-coded results table with automatic highlighting of best metrics
🗺️ Interactive Map Visualization
Start/Goal markers
Color-coded algorithm paths
Dynamic zoom to fit all routes
Custom legend and tooltips
🧠 Educational Insights
Built-in explanations for each algorithm
Ideal for teaching AI, data structures, and graph algorithms using real maps
🧩 Flexible Input Options
Use location names (e.g., “Andheri, Mumbai”)
Or input latitude & longitude directly
⚙️ Simulated Map Mode
Automatically activates when OSMnx is unavailable
Perfect for offline testing and demonstrations
🧰 Tech Stack
Component	Technology
Frontend/UI	Streamlit
Maps & Visualization	Folium + Leaflet
Routing Data	OSMnx (OpenStreetMap)
Graph Processing	NetworkX
Geocoding & Distance	Geopy
Geometry Handling	Shapely
Data Display	Pandas + Styled Tables
💻 Installation
1️⃣ Clone the Repository
git clone https://github.com/yourusername/pathfinding-app.git
cd pathfinding-app
2️⃣ Install Dependencies
pip install streamlit folium osmnx networkx geopy shapely pandas streamlit-folium
💡 Optional: Create a virtual environment before installing dependencies.
3️⃣ Run the App
streamlit run app.py
⚙️ How It Works
Select a city or enter coordinates.
The app loads the road network using OSMnx (or creates a simulated grid).
Click “🚀 Run Algorithms” to compute paths between Start and Goal nodes.
The results are visualized on an interactive map and summarized in a performance table.
📸 Example Preview
(Add a screenshot of your app running here — for example:)
“A* and Dijkstra’s paths between Andheri and Kandivali visualized on OpenStreetMap.”
📜 License
MIT License © 2025 — Open for educational and research use.
✅ Perfect for:
AI and ML students learning search algorithms
Teaching graph theory and pathfinding
Visual demos for route optimization and navigation algorithms
