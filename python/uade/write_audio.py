import argparse
from collections import deque
import os
import statistics
from PIL import Image, ImageDraw
import wave
from tqdm import tqdm
from typing import List

NUM_CHANNELS = 4

SAMPLES_PER_FRAME = 320
PIXELS_PER_SAMPLE = 4
assert (SAMPLES_PER_FRAME * PIXELS_PER_SAMPLE) == 1280

SOUNDTICKS_PAL = 3546895
FRAME_TICKS = None
PIXEL_TICKS = None

MARGIN = 8
VERTICAL_DIM = 720 // 4 - MARGIN

PAULA_EVENT_VOL = 1
PAULA_EVENT_PER = 2
PAULA_EVENT_DAT = 3
PAULA_EVENT_LEN = 4
PAULA_EVENT_LCH = 5
PAULA_EVENT_LCL = 6
PAULA_EVENT_LOOP = 7
PAULA_EVENT_OUTPUT = 8

PAULA_EVENTS = {
    PAULA_EVENT_VOL: 'vol',
    PAULA_EVENT_PER: 'per',
    PAULA_EVENT_DAT: 'dat',
    PAULA_EVENT_LEN: 'len',
    PAULA_EVENT_LCH: 'lch',
    PAULA_EVENT_LCL: 'lcl',
    PAULA_EVENT_LOOP: 'loop',
    PAULA_EVENT_OUTPUT: 'output',
}


def integrate(time_window, channel, args):
    signal = []
    i = 0
    while i < len(time_window):
        span = time_window[i:(i + PIXEL_TICKS)]
        x = statistics.mean(span) / (64 * 128)
        assert x >= -1.0 and x <= 1.0
        signal.append(x)
        i += PIXEL_TICKS

    trigger_state = 0

    centering = SAMPLES_PER_FRAME // 2
    cut_point = 0
    for i in range(centering, len(signal) - SAMPLES_PER_FRAME):
        if trigger_state == 0:
            if signal[i] < 0:
                trigger_state = 1
        else:
            if signal[i] >= 0:
                cut_point = i - centering
                assert cut_point >= 0
                assert (cut_point + SAMPLES_PER_FRAME) <= len(signal)
                break

    signal = signal[cut_point:(cut_point + SAMPLES_PER_FRAME)]
    assert len(signal) == SAMPLES_PER_FRAME

    return signal


class Channel:
    def __init__(self, channel: int):
        self.channel = channel
        self.time_window = []
        self.value = 0
        self.len = 0
        self.per = 0

    def advance_time(self, tdelta: int):
        self.time_window.extend([self.value] * tdelta)

    def poll_time_window(self):
        if len(self.time_window) < (2 * FRAME_TICKS):
            return None

        tw = self.time_window[:(2 * FRAME_TICKS)]
        self.time_window = self.time_window[FRAME_TICKS:]
        return tw


class AudioChannels:
    def __init__(self, normalisation_length: int):
        assert normalisation_length >= 0
        self.channels = []
        for i in range(NUM_CHANNELS):
            self.channels.append(Channel(i))

        self.normalisation_length = normalisation_length
        if self.normalisation_length == 0:
            self.normalisers = deque([1.0])
        else:
            self.normalisers = deque([1.0], maxlen=self.normalisation_length)

    def add_normaliser(self, normaliser: float):
        if self.normalisation_length > 0:
            self.normalisers.append(normaliser)

    def get_normaliser(self):
        return min(self.normalisers)


def _handle_paula_event(audio_channels: AudioChannels, outputs, wave_file,
                        frame, args):
    channel_nr = frame[4]
    assert channel_nr >= 0 and channel_nr < NUM_CHANNELS
    event_type = frame[5]
    event_value = int.from_bytes(frame[6:8], 'big')
    channel = audio_channels.channels[channel_nr]
    if args.verbose:
        event_type_str = PAULA_EVENTS.get(event_type)
        if event_type_str is None:
            event_type_str = 'unknown_{}'.format(event_type)
            print('paula event', channel_nr, event_type_str,
                  '0x{:04x}'.format(event_value))
    if event_type == PAULA_EVENT_LEN:
        channel.len = event_value
    elif event_type == PAULA_EVENT_PER:
        channel.per = event_value
    elif event_type == PAULA_EVENT_OUTPUT:
        assert channel_nr in (0, 1)
        outputs[channel_nr] = event_value
        if channel_nr == 1:
            wave_frame = (outputs[0].to_bytes(2, 'little') +
                          outputs[1].to_bytes(2, 'little'))
            wave_file.writeframes(wave_frame)
            outputs[0] = None
            outputs[1] = None


def _handle_paula_channel_output(audio_channels: AudioChannels, frame):
    # Handle Audio channel output
    index = 4
    for channel in audio_channels.channels:
        v = int.from_bytes(frame[index:(index + 2)], 'big')
        if v >= 0x8000:
            v -= 65536
        channel.value = v
        index += 2


class FrameImage:
    def __init__(self):
        self.im = None
        self.px = None
        self.im_line = None

    def lazy_init(self):
        if self.im is not None:
            return
        self.im = Image.new('RGB',
                            (SAMPLES_PER_FRAME * PIXELS_PER_SAMPLE,
                             (VERTICAL_DIM + MARGIN) * NUM_CHANNELS))
        self.px = self.im.load()  # For drawing pixels
        self.im_line = ImageDraw.Draw(self.im)  # For drawing lines


def _advance_time_on_channel(channel: Channel, tdelta: int, args):
    # TODO: Try maximum scanning range for trigger logic that equals
    #       channel.per * channel.len * 2

    channel.advance_time(tdelta)

    time_window = channel.poll_time_window()
    if time_window is None:
        return None

    # TODO: For certain register bit streams this assertion could fail,
    # but we don't need to handle it. Just check it.
    if channel.poll_time_window() is not None:
        raise NotImplementedError('channel.advance_time() generated more than '
                                  'one frame of data')

    return integrate(time_window, channel, args)


def _plot_channel(fi: FrameImage, channel: Channel, signal: List[float]):
    fi.lazy_init()

    base_y = channel.channel * (VERTICAL_DIM + MARGIN) + VERTICAL_DIM // 2

    for x in range(len(signal)):
        y = base_y + int(signal[x] * (VERTICAL_DIM // 2 - 1))

        if (x + 1) < len(signal):
            next_y = base_y + int(signal[x + 1] * (VERTICAL_DIM // 2 - 1))

            shape = [(PIXELS_PER_SAMPLE * x, y),
                     (PIXELS_PER_SAMPLE * (x + 1), next_y)]
            fi.im_line.line(shape)
        else:
            fi.px[PIXELS_PER_SAMPLE * x, y] = (255, 255, 255)


def _advance_time(audio_channels: AudioChannels, tdelta: int, args):
    if tdelta == 0:
        return None

    signals = []
    abs_max = 1e-10
    for channel in audio_channels.channels:
        signal = _advance_time_on_channel(channel, tdelta, args)
        if signal is not None:
            abs_max = max(abs_max, max([abs(x) for x in signal]))
            signals.append((channel, signal))

    assert len(signals) == 0 or len(signals) == NUM_CHANNELS

    if len(signals) == NUM_CHANNELS:
        audio_channels.add_normaliser(1.0 / abs_max)

    normaliser = audio_channels.get_normaliser()

    fi = FrameImage()

    for channel, signal in signals:
        normalised_signal = [normaliser * x for x in signal]
        _plot_channel(fi, channel, normalised_signal)

    return fi.im


def _init_globals(args):
    global FRAME_TICKS, PIXEL_TICKS
    FRAME_TICKS = SOUNDTICKS_PAL // args.fps
    PIXEL_TICKS = FRAME_TICKS // SAMPLES_PER_FRAME


def main(main_args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('file', nargs=1)
    parser.add_argument('--fps', type=int, default=50)
    parser.add_argument('--image-prefix', default='output_')
    parser.add_argument('--image-format', default='png')
    parser.add_argument('--manual', action='store_true')
    parser.add_argument('--normalisation-length', type=int, default=50)
    parser.add_argument('--sampling-rate', default=44100)
    parser.add_argument('--target-dir', required=True)
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--wave', required=True)
    args = parser.parse_args(args=main_args)

    assert os.path.isdir(args.target_dir)
    assert args.fps > 0

    _init_globals(args)

    reg_file = open(args.file[0], 'rb')

    reg_file_size = None
    if reg_file.seekable():
        reg_file_size = reg_file.seek(0, 2)
        reg_file.seek(0, 0)

    HEADER_SIZE = 16
    FRAME_SIZE = 12
    progress_bar = tqdm(total=reg_file_size)

    header = reg_file.read(HEADER_SIZE)
    progress_bar.update(len(header))

    assert header == b'uade_osc_0\x00\xec\x171\x03\t'

    num_images = 0

    wave_file = wave.open(args.wave, 'wb')
    wave_file.setframerate(args.sampling_rate)
    wave_file.setnchannels(2)
    wave_file.setsampwidth(2)

    outputs = [None, None]

    audio_channels = AudioChannels(args.normalisation_length)

    while True:
        # See src/write_audio.c: struct uade_write_audio_frame. It describes
        # the data format of the frame.
        frame = reg_file.read(FRAME_SIZE)
        progress_bar.update(len(frame))
        if len(frame) == 0:
            break

        # Read an unsigned 24-bit time delta value
        tdelta_time = frame[1:4]
        tdelta = int.from_bytes(tdelta_time, 'big')

        im = _advance_time(audio_channels, tdelta, args)
        if im is not None:
            if args.manual:
                print('image frame', num_images)
                im.show()
                input('Enter to continue...')

            basename = '{}{:06d}.{}'.format(
                args.image_prefix, num_images, args.image_format)
            fname = os.path.join(args.target_dir, basename)
            im.save(fname, args.image_format)
            num_images += 1

        tdelta_control = frame[0]
        if tdelta_control == 0:
            # This frame contains new PCM values for each channel
            _handle_paula_channel_output(audio_channels, frame)
        elif tdelta_control == 0x80:
            # This frame is a register write or a loop event
            _handle_paula_event(audio_channels, outputs, wave_file, frame,
                                args)
        else:
            raise NotImplementedError(
                'Unsupported control byte: {}. '
                'This is probably a bug or a format extension.'.format(
                    tdelta_control))

    wave_file.close()
    reg_file.close()


if __name__ == '__main__':
    main()
