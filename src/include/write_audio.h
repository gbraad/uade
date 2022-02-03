#ifndef _UADE_WRITE_AUDIO_H_
#define _UADE_WRITE_AUDIO_H_

#include <stdio.h>
#include <stdint.h>

/* These must have permanent integer values due to write-audio */
enum PaulaEventType {
	PET_NONE = 0,
	PET_VOL = 1,
	PET_PER = 2,
	PET_DAT = 3,
	PET_LEN = 4,
	PET_LCH = 5,
	PET_LCL = 6,
	PET_LOOP = 7,
	PET_OUTPUT = 8,
	PET_MAX_ENUM,  /* This value may change */
};

#define UADE_WRITE_AUDIO_MAGIC "uade_osc_0\x00\xec\x17\x31\x03\x09"

struct uade_write_audio_header {
	char magic[16];  // UADE_WRITE_AUDIO_MAGIC
};

struct uade_write_audio;

struct uade_write_audio *uade_write_audio_init(const char *fname);
void uade_write_audio_write(struct uade_write_audio *w, const int output[4],
			    const unsigned long tdelta);
void uade_write_audio_write_left_right(
	struct uade_write_audio *w, const int left, const int right);
void uade_write_audio_set_state(struct uade_write_audio *w,
				const int channel,
				const enum PaulaEventType event_type,
				const uint16_t value);
void uade_write_audio_close(struct uade_write_audio *w);

#endif
