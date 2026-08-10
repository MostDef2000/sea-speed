#!/usr/bin/env python3
"""Render narrowly-scoped MediaMTX configuration candidates safely."""
from __future__ import annotations
import argparse, hashlib, ipaddress, json, os, re, stat, sys
from pathlib import Path
from urllib.parse import urlsplit
RFC1918_NETWORKS = tuple(ipaddress.ip_network(v) for v in ("10.0.0.0/8","172.16.0.0/12","192.168.0.0/16"))
READER_MARKER = "# Sea Speed least-privilege reader for canonical cam1"
class ConfigError(ValueError): pass

def _split_lines(text): return text.splitlines(keepends=True)
def _ensure_newline(line): return line if line.endswith("\n") else line+"\n"
def _yaml_string(value): return json.dumps(value, ensure_ascii=False)
def _is_rfc1918_ipv4(address): return address.version == 4 and any(address in n for n in RFC1918_NETWORKS)
def _find_top_level(lines,key):
    p=re.compile(rf"^{re.escape(key)}\s*:")
    return [i for i,l in enumerate(lines) if p.match(l)]
def _top_level_bounds(lines,key):
    m=_find_top_level(lines,key)
    if len(m)!=1: raise ConfigError(f"MediaMTX config must contain exactly one top-level {key} block")
    start=m[0]; end=len(lines)
    for i in range(start+1,len(lines)):
        line=lines[i]; stripped=line.strip()
        if not stripped or line.lstrip().startswith("#"): continue
        if line[0] not in " \t": end=i; break
    return start,end

def get_top_level_scalar(text,key):
    lines=_split_lines(text); m=_find_top_level(lines,key)
    if len(m)>1: raise ConfigError(f"duplicate top-level MediaMTX key: {key}")
    if not m: return None
    raw=lines[m[0]].split(":",1)[1].strip()
    if not raw or raw.startswith("#"): return ""
    raw=raw.split(" #",1)[0].strip()
    if raw.startswith('"'):
        try: return str(json.loads(raw))
        except json.JSONDecodeError as exc: raise ConfigError(f"invalid quoted top-level field: {key}") from exc
    return raw

def set_top_level_scalar(text,key,value,*,quote):
    lines=_split_lines(text); m=_find_top_level(lines,key)
    if len(m)>1: raise ConfigError(f"duplicate top-level MediaMTX key: {key}")
    rendered=f"{key}: {_yaml_string(value) if quote else value}\n"
    if m: lines[m[0]]=rendered; return "".join(lines)
    paths=_find_top_level(lines,"paths")
    if len(paths)!=1: raise ConfigError("MediaMTX config must contain exactly one top-level paths block")
    lines.insert(paths[0],rendered); return "".join(lines)

def _paths_bounds(lines): return _top_level_bounds(lines,"paths")
def _path_ranges(lines,ps,pe):
    h=re.compile(r"^  ([^#\s][^:]*):\s*(?:#.*)?(?:\n)?$"); starts=[]
    for i in range(ps+1,pe):
        m=h.match(lines[i])
        if m:
            name=m.group(1).strip()
            if name in {n for n,_ in starts}: raise ConfigError(f"duplicate MediaMTX path: {name}")
            starts.append((name,i))
    return {name:(start, starts[pos+1][1] if pos+1<len(starts) else pe) for pos,(name,start) in enumerate(starts)}
def set_path_source(text,path_name,source,*,source_on_demand=True):
    if not re.fullmatch(r"[A-Za-z0-9._-]+",path_name): raise ConfigError("MediaMTX path name must be a simple literal name")
    lines=_split_lines(text); ps,pe=_paths_bounds(lines); ranges=_path_ranges(lines,ps,pe)
    source_line=f"    source: {_yaml_string(source)}\n"; demand_line=f"    sourceOnDemand: {'yes' if source_on_demand else 'no'}\n"; fr=re.compile(r"^    (source|sourceOnDemand)\s*:")
    if path_name in ranges:
        start,end=ranges[path_name]; kept=[l for l in lines[start+1:end] if not fr.match(l)]; lines[start:end]=[_ensure_newline(lines[start]),source_line,demand_line,*kept]; return "".join(lines)
    block=[f"  {path_name}:\n",source_line,demand_line]
    if pe>0 and lines[pe-1].strip(): block.insert(0,"\n")
    lines[pe:pe]=block; return "".join(lines)
def remove_path(text,path_name):
    lines=_split_lines(text); ps,pe=_paths_bounds(lines); ranges=_path_ranges(lines,ps,pe)
    if path_name not in ranges: raise ConfigError(f"MediaMTX path is not present: {path_name}")
    start,end=ranges[path_name]; del lines[start:end]; return "".join(lines)
def get_path_field(text,path_name,field):
    lines=_split_lines(text); ps,pe=_paths_bounds(lines); ranges=_path_ranges(lines,ps,pe)
    if path_name not in ranges: return None
    start,end=ranges[path_name]; p=re.compile(rf"^    {re.escape(field)}\s*:\s*(.*?)\s*(?:\n)?$"); found=[]
    for line in lines[start+1:end]:
        m=p.match(line)
        if m: found.append(m.group(1).strip())
    if len(found)>1: raise ConfigError(f"duplicate field {field} in MediaMTX path {path_name}")
    if not found: return None
    raw=found[0]
    if raw.startswith('"'):
        try: return str(json.loads(raw))
        except json.JSONDecodeError as exc: raise ConfigError(f"invalid quoted field {field} in MediaMTX path {path_name}") from exc
    return raw.split(" #",1)[0].strip()
def validate_reader_ip(value):
    try: addr=ipaddress.ip_address(value)
    except ValueError as exc: raise ConfigError("reader IP must be a literal RFC1918 IPv4 address") from exc
    if not _is_rfc1918_ipv4(addr): raise ConfigError("reader IP must be a literal RFC1918 IPv4 address")
def _auth_internal_users_bounds(lines):
    matches = _find_top_level(lines, "authInternalUsers")
    if len(matches) != 1:
        raise ConfigError("MediaMTX config must contain exactly one top-level authInternalUsers block")
    start = matches[0]
    if not re.match(r"^authInternalUsers\s*:\s*(?:#.*)?(?:\n)?$", lines[start]):
        raise ConfigError("authInternalUsers must use a block sequence")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if not line.strip():
            continue
        if line[0] not in " \t":
            end = index
            break
    return start, end

def _reader_rule_lines(path_name,reader_ip):
    if not re.fullmatch(r"[A-Za-z0-9._-]+",path_name): raise ConfigError("MediaMTX path name must be a simple literal name")
    validate_reader_ip(reader_ip)
    return ["  " + READER_MARKER + "\n","  - user: any\n","    pass:\n",f"    ips: [{_yaml_string(reader_ip)}]\n","    permissions:\n","      - action: read\n",f"        path: {_yaml_string(path_name)}\n"]
def verify_internal_reader_rule(text,path_name,reader_ip):
    method=get_top_level_scalar(text,"authMethod")
    if method not in (None,"internal"): raise ConfigError("MediaMTX authMethod must be internal for bounded reader authorization")
    lines=_split_lines(text); start,end=_auth_internal_users_bounds(lines)
    expected=_reader_rule_lines(path_name,reader_ip); markers=[i for i in range(start+1,end) if lines[i].strip()==READER_MARKER]
    if len(markers)!=1: raise ConfigError("exactly one Sea Speed reader authorization rule is required")
    idx=markers[0]
    if lines[idx:idx+len(expected)]!=expected: raise ConfigError("Sea Speed reader authorization rule differs from the expected least-privilege rule")
def ensure_internal_reader_rule(text,path_name,reader_ip):
    method=get_top_level_scalar(text,"authMethod")
    if method not in (None,"internal"): raise ConfigError("MediaMTX authMethod must be internal for bounded reader authorization")
    lines=_split_lines(text); start,end=_auth_internal_users_bounds(lines)
    expected=_reader_rule_lines(path_name,reader_ip); markers=[i for i in range(start+1,end) if lines[i].strip()==READER_MARKER]
    if markers:
        if len(markers)!=1 or lines[markers[0]:markers[0]+len(expected)]!=expected: raise ConfigError("existing Sea Speed reader authorization rule does not match the requested VPS reader IP")
        return text
    lines[end:end]=expected
    rendered="".join(lines); verify_internal_reader_rule(rendered,path_name,reader_ip); return rendered

def read_protected_env_value(path,key):
    try: info=os.lstat(path)
    except OSError as exc: raise ConfigError("protected source env file is unavailable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode): raise ConfigError("protected source env file must be a regular non-symlink file")
    if stat.S_IMODE(info.st_mode)!=0o600: raise ConfigError("protected source env file mode must be 0600")
    try: lines=path.read_text(encoding="utf-8").splitlines()
    except OSError as exc: raise ConfigError("protected source env file cannot be read") from exc
    prefix=key+"="; values=[]
    for line in lines:
        stripped=line.strip()
        if not stripped or stripped.startswith("#") or not stripped.startswith(prefix): continue
        raw=stripped[len(prefix):].strip()
        if len(raw)>=2 and raw[0]==raw[-1] and raw[0] in {'"',"'"}: raw=raw[1:-1]
        values.append(raw)
    if len(values)!=1 or not values[0]: raise ConfigError(f"protected env file must contain exactly one non-empty {key}")
    return values[0]
def validate_camera_source(source):
    try: parsed=urlsplit(source); host=parsed.hostname
    except (TypeError,ValueError) as exc: raise ConfigError("camera source is not a valid RTSP URL") from exc
    if parsed.scheme.lower()!="rtsp" or not host: raise ConfigError("camera source must use rtsp with a host")
    if parsed.username is None: raise ConfigError("camera source must contain protected userinfo")
def validate_private_relay_url(source,expected_path):
    try: parsed=urlsplit(source); host=parsed.hostname
    except (TypeError,ValueError) as exc: raise ConfigError("private relay source is not a valid RTSP URL") from exc
    if parsed.scheme.lower()!="rtsp" or not host: raise ConfigError("private relay source must use rtsp with a host")
    if parsed.username is not None or parsed.password is not None: raise ConfigError("private relay source must not contain userinfo")
    if parsed.path.rstrip("/")!="/"+expected_path: raise ConfigError("private relay source path does not match the canonical path")
    try: address=ipaddress.ip_address(host)
    except ValueError as exc: raise ConfigError("private relay source must use a literal RFC1918 IPv4 address") from exc
    if not _is_rfc1918_ipv4(address): raise ConfigError("private relay source IP must be RFC1918")
def validate_private_rtsp_address(address):
    if address.count(":")!=1: raise ConfigError("private RTSP listen address must be IPv4:port")
    host,pt=address.rsplit(":",1)
    try: ip=ipaddress.ip_address(host); port=int(pt)
    except ValueError as exc: raise ConfigError("private RTSP listen address must be valid IPv4:port") from exc
    if not _is_rfc1918_ipv4(ip) or not (1<=port<=65535): raise ConfigError("private RTSP listen address must use RFC1918 IPv4 and valid port")
def read_config(path):
    try: info=os.lstat(path)
    except OSError as exc: raise ConfigError("MediaMTX config is unavailable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode): raise ConfigError("MediaMTX config must be a regular non-symlink file")
    try: return path.read_text(encoding="utf-8")
    except OSError as exc: raise ConfigError("MediaMTX config cannot be read") from exc
def write_candidate(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.is_symlink(): raise ConfigError("candidate output must not be a symlink")
    temp=path.with_name(path.name+".tmp")
    try:
        temp.write_text(text,encoding="utf-8"); os.chmod(temp,0o600); os.replace(temp,path); os.chmod(path,0o600)
    finally:
        try: temp.unlink()
        except FileNotFoundError: pass
    return hashlib.sha256(text.encode()).hexdigest()
def render_ubuntu_relay(args):
    text=read_config(args.config); source=read_protected_env_value(args.source_env_file,args.source_env_key); validate_camera_source(source); validate_private_rtsp_address(args.private_rtsp_address); validate_reader_ip(args.reader_ip)
    for key,value,quote in (("rtsp","yes",False),("rtspAddress",args.private_rtsp_address,True),("rtmp","no",False),("hls","no",False),("webrtc","no",False),("srt","no",False)): text=set_top_level_scalar(text,key,value,quote=quote)
    text=set_path_source(text,args.path,source,source_on_demand=True); text=ensure_internal_reader_rule(text,args.path,args.reader_ip); digest=write_candidate(args.output,text)
    print(f"RENDERED mode=ubuntu-relay path={args.path} source_scheme=rtsp source_has_userinfo=YES reader_scope=single-rfc1918-ip reader_permission=read-only output_sha256={digest}"); return digest
def render_verify_reader_auth(args):
    text=read_config(args.config); verify_internal_reader_rule(text,args.path,args.reader_ip); print(f"VERIFIED mode=reader-auth path={args.path} reader_scope=single-rfc1918-ip reader_permission=read-only"); return ""
def render_vps_switch(args):
    text=read_config(args.config); validate_private_relay_url(args.relay_url,args.path); text=set_path_source(text,args.path,args.relay_url,source_on_demand=True); digest=write_candidate(args.output,text); print(f"RENDERED mode=vps-switch path={args.path} relay_userinfo=NO output_sha256={digest}"); return digest
def render_vps_cleanup(args):
    text=read_config(args.config); validate_private_relay_url(args.relay_url,args.path); current=get_path_field(text,args.path,"source")
    if current!=args.relay_url: raise ConfigError("canonical path is not bound to the expected private relay")
    text=remove_path(text,args.remove_path); digest=write_candidate(args.output,text); print(f"RENDERED mode=vps-cleanup path={args.path} removed={args.remove_path} output_sha256={digest}"); return digest
def build_parser():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="command",required=True)
    u=sub.add_parser("ubuntu-relay"); u.add_argument("--config",type=Path,required=True); u.add_argument("--source-env-file",type=Path,required=True); u.add_argument("--source-env-key",default="HLS_URL"); u.add_argument("--private-rtsp-address",required=True); u.add_argument("--reader-ip",required=True); u.add_argument("--path",default="cam1"); u.add_argument("--output",type=Path,required=True); u.set_defaults(handler=render_ubuntu_relay)
    v=sub.add_parser("verify-reader-auth"); v.add_argument("--config",type=Path,required=True); v.add_argument("--reader-ip",required=True); v.add_argument("--path",default="cam1"); v.set_defaults(handler=render_verify_reader_auth)
    s=sub.add_parser("vps-switch"); s.add_argument("--config",type=Path,required=True); s.add_argument("--relay-url",required=True); s.add_argument("--path",default="cam1"); s.add_argument("--output",type=Path,required=True); s.set_defaults(handler=render_vps_switch)
    c=sub.add_parser("vps-cleanup"); c.add_argument("--config",type=Path,required=True); c.add_argument("--relay-url",required=True); c.add_argument("--path",default="cam1"); c.add_argument("--remove-path",default="cam1-new"); c.add_argument("--output",type=Path,required=True); c.set_defaults(handler=render_vps_cleanup)
    return p
def main():
    args=build_parser().parse_args()
    try: args.handler(args)
    except (ConfigError,OSError) as exc: print(f"ERROR: {exc}",file=sys.stderr); return 1
    return 0
if __name__=="__main__": raise SystemExit(main())
