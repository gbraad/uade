# Oscilloscope view

generate_oscilloscope_view.py is a Python script to generate Oscilloscope
view videos with FFMPEG. Usage:
```
$ python3 generate_oscilloscope_view.py --target-dir /video_dir ../songs/AHX.Cruisin
```

A generated video has 50 frames per second by default.
For publishing in streaming services, consider using --fps 60 argument.

# Dependencies

Tools:
* ffmpeg (apt install ffmpeg)

Python 3 libraries:
* Python Imaging Library (apt install python3-pil)
* tqdm (apt install python3-tqdm)
