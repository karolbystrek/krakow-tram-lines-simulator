import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from typing import Dict, List

from datetime import datetime
from .simulation.engine import SimulationEngine
from .simulation.loader import load_tram_stops, load_shapes_from_geojson, get_service_for_weekday
from .simulation.models import Stop, Shape
from .simulation.geojson_utils import stops_to_geojson, shapes_to_geojson

# Define the paths
APP_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = APP_DIR.parent.parent / "frontend"

app = FastAPI()

# Global simulation engine instance
# Determine default service based on current weekday
current_weekday = datetime.now().weekday()
default_service_id = get_service_for_weekday(current_weekday)
print(f"Current weekday index: {current_weekday}, Default service: {default_service_id}")

simulation_engine = SimulationEngine(service_id=default_service_id)

# Load static data once at startup
@app.on_event("startup")
async def startup_event():
    print("Loading tram stops and shapes...")
    app.state.tram_stops: Dict[str, Stop] = load_tram_stops()
    app.state.tram_shapes: Dict[str, List[Shape]] = load_shapes_from_geojson()
    print(f"Loaded {len(app.state.tram_stops)} tram stops.")
    print(f"Loaded {len(app.state.tram_shapes)} tram line shapes.")
    
    # Cache stops in engine to avoid reloading
    simulation_engine._cached_stops = app.state.tram_stops
    
    # Start the simulation
    await simulation_engine.start()


@app.on_event("shutdown")
async def shutdown_event():
    await simulation_engine.stop()


# 1. Serve the frontend application
@app.get("/")
async def get_index():
    """Serves the main index.html file."""
    return FileResponse(FRONTEND_DIR / "public" / "index.html")


@app.get("/favicon.ico")
async def get_favicon():
    """Serves the favicon."""
    return FileResponse(FRONTEND_DIR / "public" / "favicon.ico")


# Mount the static directory to serve app.js and style.css
app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "src"), name="static")


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
            was_running = False
            while True:
                # Get current state from the engine
                status = simulation_engine.get_status()
                trams = simulation_engine.get_tram_positions()
                stop_states_raw = simulation_engine.get_stop_states()
                
                # Map stop_states: prioritize kod_busman for frontend compatibility
                # Create mapping from stop_num to kod_busman if possible
                stop_states = {}
                for stop_id, state_data in stop_states_raw.items():
                    # If stop_id is already a kod_busman from loaded stops, use it
                    if stop_id in app.state.tram_stops:
                        stop_states[stop_id] = state_data
                    else:
                        # Try to find matching kod_busman by checking if stop_id matches any stop's kod_busman
                        # or if we need to map stop_num to kod_busman
                        # For now, include by stop_id as well for compatibility
                        stop_states[stop_id] = state_data
                        
                        # Also try to find kod_busman match by searching stops
                        for kod_busman, stop in app.state.tram_stops.items():
                            if stop.kod_busman == stop_id or str(stop.id) == stop_id:
                                stop_states[kod_busman] = state_data
                                break
                
                # Calculate passenger totals
                total_waiting = sum(s["waiting_count"] for s in stop_states.values())
                total_on_trams = sum(t.get("occupancy", 0) for t in trams)
                
                payload = {
                    "time": status,
                    "trams": trams,
                    "status": "paused" if simulation_engine.paused else "running",
                    "service_id": simulation_engine.service_id,
                    "passengers": {
                        "total_waiting": total_waiting,
                        "total_on_trams": total_on_trams
                    },
                    "stop_states": stop_states
                }
                
                # Send the current simulation state to the client
                await websocket.send_json(payload)
                
                # Check if simulation just finished (natural end)
                # If running is False but was previously True (we can track this via simulation_engine state)
                # However, sending stats on every frame when stopped is wasteful but safe if handled by frontend
                # Better: Send a specific event when simulation finishes
                
                # Note: simulation_engine.running becomes False when it hits end time
                if was_running and not simulation_engine.running and not simulation_engine.paused:
                   print("Simulation finished detected in WS loop. Sending statistics.")
                   stats = simulation_engine.get_statistics()
                   await websocket.send_json({
                       "type": "simulation_ended",
                       "statistics": stats
                   })
                   # Reset flag to avoid sending multiple times
                   was_running = False
                
                # Update running state tracker
                if simulation_engine.running:
                    was_running = True

                # Send updates every 0.1 second (matching the simulation step)
                await asyncio.sleep(0.1)
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
                elif command == "change_service":
                    service_id = data.get("service_id")
                    if service_id:
                        await simulation_engine.reload_service(service_id)
                        # Send confirmation or let the next update reflect the change
                        await websocket.send_json({"type": "service_changed", "service_id": service_id})
                elif command == "set_time":
                    time_minutes = data.get("time")
                    if time_minutes is not None:
                        simulation_engine.set_time(float(time_minutes))
                elif command == "set_speed":
                    speed = data.get("speed")
                    if speed is not None:
                        simulation_engine.set_speed(float(speed))
                elif command == "get_statistics":
                    stats = simulation_engine.get_statistics()
                    await websocket.send_json({
                        "type": "statistics_update",
                        "statistics": stats
                    })
                elif command == "update_generation_params":
                    params = data.get("params")
                    if params:
                        simulation_engine.update_generation_params(params)
                elif command == "get_generation_params":
                    params = simulation_engine.get_generation_params()
                    await websocket.send_json({
                        "type": "generation_params",
                        "params": params
                    })
                elif command == "save_generation_params":
                    simulation_engine.save_generation_params()
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
