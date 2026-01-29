# Compressor
Drag n' Drop Video Compressor based on FFmpeg. (Termux is also supported)

## Download from [https://github.com/xetsue/Compressor/releases](https://github.com/xetsue/Compressor/releases)

# Usage
## 1. (Desktop Portable)
  -  Download the `Compressor.zip`  unzip anywhere on your device. 
  - Make sure to download the following  3 items: **COMPRESSOR.zip**, **FFMPEG** and **FFPROBE** `.exe`. 
  -  Place the **FFMPEG** and **FFPROBE** `.exe` files inside the `Compressor` folder. You may either run the python script manually  or use the `.bat` found inside the `Compressor.zip`.
  - You can drag any video files you want to compress to the `.bat` to quickly start the script without needing to write paths to your target file.
  
## 2. (Alternative Method) With ffmpeg installed or use case with termux.
  -  Alternative/Termux - ffmpeg needs to be installed through the terminal first before running this script. FFMPEG & FFPROBE `(.exe)` are NOT needed for this version. The script will check if ffmpeg is within the device paths and properly installed before running. A warning will follow if it fails to detect any ffmpeg installed. 
  - Note that this script runs slower on mobile devices. Any performance difference between desktop usage and mobile usage is unavoidable. You have been informed. 
  - Desktop version supports using both CPU and GPU to render your processes, thus the significance.
  - You may use wake-lock / `Acquire Wakelock` function (Found on termux notification) to allow this process run in the background uninterrupted. (For TERMUX) There are live notification included to update on current progress but this will require [Termux-API Addon](https://wiki.termux.com/wiki/Termux:API)

## Credits
- [[Termux](https://wiki.termux.com/wiki/Main_Page)] Packages Usage and Implementation.
- [[Google AI Studio](https://ai.google.dev/gemini-api/docs/ai-studio-quickstart)] for assisted coding. 
- [ [GYAN.DEV](https://www.gyan.dev/ffmpeg/builds/) ] for Extracted FFMPEG & FFPROBE `(.exe)` --- dev/s behind FFMPEG CODEX project.
File paths extracted inside  `ffmpeg-release-essentials.zip\bin`
Full codex: [https://www.gyan.dev/ffmpeg/builds/](https://www.gyan.dev/ffmpeg/builds/)
> Last recorded as of 29 Jan 2026 9:00PM UTC
