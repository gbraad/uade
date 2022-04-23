# TODO: Implement recursive directory scanning

import argparse
import ast
from multiprocessing import cpu_count, Pool
import os.path
import subprocess
import tempfile
from typing import List

from . import write_audio


class ArgumentError(Exception):
    pass


def _process_songfile(songfile: str,
                      args,
                      uade123_arg_list: List[str],
                      write_audio_options_list: List[str]) -> int:

    with tempfile.TemporaryDirectory(dir=args.target_dir) as tmpdir:
        bname = os.path.basename(songfile)
        regfile = os.path.join(tmpdir, bname + '.reg')
        print('Generating register dump for {}...'.format(songfile))
        cp = subprocess.run([
            args.uade123,
            '-f', '/dev/null',
            '--write-audio', regfile] + uade123_arg_list + [songfile],
            stdout=subprocess.DEVNULL)
        if cp.returncode != 0:
            print('Failed to play {}'.format(songfile))
            return 1

        wavefile = os.path.join(tmpdir, bname + '.wav')

        print('Generating oscilloscope images from {}'.format(regfile))
        write_audio.main(['--target-dir', tmpdir, '--wave', wavefile,
                          '--fps', str(args.fps)] + write_audio_options_list +
                         [regfile])

        image_pattern = os.path.join(tmpdir, 'output_%06d.png')

        videofile = os.path.join(args.target_dir, bname + '.mp4')

        print('Generating video file {}'.format(videofile))

        cp = subprocess.run([
            args.ffmpeg,
            '-i', wavefile,
            '-framerate', str(args.fps),
            '-i', image_pattern,
            '-y',
            '-pix_fmt', 'yuv420p',
            videofile],
            capture_output=True)

        if cp.returncode != 0:
            print('ffmpeg failed. STDOUT:\n\n{}\n\nSTDERR:\n\n{}\n'.format(
                cp.stdout.decode(), cp.stderr.decode()))
            print()
            print('Failed to create video for {}'.format(songfile))
            return 1

    return 0


def _generate_video(*pos) -> int:
    try:
        return _process_songfile(*pos)
    except Exception as e:
        print('Job {} threw an exception: {}'.format(pos, e))
        return 2


def main() -> int:
    parser = argparse.ArgumentParser('adsf')
    parser.add_argument('--target-dir', '-t', required=True)
    parser.add_argument('--ffmpeg', default='ffmpeg', help='Path to ffmpeg')
    parser.add_argument('files', metavar='FILE', nargs='*')
    parser.add_argument(
        '--fps', type=int, default=60,
        help=('Set framerate. Recommended values are 50, 60 and anything '
              'higher that is supported by the display and streaming '
              'technology.'))
    parser.add_argument(
        '--multiprocessing', action='store_true',
        help='Encode videos in parallel with all threads available.')
    parser.add_argument(
        '--parallelism', '-p', type=int,
        help=('Sets the amount of parallelism encoded. '
              'Same as --multiprocessing but specifies the amount of '
              'parallelism explicitly.'))
    parser.add_argument(
        '--recursive', '-r', action='store_true',
        help='Scan directories recursively')
    parser.add_argument('--uade123', default='uade123', help='Path to uade123')
    parser.add_argument(
        '--uade123-args', type=ast.literal_eval, default={},
        help=('Pass given argument to uade123. This is written as a Python '
              'dictionary. E.g. passing -t 60 for uade123 means giving '
              'argument --uade123-args "{\'-t\': 60, \'-1\': None}". '
              'If dictionary '
              'value is None, the argument is interpreted to have no value. '
              'Values are automatically converted into strings. '
              'Note: Python dictionary '
              'preserves the order of dictionary entries, so the order of '
              'arguments is also preserved for uade123. '
              'Note: Giving --uade123-args "{\'-t\': 1}" is good for '
              'testing.'))

    args = parser.parse_args()
    assert args.fps > 0

    if not os.path.isdir(args.target_dir):
        raise ArgumentError('{} is not a directory'.format(args.target_dir))

    uade123_arg_list = []
    for key, value in args.uade123_args.items():
        if not isinstance(key, str):
            raise ArgumentError('Given key {} should be a string'.format(key))

        if value is None:
            uade123_arg_list.append(key)
        else:
            uade123_arg_list.extend((key, str(value)))

    if args.parallelism is not None:
        if args.parallelism < 1:
            raise ArgumentError('Invalid parallelism: {}'.format(
                args.parallelism))
        num_processes = args.parallelism
    elif args.multiprocessing:
        num_processes = cpu_count()
    else:
        num_processes = 1

    write_audio_options_list = []
    if num_processes > 1:
        write_audio_options_list.append('--batch')

    jobs = []
    for path in args.files:
        if os.path.isdir(path):
            if args.recursive:
                for dirpath, dirnames, filenames in os.walk(path):
                    for filename in filenames:
                        songfile = os.path.join(dirpath, filename)
                        jobs.append((songfile, args, uade123_arg_list,
                                     write_audio_options_list))
            else:
                print('Ignoring {} because it is a directory. Use -r to scan '
                      'directories.'.format(path))
                return 1
        else:
            jobs.append((path, args, uade123_arg_list,
                         write_audio_options_list))

    with Pool(processes=num_processes) as pool:
        job_retcodes = pool.starmap(_generate_video, jobs)

    for job_retcode in job_retcodes:
        if job_retcode != 0:
            return job_retcode

    return 0
