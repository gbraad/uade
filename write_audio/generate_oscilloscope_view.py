import argparse
import ast
import os.path
import subprocess
import tempfile

import write_audio


class ArgumentError(Exception):
    pass


def main():
    parser = argparse.ArgumentParser('adsf')
    parser.add_argument('--target-dir', '-t', required=True)
    parser.add_argument('--ffmpeg', default='ffmpeg', help='Path to ffmpeg')
    parser.add_argument('files', metavar='FILE', nargs='*')
    parser.add_argument('--fps', type=int, default=50)
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

    for songfile in args.files:
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
                break
            wavefile = os.path.join(tmpdir, bname + '.wav')

            print('Generating oscilloscope images from {}'.format(regfile))
            write_audio.main(['--target-dir', tmpdir, '--wave', wavefile,
                              regfile, '--fps', str(args.fps)])

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


if __name__ == '__main__':
    main()
