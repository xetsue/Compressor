import argparse
import os
import subprocess
import sys 
import shutil
import re
import time 
import json
import platform
import urllib.request
import zipfile
import io

CRF_PRESETS = {
    '1_high_quality': 23, 
    '2_medium': 28,       
    '3_high_compression': 33,
}

RESOLUTION_OPTIONS = {
    '1_1080p': '1920:-1', 
    '2_720p': '1280:-1',   
    '3_480p': '854:-1',    
    '4_original': None,
    '5_custom': 'custom'
}

FPS_OPTIONS = [60, 50, 48, 30, 25, 24]
PRESET_OPTIONS = ['ultrafast', 'veryfast', 'fast', 'medium', 'slow', 'veryslow']

GPU_ENCODERS = {
    'nvidia': 'h264_nvenc',
    'amd': 'h264_amf',
    'intel': 'h264_qsv'
}

DEFAULT_OUTPUT_PLACEHOLDER = 'AUTO_COMPRESSED_NAME'
TEMP_FILE_NAME = 'temp_ffmpeg_output.mp4' 
NOTIFICATION_ID = 'XV_COMPRESS_NOTIF'
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

def set_terminal_title(title):
    if os.name == 'nt': 
        safe_title = title.replace('|', '-').replace('&', 'and').replace('<', '[').replace('>', ']')
        os.system(f'title {safe_title}')
    else:
        sys.stdout.write(f"\x1b]2;{title}\x07")
        sys.stdout.flush()

def get_binary_path(binary_name):
    if shutil.which(binary_name):
        return binary_name
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_path = os.path.join(script_dir, binary_name)
    
    if platform.system() == 'Windows':
        if os.path.exists(local_path + ".exe"): return local_path + ".exe"
    
    if os.path.exists(local_path): return local_path
    return None

def download_ffmpeg(is_desktop):
    print("\n[!] FFmpeg binaries not found.")
    print("    This is required to process videos.")
    print(f"    Downloading portable FFmpeg from: {FFMPEG_URL}")
    print("    This may take a minute depending on your internet connection...")
    
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        with urllib.request.urlopen(FFMPEG_URL) as response:
            total_size = int(response.info().get('Content-Length', 0))
            downloaded = 0
            chunk_size = 8192
            buffer = io.BytesIO()
            
            while True:
                chunk = response.read(chunk_size)
                if not chunk: break
                buffer.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = downloaded / total_size * 100
                    if is_desktop:
                        set_terminal_title(f"Downloading FFmpeg: {percent:.1f}%")
                    print(f"\r    Downloading: {percent:.1f}%", end='')
            
            print("\n    Download complete. Extracting...")
            
            with zipfile.ZipFile(buffer) as z:
                for file_info in z.infolist():
                    if file_info.filename.endswith('bin/ffmpeg.exe'):
                        file_info.filename = 'ffmpeg.exe'
                        z.extract(file_info, script_dir)
                    elif file_info.filename.endswith('bin/ffprobe.exe'):
                        file_info.filename = 'ffprobe.exe'
                        z.extract(file_info, script_dir)
                        
        print("    [OK] FFmpeg installed successfully to script folder.\n")
        return True
        
    except Exception as e:
        print(f"\n[!] Failed to download FFmpeg: {e}")
        print("    Please download 'ffmpeg-release-essentials.zip' from gyan.dev")
        print("    and extract 'ffmpeg.exe' and 'ffprobe.exe' to this folder manually.")
        return False

def convert_ffmpeg_size(size_str):
    match = re.match(r'(\d+)KiB', size_str)
    if not match: return size_str
    value_kib = int(match.group(1))
    bytes_value = value_kib * 1024
    if bytes_value >= 1024**3: return f"{bytes_value / 1024**3:.2f}GB"
    elif bytes_value >= 1024**2: return f"{bytes_value / 1024**2:.2f}MB"
    elif bytes_value >= 1024: return f"{bytes_value / 1024:.2f}KB"
    else: return f"{bytes_value}B"

def get_file_size_mb(filepath):
    if not os.path.exists(filepath): return None
    return os.path.getsize(filepath) / (1024 * 1024)

def get_output_filename(input_path, output_name):
    if output_name == DEFAULT_OUTPUT_PLACEHOLDER:
        base_dir, base_name = os.path.split(input_path)
        root, _ = os.path.splitext(base_name)
        return os.path.join(base_dir, f"{root}_compressed.mp4")
    return output_name

def get_video_metadata(filepath):
    local_ffprobe = get_binary_path('ffprobe')
    if not local_ffprobe:
        return {'fps': 0.0, 'bitrate_kbps': 0.0, 'width': 0, 'height': 0, 'resolution': 'N/A', 'duration': 0.0}
    try:
        command = [
            local_ffprobe, '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=avg_frame_rate,bit_rate,width,height,duration',
            '-of', 'json', filepath
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)['streams'][0]
        
        fps_frac = data.get('avg_frame_rate', '0/1').split('/')
        fps = float(fps_frac[0]) / float(fps_frac[1]) if len(fps_frac) == 2 and float(fps_frac[1]) != 0 else 0.0
        
        return {
            'fps': round(fps, 2),
            'bitrate_kbps': int(data.get('bit_rate', 0)) / 1000,
            'width': int(data.get('width', 0)),
            'height': int(data.get('height', 0)),
            'resolution': f"{data.get('width')}x{data.get('height')}",
            'duration': float(data.get('duration', 0))
        }
    except Exception:
        return {'fps': 0.0, 'bitrate_kbps': 0.0, 'width': 0, 'height': 0, 'resolution': 'N/A', 'duration': 0.0}

def estimate_final_size(original_size_mb, crf, original_width, target_resolution, preset):
    base_factor = 1.0 / (1.15 ** (crf - 23))
    if base_factor > 1.3: base_factor = 1.3 
    if base_factor < 0.05: base_factor = 0.05

    res_factor = 1.0
    if target_resolution and original_width > 0:
        try:
            target_w_str = target_resolution.split(':')[0]
            target_w = int(target_w_str)
            res_factor = (target_w / original_width) ** 2
        except: res_factor = 1.0

    preset_modifiers = {'ultrafast': 1.40, 'veryfast': 1.20, 'fast': 1.10, 'medium': 1.0, 'slow': 0.95, 'veryslow': 0.90}
    preset_factor = preset_modifiers.get(preset, 1.0)
    
    total_factor = max(base_factor * res_factor * preset_factor, 0.05)
    return original_size_mb * total_factor

def parse_time_to_seconds(time_str):
    try:
        parts = time_str.split(':')
        if len(parts) == 3: return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except: return 0.0
    return 0.0

def format_seconds(seconds):
    if seconds < 60: return f"{int(seconds)}s"
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{int(m)}m {int(s)}s"
    else:
        h, r = divmod(seconds, 3600)
        m, s = divmod(r, 60)
        return f"{int(h)}h {int(m)}m"

def update_termux_notification(title, content, progress_percent=None):
    if shutil.which('termux-notification'):
        cmd = ['termux-notification', '--id', NOTIFICATION_ID, '--title', title, '--content', content, '--alert-once']
        if progress_percent is not None:
             cmd.extend(['--priority', 'high', '--ongoing'])
        subprocess.run(cmd, check=False)

def clear_termux_notification():
    if shutil.which('termux-notification-remove'):
        subprocess.run(['termux-notification-remove', NOTIFICATION_ID], check=False, stderr=subprocess.DEVNULL)

def compress_video(params):
    input_path = params['input_path']
    output_path = params['output_path']
    crf = params['crf']
    resolution = params['resolution']
    preset = params['preset']
    fps = params['fps']
    encoder = params['encoder']
    is_desktop = params['is_desktop']
    temp_path = params['temp_output_path']
    duration = params['duration']
    
    local_ffmpeg = get_binary_path('ffmpeg')
    if not local_ffmpeg: return False

    res_display = resolution if resolution else f"Original ({params['orig_w']}x{params['orig_h']})"
    fps_display = fps if fps else f"Original ({params['orig_fps']} fps)"

    print(f"\n🎥 Starting compression:")
    print(f"  Encoder:    {encoder}")
    print(f"  CRF/QP:     {crf}")
    print(f"  Resolution: {res_display}")
    print(f"  FPS:        {fps_display}")
    print(f"  Preset:     {preset}")
    print(f"  Log Update: Every {params['log_interval']}s")
    print(f"  Estimate:   OG {params['orig_size']:.1f} MB -> ~{params['est_size']:.1f} MB")
    print("---")

    cmd = [local_ffmpeg, '-y', '-i', input_path, '-loglevel', 'verbose']
    cmd.extend(['-c:v', encoder])
    
    if encoder == 'libx264': cmd.extend(['-crf', str(crf), '-preset', preset])
    elif encoder == 'h264_nvenc': cmd.extend(['-rc', 'vbr', '-cq', str(crf), '-preset', 'p4']) 
    elif encoder == 'h264_amf': cmd.extend(['-rc', 'cqp', '-qp_i', str(crf), '-qp_p', str(crf), '-quality', 'balanced'])
    elif encoder == 'h264_qsv': cmd.extend(['-global_quality', str(crf), '-preset', 'medium'])

    cmd.extend(['-c:a', 'aac', '-b:a', '128k'])

    filters = []
    if resolution: filters.append(f'scale={resolution}')
    if fps: filters.append(f'fps={fps}')
    if filters: cmd.extend(['-vf', ','.join(filters)])
        
    cmd.append(temp_path)

    process = None
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        
        start_t = time.time()
        last_log_t = start_t
        
        while True:
            line = process.stderr.readline()
            if not line and process.poll() is not None: break
            
            if "frame=" in line:
                curr_t = time.time()
                raw = line.strip()
                clean_line = re.sub(r'q=[\d.-]+\s*', '', raw)
                
                s_match = re.search(r'size=\s*(\d+KiB)', clean_line)
                if s_match:
                    clean_line = clean_line.replace(s_match.group(1), convert_ffmpeg_size(s_match.group(1)))

                percent = 0.0
                eta_str = "--:--"
                t_match = re.search(r'time=(\d{2}:\d{2}:\d{2}\.\d+)', raw)
                
                if t_match and duration > 0:
                    secs = parse_time_to_seconds(t_match.group(1))
                    percent = min((secs / duration) * 100, 99.9)
                    if percent > 0.1:
                        elapsed = curr_t - start_t
                        rem_secs = (elapsed / percent) * (100 - percent)
                        eta_str = format_seconds(rem_secs)
                    
                    clean_line += f" | {percent:.1f}% | ETA: {eta_str}"

                if curr_t - last_log_t >= params['log_interval']:
                    print(f"\r{clean_line}", end='')
                    sys.stdout.flush()
                    last_log_t = curr_t
                    
                    if is_desktop:
                        set_terminal_title(f"{percent:.0f}% - ETA {eta_str} - {os.path.basename(input_path)}")
                    else:
                        termux_content = f"Prog: {percent:.1f}% | ETA: {eta_str}\nOG: {params['orig_size']:.0f}MB -> Est: ~{params['est_size']:.0f}MB"
                        update_termux_notification("Compressing Video...", termux_content, percent)

        process.wait()
        print() 
        
        if process.returncode != 0:
            print(f"[!] FFmpeg Error {process.returncode}")
            return False
            
        shutil.move(temp_path, output_path)
        return True

    except KeyboardInterrupt:
        print("\n\n🛑 Stopping FFmpeg...")
        if process:
            process.kill()
            process.wait()
        raise KeyboardInterrupt

    except Exception as e:
        print(f"\n[!] Error: {e}")
        if process:
            process.kill()
        return False

def interactive_input(is_desktop, file_path=None):
    print("\n=== Universal Video Compressor ===")
    
    if file_path and os.path.exists(file_path):
        path = file_path
    else:
        while True:
            path = input("Enter video path: ").strip().strip('"\'')
            if os.path.exists(path): break
            print("File not found.")

    meta = get_video_metadata(path)
    print(f"   [Info] {meta['resolution']} @ {meta['fps']}fps | {meta['bitrate_kbps']}kbps")

    out_path = input("Output filename (Enter for auto): ").strip().strip('"\'')
    if not out_path: out_path = DEFAULT_OUTPUT_PLACEHOLDER

    encoder = 'libx264'
    if is_desktop:
        print("\n--- Processing Method ---")
        print("  1: CPU (High Quality) [Default]")
        print("  2: GPU - NVIDIA (NVENC)")
        print("  3: GPU - AMD (AMF)")
        print("  4: GPU - INTEL (QSV)")
        m = input("Choose (1-4): ").strip()
        if m == '2': encoder = GPU_ENCODERS['nvidia']
        elif m == '3': encoder = GPU_ENCODERS['amd']
        elif m == '4': encoder = GPU_ENCODERS['intel']
    
    print("\n--- Quality (CRF/QP) ---")
    keys = sorted(CRF_PRESETS.keys())
    for i, k in enumerate(keys, 1):
        print(f"  {i}: {k.split('_', 1)[1].replace('_', ' ').title()} ({CRF_PRESETS[k]})")
    print(f"  {len(keys)+1}: Custom Value")
    
    crf = 28
    c = input(f"Choose (1-{len(keys)+1}): ").strip()
    if c.isdigit():
        idx = int(c)
        if 1 <= idx <= len(keys): crf = CRF_PRESETS[keys[idx-1]]
        elif idx == len(keys)+1: 
            v = input("Enter CRF (0-51): ").strip()
            if v.isdigit(): crf = int(v)

    print("\n--- Resolution ---")
    res_keys = sorted(RESOLUTION_OPTIONS.keys())
    for i, k in enumerate(res_keys, 1):
        v = RESOLUTION_OPTIONS[k]
        print(f"  {i}: {k.split('_', 1)[1].replace('_', ' ').title()} ({v if v else 'Original'})")
    
    res = None
    r = input("Choose (Default: 4): ").strip()
    if r.isdigit():
        idx = int(r)
        if 1 <= idx <= len(res_keys):
            k = res_keys[idx-1]
            if k == '5_custom': res = input("Ex: 1280:-1 : ").strip()
            else: res = RESOLUTION_OPTIONS[k]

    print(f"\n--- FPS Control (Original: {meta['fps']}) ---")
    print(f"  1: Keep Original [Default]")
    for i, f in enumerate(FPS_OPTIONS, 2):
        print(f"  {i}: {f} fps")
    print(f"  {len(FPS_OPTIONS)+2}: Custom")
    
    final_fps = None
    f_c = input(f"Choose (1-{len(FPS_OPTIONS)+2}): ").strip()
    if f_c.isdigit():
        idx = int(f_c)
        if idx > 1 and idx <= len(FPS_OPTIONS)+1: final_fps = FPS_OPTIONS[idx-2]
        elif idx == len(FPS_OPTIONS)+2: final_fps = input("Enter FPS: ").strip()

    preset = 'medium'
    if encoder == 'libx264':
        print(f"\n--- Speed Preset ---")
        print(f"Options: {', '.join(PRESET_OPTIONS)}")
        p = input("Enter preset (default: medium): ").strip().lower()
        if p in PRESET_OPTIONS: preset = p

    log_interval = 2.0 if not is_desktop else 0.5
    print(f"\n--- Log Interval ---")
    print(f"Default: {log_interval}s")
    l_in = input("Enter interval (seconds) or Press Enter: ").strip()
    try:
        if l_in: 
            val = float(l_in)
            if val >= 0.1: log_interval = val
    except: pass

    return {
        'input_path': path, 'output_path': out_path, 'crf': crf, 
        'resolution': res, 'fps': final_fps, 'preset': preset, 
        'encoder': encoder, 'is_desktop': is_desktop,
        'orig_w': meta['width'], 'orig_h': meta['height'],
        'orig_fps': meta['fps'], 'duration': meta['duration'],
        'log_interval': log_interval
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('input', nargs='?', help="Input file")
    parser.add_argument('-d', '--desktop', action='store_true', help="Enable Desktop mode")
    parser.add_argument('-e', '--encoder', default='cpu', choices=['cpu', 'nvidia', 'amd', 'intel'], help="Encoder type")
    parser.add_argument('-q', '--crf', type=int, default=28, help="CRF/Quality value (default 28)")
    parser.add_argument('-res', '--resolution', default='original', help="Resolution (e.g. 1080p, 720p, or original)")
    parser.add_argument('-fps', '--fps', default='original', help="FPS (e.g. 30, 60, or original)")
    parser.add_argument('-p', '--preset', default='medium', help="Encoder preset")
    parser.add_argument('-l', '--log', type=float, default=0.5, help="Log interval in seconds")
    parser.add_argument('-y', '--yes', action='store_true', help="Auto confirm keep file")

    args = parser.parse_args()

    is_desktop = args.desktop or platform.system() == 'Windows'
    
    if not get_binary_path('ffmpeg') or not get_binary_path('ffprobe'):
        if is_desktop or platform.system() == 'Windows':
            download_ffmpeg(is_desktop)
            if not get_binary_path('ffmpeg'):
                input("Press Enter to exit...")
                sys.exit(1)
        else:
            print("[!] FFmpeg not found. Please install it using your package manager (e.g., pkg install ffmpeg).")
            sys.exit(1)

    temp_out = None
    auto_confirm = False

    try:
        if args.input:
            enc_map = {'cpu': 'libx264', 'nvidia': 'h264_nvenc', 'amd': 'h264_amf', 'intel': 'h264_qsv'}
            encoder = enc_map.get(args.encoder, 'libx264')
            
            res = None
            if args.resolution != 'original':
                 if '1080' in args.resolution: res = '1920:-1'
                 elif '720' in args.resolution: res = '1280:-1'
                 elif '480' in args.resolution: res = '854:-1'
                 else: res = args.resolution

            fps = None
            if args.fps != 'original':
                fps = args.fps

            meta = get_video_metadata(args.input)
            
            settings = {
                'input_path': args.input,
                'output_path': DEFAULT_OUTPUT_PLACEHOLDER,
                'crf': args.crf,
                'resolution': res,
                'fps': fps,
                'preset': args.preset,
                'encoder': encoder,
                'is_desktop': is_desktop,
                'orig_w': meta['width'],
                'orig_h': meta['height'],
                'orig_fps': meta['fps'],
                'duration': meta['duration'],
                'log_interval': args.log
            }
            auto_confirm = args.yes
        else:
            settings = interactive_input(is_desktop, None)
            auto_confirm = False

        final_out = get_output_filename(settings['input_path'], settings['output_path'])
        temp_out = os.path.join(os.path.dirname(final_out), TEMP_FILE_NAME)
        orig_size = get_file_size_mb(settings['input_path'])
        
        est_size = estimate_final_size(
            orig_size, settings['crf'], settings['orig_w'], settings['resolution'], settings['preset']
        )

        compress_params = {
            'input_path': settings['input_path'],
            'output_path': final_out,
            'temp_output_path': temp_out,
            'crf': settings['crf'],
            'resolution': settings['resolution'],
            'preset': settings['preset'],
            'fps': settings['fps'],
            'encoder': settings['encoder'],
            'is_desktop': settings['is_desktop'],
            'log_interval': settings['log_interval'],
            'duration': settings['duration'],
            'orig_size': orig_size,
            'est_size': est_size,
            'orig_w': settings['orig_w'],
            'orig_h': settings['orig_h'],
            'orig_fps': settings['orig_fps']
        }

        if is_desktop: set_terminal_title("Processing...")
        
        start_time = time.time()
        success = compress_video(compress_params)
        
        if success:
            final_size = get_file_size_mb(final_out)
            reduction = orig_size - final_size
            pct = (reduction / orig_size) * 100
            
            print(f"\n☑ Done in {format_seconds(time.time() - start_time)}")
            print(f"Original: {orig_size:.2f} MB")
            print(f"Result:   {final_size:.2f} MB")
            print(f"Saved:    {reduction:.2f} MB ({pct:.2f}%)")
            
            if is_desktop: set_terminal_title(f"Done! Saved {pct:.0f}%")
            else:
                update_termux_notification("Compression Complete", f"Saved {pct:.1f}% ({final_size:.1f}MB)")
                
            if not auto_confirm:
                while True:
                    k = input("Keep file? (y/n): ").lower()
                    if k == 'y': break
                    elif k == 'n': 
                        os.remove(final_out)
                        print("Deleted.")
                        break
            else:
                print("Auto-keeping file.")
        else:
             print("\n[!] Compression failed.")

    except KeyboardInterrupt:
        print("\n\n[!] Operation Cancelled by User.")
        
    finally:
        if temp_out and os.path.exists(temp_out):
            try:
                os.remove(temp_out)
                print("[*] Temp file cleaned up.")
            except Exception as e:
                print(f"[!] Warning: Could not remove temp file: {e}")
                
        if not is_desktop:
            clear_termux_notification()
            
    sys.exit(0)