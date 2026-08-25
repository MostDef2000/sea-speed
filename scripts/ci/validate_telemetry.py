#!/usr/bin/env python3
"""Validate Sea Speed state or vehicle-event telemetry without external packages."""
from __future__ import annotations
import argparse,json,re,sys
from pathlib import Path
from typing import Any
SHA_RE=re.compile(r"^[0-9a-f]{40}$"); CALIBRATION_RE=re.compile(r"^sha256:[0-9a-f]{16}$")
PROFILES={"water-v1":("water","cam1"),"road-v1":("road","road1")}
def fail(message:str)->None: raise ValueError(message)
def validate_commit(value:Any)->None:
    if value is None or value=="unknown": return
    if not isinstance(value,str) or not SHA_RE.fullmatch(value): fail("worker_source_commit must be a lowercase full Git SHA, unknown, or null")
def validate_profile(payload:dict[str,Any], *, required:bool=False)->None:
    profile=payload.get("analytics_profile")
    if profile is None and not required: return
    if profile not in PROFILES: fail("analytics_profile must be water-v1 or road-v1")
    domain,camera=PROFILES[profile]
    if payload.get("domain")!=domain: fail("domain does not match analytics_profile")
    if payload.get("camera_id")!=camera: fail("camera_id does not match analytics_profile")
def validate_state(payload):
    if payload.get("state_schema")!="sea_speed_worker_state_v1": fail("invalid state_schema")
    if payload.get("telemetry_schema")!="sea_speed_telemetry_v1": fail("invalid telemetry_schema")
    validate_commit(payload.get("worker_source_commit"))
    if not isinstance(payload.get("camera_id"),str) or not payload["camera_id"]: fail("camera_id is required")
    frame=payload.get("frame_no")
    if not isinstance(frame,int) or isinstance(frame,bool) or frame<0: fail("frame_no must be a non-negative integer")
    if not isinstance(payload.get("worker_online"),bool): fail("worker_online must be boolean")
    updated=payload.get("updated_at")
    if updated is not None and not isinstance(updated,str): fail("updated_at must be a string or null")
    validate_profile(payload)
def validate_event(payload):
    if payload.get("event_schema")!="sea_speed_vehicle_event_v1": fail("invalid event_schema")
    if payload.get("telemetry_schema")!="sea_speed_telemetry_v1": fail("invalid telemetry_schema")
    validate_commit(payload.get("worker_source_commit")); calibration=payload.get("calibration_version")
    if calibration is not None and (not isinstance(calibration,str) or not CALIBRATION_RE.fullmatch(calibration)): fail("calibration_version must be sha256:<16 hex> or null")
    for field in ("event_id","created_at","camera_id","class_name"):
        if not isinstance(payload.get(field),str) or not payload[field]: fail(f"{field} is required")
    confidence=payload.get("confidence")
    if not isinstance(confidence,(int,float)) or isinstance(confidence,bool) or not 0<=confidence<=1: fail("confidence must be between 0 and 1")
    speed=payload.get("speed_kmh")
    if speed is not None and (not isinstance(speed,(int,float)) or isinstance(speed,bool) or speed<0): fail("speed_kmh must be non-negative or null")
    if "analytics_profile" in payload:
        validate_profile(payload,required=True)
        for field in ("object_type","model_class"):
            if not isinstance(payload.get(field),str) or not payload[field]: fail(f"{field} is required for profiled events")
        if payload.get("class_name")!=payload.get("object_type"): fail("class_name must equal canonical object_type")
        if payload["analytics_profile"]=="water-v1" and (payload["object_type"]!="vessel" or payload["model_class"]!="boat"): fail("water-v1 event must normalize boat to vessel")
        if payload["analytics_profile"]=="road-v1" and payload["model_class"] not in {"car","truck","bus","motorcycle","bicycle"}: fail("road-v1 event model_class is not allowed")
def validate_road_live(payload):
    schema = payload.get("schema")
    if schema not in {"sea_speed_road_live_v1", "sea_speed_road_live_v2"}:
        fail("schema must be sea_speed_road_live_v1/v2")
    if payload.get("camera_id") != "road1":
        fail("camera_id must be road1")
    if payload.get("analytics_profile") != "road-v1":
        fail("analytics_profile must be road-v1")
    if payload.get("domain") != "road":
        fail("domain must be road")
    for field in ("frame_no", "generation", "frame_width", "frame_height"):
        if not isinstance(payload.get(field), int) or isinstance(payload.get(field), bool) or payload[field] < 0:
            fail(f"{field} must be non-negative int")
    if schema == "sea_speed_road_live_v2":
        for field in ("capture_time_unix_ms", "processed_time_unix_ms"):
            if not isinstance(payload.get(field), int) or payload[field] < 0:
                fail(f"{field} must be non-negative int")
        if payload.get("timestamp_semantics") != "worker_receive_utc":
            fail("timestamp_semantics must be worker_receive_utc")
    detections = payload.get("detections")
    if not isinstance(detections, list) or len(detections) > 64:
        fail("detections must be list max 64")
    for det in detections:
        if not isinstance(det, dict):
            fail("detection must be object")
        for coord in ("x1_norm", "y1_norm", "x2_norm", "y2_norm"):
            v = det.get(coord)
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not 0 <= float(v) <= 1:
                fail(f"{coord} must be 0..1")
        if float(det.get("x2_norm")) <= float(det.get("x1_norm")) or float(det.get("y2_norm")) <= float(det.get("y1_norm")):
            fail("invalid box")
    validate_commit(payload.get("worker_source_commit"))

def validate_water_live(payload):
    schema = payload.get("schema")
    if schema not in {"sea_speed_water_live_v1", "sea_speed_water_live_v2"}:
        fail("schema must be sea_speed_water_live_v1/v2")
    if payload.get("camera_id") != "cam1":
        fail("camera_id must be cam1")
    if payload.get("analytics_profile") != "water-v1":
        fail("analytics_profile must be water-v1")
    if payload.get("domain") != "water":
        fail("domain must be water")
    for field in ("frame_no", "generation", "frame_width", "frame_height"):
        if not isinstance(payload.get(field), int) or isinstance(payload.get(field), bool) or payload[field] < 0:
            fail(f"{field} must be non-negative int")
    if schema == "sea_speed_water_live_v2":
        for field in ("capture_time_unix_ms", "processed_time_unix_ms"):
            if not isinstance(payload.get(field), int) or payload[field] < 0:
                fail(f"{field} must be non-negative int")
        if payload.get("timestamp_semantics") != "worker_receive_utc":
            fail("timestamp_semantics must be worker_receive_utc")
    detections = payload.get("detections")
    if not isinstance(detections, list) or len(detections) > 64:
        fail("detections must be list max 64")
    for det in detections:
        if not isinstance(det, dict):
            fail("detection must be object")
        for coord in ("x1_norm", "y1_norm", "x2_norm", "y2_norm"):
            v = det.get(coord)
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not 0 <= float(v) <= 1:
                fail(f"{coord} must be 0..1")
        if float(det.get("x2_norm")) <= float(det.get("x1_norm")) or float(det.get("y2_norm")) <= float(det.get("y1_norm")):
            fail("invalid box")
    validate_commit(payload.get("worker_source_commit"))

def validate_payload(payload,kind="auto"):
    resolved=kind
    if resolved=="auto":
        if "state_schema" in payload: resolved="state"
        elif "event_schema" in payload: resolved="event"
        elif payload.get("schema") in {"sea_speed_road_live_v1", "sea_speed_road_live_v2"}: resolved="road_live"
        elif payload.get("schema") in {"sea_speed_water_live_v1", "sea_speed_water_live_v2"}: resolved="water_live"
        else: fail("cannot infer telemetry kind")
    if resolved=="state": validate_state(payload)
    elif resolved=="event": validate_event(payload)
    elif resolved=="road_live": validate_road_live(payload)
    elif resolved=="water_live": validate_water_live(payload)
    else: fail(f"unsupported telemetry kind: {resolved}")
    return resolved
def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("payload",type=Path); p.add_argument("--kind",choices=("auto","state","event","road_live","water_live"),default="auto"); a=p.parse_args()
    try:
        payload=json.loads(a.payload.read_text(encoding="utf-8"));
        if not isinstance(payload,dict): fail("payload root must be an object")
        kind=validate_payload(payload,a.kind)
    except (OSError,json.JSONDecodeError,ValueError) as exc: print(f"ERROR: {exc}",file=sys.stderr); return 1
    print(f"Sea Speed {kind} telemetry valid: {a.payload}"); return 0
if __name__=="__main__": raise SystemExit(main())
