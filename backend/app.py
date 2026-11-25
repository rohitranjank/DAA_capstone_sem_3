from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import json, os, time, csv, random, io
from datetime import datetime

app = Flask(__name__)
CORS(app)
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
REPORT_DIR = os.path.join(ROOT, "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

def read_json(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)

def merge_sort(items):
    if len(items) <= 1:
        return items[:]
    mid = len(items)//2
    left, right = merge_sort(items[:mid]), merge_sort(items[mid:])
    out, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        a = (-left[i]["priority"], left[i]["deadline"])
        b = (-right[j]["priority"], right[j]["deadline"])
        if a <= b:
            out.append(left[i]); i += 1
        else:
            out.append(right[j]); j += 1
    return out + left[i:] + right[j:]

def knapsack(items, capacity):
    n = len(items)
    dp = [[0]*(capacity+1) for _ in range(n+1)]
    for i in range(1, n+1):
        wt, val = items[i-1]["weight"], items[i-1]["value"]
        for w in range(capacity+1):
            dp[i][w] = max(val + dp[i-1][w-wt], dp[i-1][w]) if wt <= w else dp[i-1][w]
    chosen, w = [], capacity
    for i in range(n, 0, -1):
        if dp[i][w] != dp[i-1][w]:
            chosen.append(items[i-1]); w -= items[i-1]["weight"]
    chosen.reverse()
    ids = {p["id"] for p in chosen}
    weight = sum(p["weight"] for p in chosen)
    return {"selected": chosen, "rejected": [p for p in items if p["id"] not in ids],
            "total_weight": weight, "total_value": sum(p["value"] for p in chosen),
            "remaining_capacity": capacity-weight, "dp_table": dp}

def build_graph(data):
    graph = {x: [] for x in data["locations"]}
    for u, v, wt in data["edges"]:
        graph[u].append((v, wt)); graph[v].append((u, wt))
    return graph

def dijkstra(graph, source):
    import heapq
    dist = {v: float("inf") for v in graph}
    parent = {v: None for v in graph}
    dist[source] = 0
    pq = [(0, source)]
    while pq:
        d, u = heapq.heappop(pq)
        if d != dist[u]: continue
        for v, wt in graph[u]:
            nd = d + wt
            if nd < dist[v]:
                dist[v], parent[v] = nd, u
                heapq.heappush(pq, (nd, v))
    return dist, parent

def path_for(parent, source, dest):
    path, cur = [], dest
    while cur is not None:
        path.append(cur); cur = parent[cur]
    path.reverse()
    return path if path and path[0] == source else []

def nearest_neighbor(start, destinations, matrix):
    remaining = set(destinations); remaining.discard(start)
    route, total, cur = [start], 0, start
    while remaining:
        nxt = min(remaining, key=lambda x: matrix[cur][x])
        if matrix[cur][nxt] == float("inf"):
            raise ValueError("A destination is unreachable.")
        total += matrix[cur][nxt]; route.append(nxt)
        remaining.remove(nxt); cur = nxt
    if matrix[cur][start] == float("inf"):
        raise ValueError("Cannot return to warehouse.")
    total += matrix[cur][start]; route.append(start)
    return route, total

def route_plan(selected, graph):
    destinations = list(dict.fromkeys(p["destination"] for p in selected))
    points = ["W"] + destinations
    matrix, paths = {}, {}
    for src in points:
        dist, parent = dijkstra(graph, src)
        matrix[src] = {dst: dist[dst] for dst in points}
        paths[src] = {dst: path_for(parent, src, dst) for dst in points}
    route, distance = nearest_neighbor("W", points, matrix)
    legs = []
    for a, b in zip(route, route[1:]):
        legs.append({"from": a, "to": b, "path": paths[a][b], "distance": matrix[a][b]})
    return {"route": route, "total_distance": distance, "legs": legs, "destinations": destinations}

@app.get("/api/initial")
def initial():
    return jsonify({"parcels": read_json("parcels.json"), "map": read_json("locations.json")})

@app.get("/api/sort")
def sort_api():
    parcels = read_json("parcels.json")
    start = time.perf_counter(); result = merge_sort(parcels); elapsed = time.perf_counter()-start
    return jsonify({"parcels": result, "seconds": elapsed})

@app.post("/api/knapsack")
def knapsack_api():
    body = request.get_json(silent=True) or {}
    capacity = int(body.get("capacity", 15))
    if capacity < 1 or capacity > 10000:
        return jsonify({"error": "Capacity must be between 1 and 10000 kg."}), 400
    return jsonify(knapsack(read_json("parcels.json"), capacity))

@app.get("/api/graph")
def graph_api():
    data = read_json("locations.json")
    graph = build_graph(data)
    return jsonify({"locations": data["locations"], "edges": data["edges"],
                    "adjacency": {k: [{"to": v, "distance": w} for v,w in vals] for k,vals in graph.items()}})

@app.post("/api/shortest-path")
def shortest_api():
    body = request.get_json() or {}
    src, dst = body.get("source"), body.get("destination")
    graph = build_graph(read_json("locations.json"))
    if src not in graph or dst not in graph:
        return jsonify({"error": "Select valid locations."}), 400
    start = time.perf_counter(); dist, parent = dijkstra(graph, src); elapsed = time.perf_counter()-start
    path = path_for(parent, src, dst)
    return jsonify({"source": src, "destination": dst, "path": path,
                    "distance": dist[dst] if path else None, "seconds": elapsed})

@app.post("/api/route")
def route_api():
    body = request.get_json(silent=True) or {}
    capacity = int(body.get("capacity", 15))
    if capacity < 1 or capacity > 10000:
        return jsonify({"error": "Capacity must be between 1 and 10000 kg."}), 400
    parcels = read_json("parcels.json")
    packed = knapsack(parcels, capacity)
    graph = build_graph(read_json("locations.json"))
    start = time.perf_counter()
    try:
        route = route_plan(packed["selected"], graph)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    route["packing"] = {k: packed[k] for k in ("selected","rejected","total_weight","total_value","remaining_capacity")}
    route["seconds"] = time.perf_counter()-start
    return jsonify(route)

@app.get("/api/report")
def report_api():
    capacity = int(request.args.get("capacity", 15))
    parcels = read_json("parcels.json")
    packed = knapsack(parcels, capacity)
    route = route_plan(packed["selected"], build_graph(read_json("locations.json")))
    lines = [
        "INTELLIGENT COURIER PLANNING AND OPTIMIZATION SYSTEM",
        "DELIVERY REPORT",
        f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}",
        "",
        f"Vehicle capacity: {capacity} kg",
        f"Loaded weight: {packed['total_weight']} kg",
        f"Remaining capacity: {packed['remaining_capacity']} kg",
        f"Total parcel value: {packed['total_value']}",
        "", "SELECTED PARCELS"
    ]
    lines += [f"{p['id']} | {p['weight']} kg | value {p['value']} | destination {p['destination']}" for p in packed["selected"]]
    lines += ["", "REJECTED PARCELS"]
    lines += [f"{p['id']} | {p['weight']} kg | value {p['value']}" for p in packed["rejected"]]
    lines += ["", "DELIVERY ROUTE", " -> ".join(route["route"]), f"Total distance: {route['total_distance']} km", "", "ROUTE LEGS"]
    lines += [f"{x['from']} -> {x['to']}: {' -> '.join(x['path'])} ({x['distance']} km)" for x in route["legs"]]
    content = "\n".join(lines)
    path = os.path.join(REPORT_DIR, "delivery_report.txt")
    with open(path, "w", encoding="utf-8") as f: f.write(content)
    return send_file(path, as_attachment=True, download_name="delivery_report.txt", mimetype="text/plain")

@app.get("/api/benchmark")
def benchmark_api():
    # Lightweight repeatable demonstration benchmark of implemented algorithms.
    sizes, rows = [10, 50, 100, 200], []
    for n in sizes:
        items = [{"id":str(i),"weight":random.randint(1,10),"value":random.randint(10,100),
                  "priority":random.randint(1,3),"deadline":f"{random.randint(8,18):02d}:00"} for i in range(n)]
        t=time.perf_counter(); merge_sort(items); merge_t=time.perf_counter()-t
        cap=max(15,n*5)
        t=time.perf_counter(); knapsack(items,cap); knap_t=time.perf_counter()-t
        graph_data=read_json("locations.json"); graph=build_graph(graph_data)
        t=time.perf_counter(); dijkstra(graph,"W"); dij_t=time.perf_counter()-t
        rows.append({"input_size":n,"merge_sort_seconds":merge_t,"knapsack_seconds":knap_t,"dijkstra_seconds":dij_t})
    os.makedirs(REPORT_DIR,exist_ok=True)
    with open(os.path.join(REPORT_DIR,"performance_results.csv"),"w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0].keys())); writer.writeheader(); writer.writerows(rows)
    return jsonify({"results":rows,"message":"Benchmark completed. CSV saved in backend/reports/."})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
