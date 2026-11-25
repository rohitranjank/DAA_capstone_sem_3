# Intelligent Courier Planning and Optimization — Web Prototype

A React + Flask web application implementing the same courier-planning project: Merge Sort, 0/1 Knapsack, Dijkstra shortest paths, Nearest Neighbor TSP, benchmarking and downloadable delivery report.

## Requirements
- Python 3.10+
- Node.js 18+ and npm

## Run on Windows

### 1. Start backend (Terminal 1)
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```
Backend: http://127.0.0.1:5000

### 2. Start frontend (Terminal 2)
```powershell
cd frontend
npm install
npm run dev
```
Open the local URL printed by Vite (usually http://localhost:5173).

Keep both terminals running while using the application.

## Features
- Dashboard overview
- Merge Sort parcel prioritization
- 0/1 Knapsack package selection with DP table
- Weighted delivery network and Dijkstra path lookup
- Nearest Neighbor TSP delivery route
- Downloadable delivery report
- Basic algorithm benchmarking and CSV output

## Notes
- Sample data is stored in `backend/data/`.
- The sample vehicle capacity defaults to 15 kg and can be changed in the interface.
- TSP uses Nearest Neighbor, a heuristic; it does not guarantee the globally optimal tour.
- Benchmark timings vary by computer. The benchmark Dijkstra test uses the supplied sample graph.
