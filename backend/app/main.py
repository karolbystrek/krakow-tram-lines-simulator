import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .simulation.engine import SimulationEngine
from .simulation.geojson_utils import stops_to_geojson, shapes_to_geojson
from .simulation.loader import (
    load_tram_stops,
    load_shapes_from_geojson,
    get_service_for_weekday,
)
from .simulation.models import Stop, Shape

APP_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = APP_DIR.parent.parent / "frontend"

app = FastAPI()

current_weekday = datetime.now().weekday()
default_service_id = get_service_for_weekday(current_weekday)
print(f"Current weekday index: {current_weekday}, Default service: {default_service_id}")

simulation_engine = SimulationEngine(service_id=default_service_id)


@app.on_event("startup")
async def startup_event():
    print("Loading tram shapes...")
    app.state.tram_shapes: Dict[str, List[Shape]] = load_shapes_from_geojson()
    print(f"Loaded {len(app.state.tram_shapes)} tram line shapes.")

    # simulation_engine already loaded default service and its stops in __init__
    app.state.tram_stops = getattr(simulation_engine, "_cached_stops", {})
    print(f"Initialized with {len(app.state.tram_stops)} tram stops for current service.")

    await simulation_engine.start()


@app.on_event("shutdown")
async def shutdown_event():
    await simulation_engine.stop()


@app.get("/")
async def get_index():
    """Serves the main index.html file."""
    return FileResponse(FRONTEND_DIR / "public" / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "src"), name="static")


@app.get("/api/stops")
async def get_stops_data():
    """Serves the tram stops data as GeoJSON FeatureCollection."""
    stops = getattr(simulation_engine, "_cached_stops", app.state.tram_stops)
    geojson_data = stops_to_geojson(stops)
    return JSONResponse(content=geojson_data)


@app.get("/api/routes")
async def get_routes_data():
    """Serves the tram line shapes data as GeoJSON FeatureCollection."""
    geojson_data = shapes_to_geojson(app.state.tram_shapes)
    return JSONResponse(content=geojson_data)


@app.get("/api/simulation/weights")
async def get_stop_weights():
    """Get current stop weights with names."""
    if not simulation_engine.arrival_model:
        return JSONResponse(content=[])

    weights = simulation_engine.arrival_model.stop_weights
    result = []

    for stop_id, weight in weights.items():
        name = stop_id
        if stop_id in simulation_engine.stop_states:
            name = simulation_engine.stop_states[stop_id].name

        result.append({"id": stop_id, "name": name, "weight": weight})

    return JSONResponse(content=result)


@app.post("/api/simulation/weights")
async def update_stop_weights(weights: Dict[str, float] = Body(...)):
    """Update stop weights."""
    if simulation_engine.arrival_model:
        for stop_id, weight in weights.items():
            simulation_engine.arrival_model.set_stop_weight(stop_id, weight)
            simulation_engine.arrival_model.update_weight_config(stop_id, weight)

        simulation_engine.arrival_model.save_weights()
        return JSONResponse(content={"status": "updated", "count": len(weights)})
    return JSONResponse(
        content={"status": "error", "message": "Engine not ready"}, status_code=500
    )


@app.get("/api/simulation/stats/detailed")
async def get_detailed_stats():
    """Get detailed statistics including top stops."""
    stats = simulation_engine.get_statistics()

    stop_stats = []
    if simulation_engine.stop_states:
        for stop_state in simulation_engine.stop_states.values():
            stop_stats.append(
                {
                    "id": stop_state.stop_id,
                    "name": stop_state.name,
                    "boarded": stop_state.total_boarded,
                    "alighted": stop_state.total_alighted,
                    "arrived": stop_state.total_arrived,
                }
            )

    top_stops = sorted(stop_stats, key=lambda x: x["boarded"], reverse=True)

    response_data = {"global": stats, "top_stops": top_stops}
    return JSONResponse(content=response_data)


@app.websocket("/ws/simulation")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected to WebSocket.")

    async def send_updates():
        try:
            was_running = False
            while True:
                status = simulation_engine.get_status()
                trams = simulation_engine.get_tram_positions()
                stop_states_raw = simulation_engine.get_stop_states()

                stop_states = {}
                for stop_id, state_data in stop_states_raw.items():
                    if stop_id in app.state.tram_stops:
                        stop_states[stop_id] = state_data
                    else:
                        stop_states[stop_id] = state_data
                        for kod_busman, stop in app.state.tram_stops.items():
                            if stop.kod_busman == stop_id or str(stop.id) == stop_id:
                                stop_states[kod_busman] = state_data
                                break

                total_waiting = sum(s["waiting_count"] for s in stop_states.values())
                total_on_trams = sum(t.get("occupancy", 0) for t in trams)

                payload = {
                    "time": status,
                    "trams": trams,
                    "status": "paused" if simulation_engine.paused else "running",
                    "service_id": simulation_engine.service_id,
                    "passengers": {
                        "total_waiting": total_waiting,
                        "total_on_trams": total_on_trams,
                    },
                    "stop_states": stop_states,
                }

                await websocket.send_json(payload)

                if (
                    was_running
                    and not simulation_engine.running
                    and not simulation_engine.paused
                ):
                    print("Simulation finished detected in WS loop. Sending statistics.")
                    stats = simulation_engine.get_statistics()
                    await websocket.send_json(
                        {"type": "simulation_ended", "statistics": stats}
                    )
                    was_running = False

                if simulation_engine.running:
                    was_running = True

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
                        await websocket.send_json(
                            {"type": "service_changed", "service_id": service_id}
                        )
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
                    await websocket.send_json(
                        {"type": "statistics_update", "statistics": stats}
                    )
                elif command == "update_generation_params":
                    params = data.get("params")
                    if params:
                        simulation_engine.update_generation_params(params)
                elif command == "get_generation_params":
                    params = simulation_engine.get_generation_params()
                    await websocket.send_json(
                        {"type": "generation_params", "params": params}
                    )
                elif command == "save_generation_params":
                    simulation_engine.save_generation_params()
        except WebSocketDisconnect:
            print("Client disconnected (receive_commands).")
        except Exception as e:
            print(f"Error in receive_commands: {e}")

    try:
        sender_task = asyncio.create_task(send_updates())
        receiver_task = asyncio.create_task(receive_commands())

        done, pending = await asyncio.wait(
            [sender_task, receiver_task], return_when=asyncio.FIRST_COMPLETED
        )

        for task in pending:
            task.cancel()

    except Exception as e:
        print(f"An error occurred in websocket handler: {e}")
    finally:
        print("Closing WebSocket connection.")
