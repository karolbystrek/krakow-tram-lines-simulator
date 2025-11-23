import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from typing import Dict, List

from .simulation.engine import SimulationEngine
from .simulation.loader import load_tram_stops, load_shapes_from_geojson
from .simulation.models import Stop, Shape
from .simulation.geojson_utils import stops_to_geojson, shapes_to_geojson

# Define the paths
APP_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = APP_DIR.parent.parent / "frontend"

app = FastAPI()

# Global simulation engine instance
simulation_engine = SimulationEngine()

# Load static data once at startup
@app.on_event("startup")
async def startup_event():
    print("Loading tram stops and shapes...")
    app.state.tram_stops: Dict[str, Stop] = load_tram_stops()
    app.state.tram_shapes: Dict[str, List[Shape]] = load_shapes_from_geojson()
    print(f"Loaded {len(app.state.tram_stops)} tram stops.")
    print(f"Loaded {len(app.state.tram_shapes)} tram line shapes.")
    
    # Start the simulation
    await simulation_engine.start()


@app.on_event("shutdown")
async def shutdown_event():
    await simulation_engine.stop()


# 1. Serve the frontend application
@app.get("/")
async def get_index():
    """Serves the main index.html file."""
    return FileResponse(FRONTEND_DIR / "index.html")


# Mount the static directory to serve app.js and style.css
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# 2. API endpoints to serve static data (one-time load)
@app.get("/api/stops")
async def get_stops_data():
    """
    Serves the tram stops data as GeoJSON FeatureCollection.
    Each stop is represented as a Point feature.
    """
    geojson_data = stops_to_geojson(app.state.tram_stops)
    return JSONResponse(content=geojson_data)


@app.get("/api/routes")
async def get_routes_data():
    """
    Serves the tram line shapes data as GeoJSON FeatureCollection.
    Each line shape is represented as a LineString feature.
    """
    geojson_data = shapes_to_geojson(app.state.tram_shapes)
    return JSONResponse(content=geojson_data)


# 3. The WebSocket endpoint for real-time simulation
@app.websocket("/ws/simulation")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected to WebSocket.")

    async def send_updates():
        try:
            while True:
                # Get current state from the engine
                status = simulation_engine.get_status()
                trams = simulation_engine.get_tram_positions()
                
                payload = {
                    "time": status,
                    "trams": trams,
                    "status": "paused" if simulation_engine.paused else "running"
                }
                
                # Send the current simulation state to the client
                await websocket.send_json(payload)

                # Send updates every second (matching the simulation step)
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Error in send_updates: {e}")

    async def receive_commands():
        try:
            while True:
                data = await websocket.receive_json()
                command = data.get("command")
                print(f"Received command: {command}")
                
                if command == "pause":
                    simulation_engine.pause()
                elif command == "resume":
                    simulation_engine.resume()
                elif command == "restart":
                    simulation_engine.restart()
        except WebSocketDisconnect:
            print("Client disconnected (receive_commands).")
        except Exception as e:
            print(f"Error in receive_commands: {e}")

    try:
        # Run both tasks concurrently
        sender_task = asyncio.create_task(send_updates())
        receiver_task = asyncio.create_task(receive_commands())
        
        # Wait for either to finish (likely receiver_task on disconnect)
        done, pending = await asyncio.wait(
            [sender_task, receiver_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        for task in pending:
            task.cancel()
            
    except Exception as e:
        print(f"An error occurred in websocket handler: {e}")
    finally:
        print("Closing WebSocket connection.")
