import math
import streamlit as st
import folium
import heapq
import random
import pandas as pd
import networkx as nx
from streamlit_folium import st_folium
from collections import deque
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from shapely.geometry import LineString

try:
    import osmnx as ox
    OSMNX_AVAILABLE = True
    ox.settings.log_console = True
    ox.settings.use_cache = True
except ImportError:
    OSMNX_AVAILABLE = False


st.set_page_config(page_title="Pathfinding", layout="wide")
st.title("🗺️ Real-World Pathfinding")

if not OSMNX_AVAILABLE:
    st.warning("**OSMnx not available** - Using simulated data. Install with: `pip install osmnx`")

# Initialize geocoder with a longer timeout
try:
    geolocator = Nominatim(user_agent="pathfinding_app", timeout=10)
except Exception as e:
    st.error(f"Could not initialize geocoder: {e}")
    geolocator = None


# Define speeds for different transport modes (in meters per second)
TRANSPORT_SPEEDS = {
    "walk": 1.4,    # ~5 km/h
    "bike": 4.2,    # ~15 km/h
    "drive": 13.9   # ~50 km/h (average city speed)
}


# Simulated Map (used when OSMnx isn't available)
def create_simulated_map(center_lat, center_lng, start_lat, start_lon, goal_lat, goal_lon):
    m = folium.Map(location=[center_lat, center_lng], zoom_start=14)

    # Add grid pattern
    for i in range(-8, 9):
        lat = center_lat + i * 0.0008
        folium.PolyLine([[lat, center_lng - 8 * 0.0008], [lat, center_lng + 8 * 0.0008]], color='gray', weight=2).add_to(m)
        lng = center_lng + i * 0.0008
        folium.PolyLine([[center_lat - 8 * 0.0008, lng], [center_lat + 8 * 0.0008, lng]], color='gray', weight=2).add_to(m)

    # Add markers
    if start_lat and start_lon:
        folium.Marker([start_lat, start_lon], popup="🏁 Start", tooltip="START",
                      icon=folium.Icon(color="green", icon="play", prefix="fa")).add_to(m)
    if goal_lat and goal_lon:
        folium.Marker([goal_lat, goal_lon], popup="🎯 Goal", tooltip="GOAL",
                      icon=folium.Icon(color="red", icon="flag", prefix="fa")).add_to(m)

    # Add simulated paths with proper styling
    if all([start_lat, start_lon, goal_lat, goal_lon]):
        # A* path (direct) - use same color as Dijkstra
        folium.PolyLine([[start_lat, start_lon], [goal_lat, goal_lon]],
                        color='#45B7D1', weight=6, opacity=0.9,
                        popup="<b>A* Search</b><br>Length: 850m<br>Nodes: 12",
                        tooltip="A* Search Path").add_to(m)

        # BFS path (winding)
        mid_lat, mid_lon = (start_lat + goal_lat) / 2 + 0.002, (start_lon + goal_lon) / 2 - 0.002
        folium.PolyLine([[start_lat, start_lon], [mid_lat, mid_lon], [goal_lat, goal_lon]],
                        color='#FF6B6B', weight=6, opacity=0.9,
                        popup="<b>BFS</b><br>Length: 950m<br>Nodes: 18",
                        tooltip="BFS Path").add_to(m)

        # Flood Fill path (different winding)
        flood_mid_lat, flood_mid_lon = (start_lat + goal_lat) / 2 - 0.001, (start_lon + goal_lon) / 2 + 0.001
        folium.PolyLine([[start_lat, start_lon], [flood_mid_lat, flood_mid_lon], [goal_lat, goal_lon]],
                        color='#9b59b6', weight=6, opacity=0.9,
                        popup="<b>Flood Fill</b><br>Length: 7200m<br>Nodes: 50",
                        tooltip="Flood Fill Path").add_to(m)

        # Dijkstra path (similar to A* but with dash)
        folium.PolyLine([[start_lat, start_lon], [goal_lat, goal_lon]],
                        color='#45B7D1', weight=6, opacity=0.9, dash_array='5, 10',
                        popup="<b>Dijkstra's</b><br>Length: 850m<br>Nodes: 15",
                        tooltip="Dijkstra's Path").add_to(m)

    return m


# ----------------------
# Helper Functions
# ----------------------
def geocode_location(location_name):
    """Convert location name to coordinates with better error handling"""
    if not geolocator:
        st.error("Geocoder is not available.")
        return None, None
    try:
        location = geolocator.geocode(location_name)
        if location:
            return location.latitude, location.longitude
        return None, None
    except GeocoderTimedOut:
        st.error("Geocoding service timed out. Please try again or use coordinates directly.")
        return None, None
    except GeocoderServiceError as e:
        st.error(f"Geocoding service error: {e}. Please try again or use coordinates directly.")
        return None, None
    except Exception as e:
        st.error(f"An unexpected error occurred during geocoding: {e}")
        return None, None


def find_nearest_node(graph, lat, lng):
    """Use OSMnx utility when available, otherwise fallback to scanning nodes."""
    if graph is None:
        return None
    try:
        if OSMNX_AVAILABLE:
            # ox.distance.nearest_nodes expects x=lon, y=lat
            return ox.distance.nearest_nodes(graph, lng, lat)
    except Exception:
        pass

    # Fallback: brute-force nearest node
    min_dist, nearest = float('inf'), None
    for node, data in graph.nodes(data=True):
        node_lat = data.get('y') or data.get('lat') or 0.0
        node_lon = data.get('x') or data.get('lon') or 0.0
        try:
            dist = geodesic((lat, lng), (node_lat, node_lon)).meters
        except Exception:
            dist = float('inf')
        if dist < min_dist:
            min_dist, nearest = dist, node
    return nearest


def get_edge_length(edge):
    """Return the best available length for an edge data dict."""
    if edge is None:
        return None
    if 'length' in edge and edge['length'] is not None:
        return float(edge['length'])
    # try geometry based length
    if 'geometry' in edge and edge['geometry'] is not None:
        coords = list(edge['geometry'].coords)
        total = 0.0
        for a, b in zip(coords, coords[1:]):
            total += geodesic((a[1], a[0]), (b[1], b[0])).meters
        return total
    return None


def get_min_edge_length_between(graph, u, v):
    """MultiGraph-safe: return the minimum known length among parallel edges or None"""
    edge_data = graph.get_edge_data(u, v)
    if not edge_data:
        return None
    lengths = []
    for key, ed in edge_data.items():
        l = get_edge_length(ed)
        if l is not None:
            lengths.append(l)
    if lengths:
        return min(lengths)
    # fallback: geodesic between nodes
    u_data, v_data = graph.nodes[u], graph.nodes[v]
    return geodesic((u_data['y'], u_data['x']), (v_data['y'], v_data['x'])).meters


def path_to_coords(graph, path):
    """
    Convert a path (list of nodes) to a sequence of lat/lon coordinates that follows edge geometry
    when available. This prevents straight-line shortcuts when edges have intermediate geometry.

    NOTE: improved fallback - if an edge lookup (u, v) fails (e.g. directional graph or edge stored
    in reverse), try (v, u) and reverse geometry accordingly. This fixes cases where a path exists
    but edge data is only stored in the opposite direction.
    """
    if not path or len(path) == 0:
        return []

    coords = []
    for u, v in zip(path[:-1], path[1:]):
        reverse = False
        edge_data = graph.get_edge_data(u, v)
        if not edge_data:
            # try the opposite direction (some graphs may store only (v,u))
            edge_data = graph.get_edge_data(v, u)
            if edge_data:
                reverse = True

        if not edge_data:
            # no edge data (shouldn't normally happen), fallback to node coordinates
            u_n = graph.nodes[u]; v_n = graph.nodes[v]
            segment = [(u_n['y'], u_n['x']), (v_n['y'], v_n['x'])]
        else:
            # choose the edge entry with the most geometry/length info (prefer one with geometry)
            chosen = None
            for key, ed in edge_data.items():
                if ed and ed.get('geometry') is not None:
                    chosen = ed
                    break
            if chosen is None:
                chosen = list(edge_data.values())[0]

            if chosen and chosen.get('geometry') is not None:
                raw = list(chosen['geometry'].coords)  # (lon, lat)
                segment = [(pt[1], pt[0]) for pt in raw]
                if reverse:
                    # if we used the opposite edge direction, reverse the sequence so it follows u->v
                    segment = list(reversed(segment))
            else:
                u_n = graph.nodes[u]; v_n = graph.nodes[v]
                segment = [(u_n['y'], u_n['x']), (v_n['y'], v_n['x'])]

        # Append segment, avoiding duplicate points
        if coords and coords[-1] == segment[0]:
            coords.extend(segment[1:])
        else:
            coords.extend(segment)

    # if still empty (unlikely), fall back to node coordinates
    if not coords:
        coords = [(graph.nodes[n]['y'], graph.nodes[n]['x']) for n in path]
    return coords


def calculate_path_length(graph, path):
    """Compute path length by summing actual edge lengths (or geometry lengths)."""
    if not path or len(path) < 2:
        return 0.0
    total = 0.0
    for u, v in zip(path[:-1], path[1:]):
        l = get_min_edge_length_between(graph, u, v)
        if l is not None:
            total += l
    return total


# ----------------------
# Pathfinding Algorithms (robust, on-graph)
# ----------------------
def bfs_graph(graph, start, goal):
    """BFS that returns full path and number of nodes popped (explored)."""
    queue = deque([(start, [start])])
    visited = {start}
    nodes_explored = 0
    while queue:
        node, path = queue.popleft()
        nodes_explored += 1
        if node == goal:
            return path, nodes_explored
        for neighbor in graph.neighbors(node):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
    return None, nodes_explored


def astar_graph(graph, start, goal):
    """A* using geodesic heuristic and edge lengths."""
    if start == goal:
        return [start], 1

    def heuristic(u, v):
        udata, vdata = graph.nodes[u], graph.nodes[v]
        return geodesic((udata['y'], udata['x']), (vdata['y'], vdata['x'])).meters

    start_h = heuristic(start, goal)
    heap = [(start_h, 0.0, start, [start])]
    visited = set()
    nodes_expanded = 0

    while heap:
        f, g, node, path = heapq.heappop(heap)
        if node == goal:
            return path, nodes_expanded + 1
        if node in visited:
            continue
        visited.add(node)
        nodes_expanded += 1

        for neighbor in graph.neighbors(node):
            if neighbor in visited:
                continue
            edge_len = get_min_edge_length_between(graph, node, neighbor) or 1.0
            new_g = g + edge_len
            h = heuristic(neighbor, goal)
            heapq.heappush(heap, (new_g + h, new_g, neighbor, path + [neighbor]))

    return None, nodes_expanded


def dijkstra_graph(graph, start, goal):
    """Dijkstra (priority by cumulative distance)."""
    if start == goal:
        return [start], 1
    pq = [(0.0, start, [start])]
    visited = set()
    nodes_expanded = 0
    while pq:
        dist, node, path = heapq.heappop(pq)
        if node == goal:
            return path, nodes_expanded + 1
        if node in visited:
            continue
        visited.add(node)
        nodes_expanded += 1
        for neighbor in graph.neighbors(node):
            if neighbor in visited:
                continue
            edge_len = get_min_edge_length_between(graph, node, neighbor) or 1.0
            heapq.heappush(pq, (dist + edge_len, neighbor, path + [neighbor]))
    return None, nodes_expanded


def flood_fill_graph(graph, start, goal):
    """DFS-style flood-fill (stack), with random neighbor ordering for variety."""
    stack = [(start, [start])]
    visited = {start}
    nodes_expanded = 0
    while stack:
        node, path = stack.pop()
        nodes_expanded += 1
        if node == goal:
            return path, nodes_expanded
        neighbors = list(graph.neighbors(node))
        random.shuffle(neighbors)
        for neighbor in neighbors:
            if neighbor not in visited:
                visited.add(neighbor)
                stack.append((neighbor, path + [neighbor]))
    return None, nodes_expanded


# ----------------------
# Graph Loading
# ----------------------
@st.cache_data
def load_network(center, network_type, area_km):
    """Load an OSMnx network around center.
    area_km: approximate radius in kilometers (not area). If OSMnx not available this returns None.
    """
    if not OSMNX_AVAILABLE:
        return None
    try:
        with st.spinner(f"Loading {network_type} network for ~{area_km:.1f}km radius..."):
            dist_m = int(max(500, min(50000, area_km * 1000)))
            G = ox.graph_from_point(center, dist=dist_m, network_type=network_type, simplify=True)
            return G
    except Exception as e:
        st.error(f"Error loading map: {e}")
        return None


# ----------------------
# UI: Sidebar Settings
# ----------------------
st.sidebar.header("📍 Settings")
cities = {
    "New York": (40.7128, -74.0060),
    "San Francisco": (37.7749, -122.4194),
    "London": (51.5074, -0.1278),
    "Tokyo": (35.6762, 139.6503),
    "Mumbai": (19.0760, 72.8777),
    "Custom Location": None
}

selected = st.sidebar.selectbox("City:", list(cities.keys()))

# Handle custom location
if selected == "Custom Location":
    st.sidebar.subheader("🌍 Custom Location")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        custom_lat = st.number_input("Latitude", value=40.7128, format="%.6f", key="custom_lat")
    with col2:
        custom_lon = st.number_input("Longitude", value=-74.0060, format="%.6f", key="custom_lon")
    city_coords = (custom_lat, custom_lon)
    location_name = f"Custom ({custom_lat:.2f}, {custom_lon:.2f})"
else:
    city_coords = cities[selected]
    location_name = selected

if OSMNX_AVAILABLE:
    network_type = st.sidebar.radio("Network:", ["drive", "walk", "bike"], horizontal=True)
    area_size = st.sidebar.slider("Area (km radius):", 1, 25, 2)
else:
    network_type, area_size = "walk", 2

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Route")
input_method = st.sidebar.radio("Method:", ["Auto-generate", "Manual"])

# Initialize variables in session state
if 'manual_graph' not in st.session_state:
    st.session_state.manual_graph = None
if 'results' not in st.session_state:
    st.session_state.results = None

# ----------------------
# Main App Logic
# ----------------------
graph = None
start_node = None
goal_node = None
start_lat, start_lon = None, None
goal_lat, goal_lon = None, None
final_location_name = location_name

if input_method == "Auto-generate":
    graph = load_network(city_coords, network_type, area_size)
    if graph and len(graph.nodes) >= 2:
        center_lat, center_lon = city_coords
        center_node = find_nearest_node(graph, center_lat, center_lon)
        if center_node is None:
            nodes_list = list(graph.nodes())
            start_node, goal_node = nodes_list[0], nodes_list[-1]
        else:
            undirected = graph.to_undirected()
            comp = None
            for c in nx.connected_components(undirected):
                if center_node in c:
                    comp = c
                    break
            if comp:
                nodes = list(comp)
                distances = []
                for n in nodes:
                    nd = graph.nodes[n]
                    distances.append((geodesic((center_lat, center_lon), (nd['y'], nd['x'])).meters, n))
                distances.sort(reverse=True)
                goal_node = distances[0][1]
                best_start = center_node
                best_score = -1
                goal_data = graph.nodes[goal_node]
                for i in range(min(len(distances), 30)):
                    candidate = distances[i][1]
                    cand_data = graph.nodes[candidate]
                    d_center = geodesic((center_lat, center_lon), (cand_data['y'], cand_data['x'])).meters
                    d_goal = geodesic((goal_data['y'], goal_data['x']), (cand_data['y'], cand_data['x'])).meters
                    score = d_goal - max(0, d_center - 2000) / 2
                    if score > best_score:
                        best_score, best_start = score, candidate
                start_node, goal_node = best_start, goal_node

        if start_node and goal_node:
            start_data, goal_data = graph.nodes[start_node], graph.nodes[goal_node]
            start_lat, start_lon = start_data['y'], start_data['x']
            goal_lat, goal_lon = goal_data['y'], goal_data['x']
            st.sidebar.success(f"Route generated in {location_name}")

else:  # Manual Mode
    input_type = st.sidebar.radio("Input Type:", ["Location Names", "Coordinates"], key="input_type")

    if input_type == "Location Names":
        st.sidebar.markdown("### 🏁 Start Location")
        start_location_input = st.sidebar.text_input("e.g., Andheri, Mumbai", key="start_location_input")

        st.sidebar.markdown("### 🎯 Goal Location")
        goal_location_input = st.sidebar.text_input("e.g., Kandivali, Mumbai", key="goal_location_input")

        if st.sidebar.button("🔍 Find Locations & Load Map"):
            # Clear previous results
            st.session_state.manual_graph = None
            st.session_state.results = None

            if not start_location_input or not goal_location_input:
                st.sidebar.error("Please enter both a start and goal location.")
            else:
                start_lat, start_lon = geocode_location(start_location_input)
                goal_lat, goal_lon = geocode_location(goal_location_input)

                if start_lat and goal_lat:
                    st.sidebar.success(f"Found: {start_location_input} and {goal_location_input}")

                    center_lat = (start_lat + goal_lat) / 2
                    center_lon = (start_lon + goal_lon) / 2
                    distance_km = geodesic((start_lat, start_lon), (goal_lat, goal_lon)).kilometers
                    dynamic_area_size = max(2, (distance_km / 2) + 2)
                    dynamic_area_size = min(25, dynamic_area_size)

                    loaded_graph = load_network((center_lat, center_lon), network_type, dynamic_area_size)

                    if loaded_graph and len(loaded_graph.nodes) > 0:
                        start_node = find_nearest_node(loaded_graph, start_lat, start_lon)
                        goal_node = find_nearest_node(loaded_graph, goal_lat, goal_lon)

                        if start_node and goal_node:
                            st.sidebar.success("✅ Locations found on the map! You can now run the algorithms.")
                            st.session_state.manual_graph = loaded_graph
                            st.session_state.manual_start_node = start_node
                            st.session_state.manual_goal_node = goal_node
                            st.session_state.manual_coords = {
                                'start_lat': start_lat, 'start_lon': start_lon,
                                'goal_lat': goal_lat, 'goal_lon': goal_lon
                            }
                            st.session_state.manual_location_names = (start_location_input, goal_location_input)
                        else:
                            st.sidebar.error("❌ Could not find road nodes near your locations. The area might not have detailed road data.")
                    else:
                        st.sidebar.error("❌ Failed to load road network for this area. It might be too remote or lack data.")
    else:  # Coordinates input
        st.sidebar.markdown("### 🏁 Start Coordinates")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_lat = st.number_input("Start Lat", value=19.1196, format="%.6f", key="manual_start_lat")
        with col2:
            start_lon = st.number_input("Start Lon", value=72.8465, format="%.6f", key="manual_start_lon")

        st.sidebar.markdown("### 🎯 Goal Coordinates")
        col3, col4 = st.sidebar.columns(2)
        with col3:
            goal_lat = st.number_input("Goal Lat", value=19.2159, format="%.6f", key="manual_goal_lat")
        with col4:
            goal_lon = st.number_input("Goal Lon", value=72.8617, format="%.6f", key="manual_goal_lon")

        if st.sidebar.button("📍 Load Map & Find Nodes"):
            if all([start_lat is not None, start_lon is not None, goal_lat is not None, goal_lon is not None]):
                st.session_state.manual_graph = None
                st.session_state.results = None

                center_lat = (start_lat + goal_lat) / 2
                center_lon = (start_lon + goal_lon) / 2
                distance_km = geodesic((start_lat, start_lon), (goal_lat, goal_lon)).kilometers
                dynamic_area_size = max(2, (distance_km / 2) + 2)
                dynamic_area_size = min(25, dynamic_area_size)

                loaded_graph = load_network((center_lat, center_lon), network_type, dynamic_area_size)

                if loaded_graph and len(loaded_graph.nodes) > 0:
                    start_node = find_nearest_node(loaded_graph, start_lat, start_lon)
                    goal_node = find_nearest_node(loaded_graph, goal_lat, goal_lon)

                    if start_node and goal_node:
                        st.sidebar.success("✅ Road nodes found! You can now run the algorithms.")
                        st.session_state.manual_graph = loaded_graph
                        st.session_state.manual_start_node = start_node
                        st.session_state.manual_goal_node = goal_node
                        st.session_state.manual_coords = {
                            'start_lat': start_lat, 'start_lon': start_lon,
                            'goal_lat': goal_lat, 'goal_lon': goal_lon
                        }
                        st.session_state.manual_location_names = ("Custom Start", "Custom Goal")
                    else:
                        st.sidebar.error("❌ Could not find road nodes near your coordinates.")
                else:
                    st.sidebar.error("❌ Failed to load road network for this area.")
            else:
                st.sidebar.error("Please enter all coordinates.")

    # Load data from session state if it exists
    if st.session_state.manual_graph:
        graph = st.session_state.manual_graph
        start_node = st.session_state.manual_start_node
        goal_node = st.session_state.manual_goal_node
        coords = st.session_state.manual_coords
        start_lat, start_lon = coords['start_lat'], coords['start_lon']
        goal_lat, goal_lon = coords['goal_lat'], coords['goal_lon']
        start_name, goal_name = st.session_state.manual_location_names
        final_location_name = f"Route: {start_name} to {goal_name}"
    else:
        st.sidebar.info("Enter locations/coordinates and click the button to begin.")


# If auto-generate mode had filled graph & nodes, use them
if input_method == "Auto-generate" and graph is None and OSMNX_AVAILABLE:
    graph = load_network(city_coords, network_type, area_size)


# ----------------------
# Run Algorithms Button
# ----------------------
if start_node and goal_node and graph:
    if st.sidebar.button("🚀 Run Algorithms", type="primary"):
        with st.spinner("Computing paths..."):
            bfs_path, bfs_nodes = bfs_graph(graph, start_node, goal_node)
            astar_path, astar_nodes = astar_graph(graph, start_node, goal_node)
            dijkstra_path, dijkstra_nodes = dijkstra_graph(graph, start_node, goal_node)
            flood_path, flood_nodes = flood_fill_graph(graph, start_node, goal_node)

            results = {
                'bfs': (bfs_path, bfs_nodes),
                'astar': (astar_path, astar_nodes),
                'dijkstra': (dijkstra_path, dijkstra_nodes),
                'flood': (flood_path, flood_nodes),
                'graph': graph,
                'start': (start_lat, start_lon),
                'goal': (goal_lat, goal_lon),
                'location': final_location_name,
                'network_type': network_type
            }
            # Precompute coords for display (if graph present)
            for k in ['bfs', 'astar', 'dijkstra', 'flood']:
                path, _ = results[k]
                if path:
                    results[f"{k}_coords"] = path_to_coords(graph, path)
                else:
                    results[f"{k}_coords"] = None

            st.session_state.results = results
            st.success("✅ All algorithms completed!")


# ----------------------
# Create Map
# ----------------------
if not OSMNX_AVAILABLE and all([start_lat, start_lon, goal_lat, goal_lon]):
    m = create_simulated_map(city_coords[0], city_coords[1], start_lat, start_lon, goal_lat, goal_lon)
else:
    if start_lat and goal_lat:
        map_center = [(start_lat + goal_lat) / 2, (start_lon + goal_lon) / 2]
    elif city_coords:
        map_center = city_coords
    else:
        map_center = [40.7128, -74.0060]

    m = folium.Map(location=map_center, zoom_start=13)


# ----------------------
# Display Results on Map
# ----------------------
if st.session_state.results:
    r = st.session_state.results
    graph = r['graph']

    folium.Marker(r['start'], popup="🏁 Start", tooltip="START",
                  icon=folium.Icon(color="green", icon="play", prefix="fa")).add_to(m)
    folium.Marker(r['goal'], popup="🎯 Goal", tooltip="GOAL",
                  icon=folium.Icon(color="red", icon="flag", prefix="fa")).add_to(m)

    styles = {
        'bfs': {'color': '#FF6B6B', 'dash': None},
        'astar': {'color': '#45B7D1', 'dash': None},
        'dijkstra': {'color': '#45B7D1', 'dash': '5,10'},
        'flood': {'color': '#9b59b6', 'dash': '2,8'}
    }

    names = {'bfs': 'BFS', 'astar': 'A*', 'dijkstra': 'Dijkstra', 'flood': 'Flood Fill'}

    all_coords = []
    for algo in ['bfs', 'astar', 'dijkstra', 'flood']:
        path, nodes = r[algo]
        coords = r.get(f"{algo}_coords", None)
        if path and coords and len(coords) > 0:
            length = calculate_path_length(graph, path)
            all_coords.extend(coords)
            folium.PolyLine(coords, color=styles[algo]['color'], weight=6,
                            dash_array=styles[algo]['dash'], opacity=0.9,
                            popup=f"<b>{names[algo]}</b><br>Length: {length:.0f}m<br>Nodes: {len(path)}",
                            tooltip=f"{names[algo]} Path").add_to(m)

    # Fit map bounds to show full route for all algorithms
    if all_coords:
        lats = [c[0] for c in all_coords]
        lons = [c[1] for c in all_coords]
        sw = [min(lats), min(lons)]
        ne = [max(lats), max(lons)]
        m.fit_bounds([sw, ne])


# Legend
legend = '''
<div style="position:fixed;top:10px;left:50px;width:280px;background:white;border:2px solid #2c3e50;border-radius:10px;z-index:9999;padding:15px;font-family:Arial,sans-serif;box-shadow:0 4px 6px rgba(0,0,0,0.1);">
<h4 style="margin:0 0 15px 0;color:#2c3e50;border-bottom:2px solid #eee;padding-bottom:8px;">🗺️ Pathfinding Algorithms</h4>
<div style="display:flex;align-items:center;margin:8px 0;"><div style="width:20px;height:20px;background:green;border-radius:50%;margin-right:10px;"></div><span style="font-weight:bold;color:#2c3e50;">🏁 Start Point</span></div>
<div style="display:flex;align-items:center;margin:8px 0;"><div style="width:20px;height:20px;background:red;border-radius:50%;margin-right:10px;"></div><span style="font-weight:bold;color:#2c3e50;">🎯 Goal Point</span></div>
<div style="border-top:1px solid #eee;margin:12px 0;padding-top:12px;">
<div style="display:flex;align-items:center;margin:8px 0;"><div style="width:25px;height:6px;background:#FF6B6B;margin-right:10px;"></div><span style="font-weight:bold;color:#FF6B6B;">BFS Algorithm</span></div>
<div style="display:flex;align-items:center;margin:8px 0;"><div style="width:25px;height:6px;background:#45B7D1;margin-right:10px;"></div><span style="font-weight:bold;color:#45B7D1;">A* Search</span></div>
<div style="display:flex;align-items:center;margin:8px 0;"><div style="width:25px;height:6px;background:#45B7D1;margin-right:10px;border:1px dashed #45B7D1;"></div><span style="font-weight:bold;color:#45B7D1;">Dijkstra's</span></div>
<div style="display:flex;align-items:center;margin:8px 0;"><div style="width:25px;height:6px;background:#9b59b6;margin-right:10px;border:1px dotted #9b59b6;"></div><span style="font-weight:bold;color:#9b59b6;">Flood Fill</span></div>
</div>
</div>
'''
m.get_root().html.add_child(folium.Element(legend))

st.subheader(f"🗺️ Interactive Map - {final_location_name}")
st_folium(m, width=1200, height=600)


# ----------------------
# Results table with styling
# ----------------------
if st.session_state.results:
    st.subheader("📊 Algorithm Performance Comparison")
    r = st.session_state.results
    graph = r['graph']
    current_network_type = r.get('network_type', 'walk')
    current_speed = TRANSPORT_SPEEDS.get(current_network_type, 1.4)

    data = []
    for algo, name in [('bfs', 'BFS'), ('astar', 'A*'), ('dijkstra', 'Dijkstra'), ('flood', 'Flood Fill')]:
        path, nodes = r[algo]
        if path:
            length = calculate_path_length(graph, path)
            time_estimate = length / current_speed
            efficiency = (len(path) / nodes) * 100 if nodes > 0 else 0
            data.append({
                'Algorithm': name,
                'Path Found': '✅',
                'Path Length (m)': f"{length:.1f}",
                'Time (s)': f"{time_estimate:.1f}",
                'Nodes Explored': nodes,
                'Path Nodes': len(path),
                'Efficiency (%)': f"{efficiency:.1f}"
            })
        else:
            data.append({
                'Algorithm': name,
                'Path Found': '❌',
                'Path Length (m)': 'N/A',
                'Time (s)': 'N/A',
                'Nodes Explored': nodes,
                'Path Nodes': 0,
                'Efficiency (%)': 'N/A'
            })

    df = pd.DataFrame(data)

    def color_path_found(val):
        color = 'background-color: #d4edda; color: #155724;' if val == '✅' else 'background-color: #f8d7da; color: #721c24;'
        return color

    def highlight_best_metric(col):
        if col.name == 'Path Length (m)':
            valid_values = []
            for x in col:
                try:
                    valid_values.append(float(x))
                except Exception:
                    pass
            if valid_values:
                min_val = min(valid_values)
                return ['background-color: #d1ecf1; color: #0c5460; font-weight: bold;'
                        if (isinstance(x, str) and x != 'N/A' and float(x) == min_val) or (isinstance(x, float) and x == min_val)
                        else '' for x in col]
        elif col.name == 'Efficiency (%)':
            valid_values = []
            for x in col:
                try:
                    valid_values.append(float(x))
                except Exception:
                    pass
            if valid_values:
                max_val = max(valid_values)
                return ['background-color: #d1ecf1; color: #0c5460; font-weight: bold;'
                        if (isinstance(x, str) and x != 'N/A' and float(x) == max_val) or (isinstance(x, float) and x == max_val)
                        else '' for x in col]
        return [''] * len(col)

    styled_df = df.style\
        .map(color_path_found, subset=['Path Found'])\
        .apply(highlight_best_metric, axis=0)\
        .set_properties(**{
            'background-color': '#f8f9fa',
            'color': '#212529',
            'border-color': '#dee2e6',
            'font-size': '14px'
        })\
        .set_table_styles([
            {'selector': 'thead th', 'props': [
                ('background-color', '#2c3e50'),
                ('color', 'white'),
                ('font-weight', 'bold'),
                ('text-align', 'center'),
                ('padding', '12px')
            ]},
            {'selector': 'tbody td', 'props': [
                ('padding', '10px'),
                ('text-align', 'center'),
                ('border', '1px solid #dee2e6')
            ]}
        ])

    st.markdown(styled_df.to_html(), unsafe_allow_html=True)

    # Algorithm insights
    st.subheader("🧠 Algorithm Insights")
    col1, col2 = st.columns(2)

    with col1:
        successful = [d for d in data if d['Path Found'] == '✅']
        if successful:
            try:
                best = min(successful, key=lambda x: float(x['Path Length (m)']))
                st.success(f"**🏆 Best Path:** {best['Algorithm']} found the shortest route ({best['Path Length (m)']}m)")
            except Exception:
                pass

        efficient = [d for d in data if d['Efficiency (%)'] != 'N/A']
        if efficient:
            most_efficient = max(efficient, key=lambda x: float(x['Efficiency (%)']))
            st.info(f"**⚡ Most Efficient:** {most_efficient['Algorithm']} had a search efficiency of {most_efficient['Efficiency (%)']}%")

    with col2:
        success_rate = len([d for d in data if d['Path Found'] == '✅']) / len(data) * 100
        st.metric("Success Rate", f"{success_rate:.0f}%")

        mode_name = current_network_type.capitalize()
        speed_kmh = current_speed * 3.6
        st.metric(f"{mode_name} Speed", f"{speed_kmh:.1f} km/h")

        flood_data = next((d for d in data if d['Algorithm'] == 'Flood Fill'), None)
        if flood_data:
            if flood_data['Path Found'] == '✅':
                st.info("**Flood Fill** explores all possible paths like water filling a container")
            else:
                st.error("**Flood Fill** couldn't reach the goal")


# Educational Content
with st.expander("🎓 Learn About Pathfinding Algorithms", expanded=False):
    st.markdown("""
    <style>
    .algorithm-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .algorithm-card h4 {
        color: white;
        margin-top: 0;
    }
    </style>

    <div class="algorithm-card">
    <h4>🚀 BFS (Breadth-First Search)</h4>
    <p><strong>Strategy:</strong> Explores all neighbors at current depth before moving deeper<br>
    <strong>Guarantees:</strong> Shortest path in unweighted graphs<br>
    <strong>Best for:</strong> Simple grids, small search spaces</p>
    </div>

    <div class="algorithm-card">
    <h4>🎯 A* Search</h4>
    <p><strong>Strategy:</strong> Uses heuristic to guide search toward goal<br>
    <strong>Guarantees:</strong> Optimal path with admissible heuristic<br>
    <strong>Best for:</strong> Geographical pathfinding, known goal locations</p>
    </div>

    <div class="algorithm-card">
    <h4>⚖️ Dijkstra's Algorithm</h4>
    <p><strong>Strategy:</strong> Explores all directions with priority on shortest cumulative distance<br>
    <strong>Guarantees:</strong> Shortest path in weighted graphs<br>
    <strong>Best for:</strong> Road networks with varying edge weights</p>
    </div>

    <div class="algorithm-card">
    <h4>💧 Flood Fill</h4>
    <p><strong>Strategy:</strong> Expands outward in all directions like water filling a container<br>
    <strong>Guarantees:</strong> Will find a path if one exists<br>
    <strong>Best for:</strong> Exploring all possible paths, finding all connected components</p>
    </div>
    """, unsafe_allow_html=True)


# Installation instructions
with st.sidebar.expander("🔧 Installation Help", expanded=False):
    st.markdown("""
    **For full functionality:**
    ```
    pip install osmnx networkx scikit-learn geopy shapely
    ```

    **Current Status:**
    - OSMnx: {'✅ Available' if OSMNX_AVAILABLE else '❌ Not Available'}
    - Real Map Data: {'✅ Enabled' if OSMNX_AVAILABLE and graph else '❌ Simulated'}
    """)


# Tips
with st.sidebar.expander("💡 Tips", expanded=False):
    st.markdown("""
    - If location names fail, try switching to "Coordinates" input.
    - You can find coordinates on Google Maps by right-clicking a location.
    - For better results, include the city name with the location.
    - The app now dynamically loads the map for your specific route.
    - **Efficiency %**: Higher is better. It's the percentage of explored nodes that were in the final path.
    - **Speed Settings**: Different speeds are used for walking (5 km/h), biking (15 km/h), and driving (50 km/h).
    """)

st.caption("🌍 Interactive map powered by Leaflet/Folium • Pathfinding algorithms comparison • Dynamic route loading")