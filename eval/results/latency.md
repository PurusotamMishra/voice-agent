# Latency report

## tts_mode = sentence

| Stage | p50 ms | p95 ms | n |
|---|---|---|---|
| stt | 605 | 644 | 2 |
| nlu | 703 | 1132 | 8 |
| search | 4 | 41 | 8 |
| rank | 0 | 0 | 8 |
| compose | 1426 | 8731 | 8 |
| pipeline | 2673 | 9185 | 8 |
| first_audio_ready | 3431 | 9465 | 8 |
| tts | 1860 | 2313 | 8 |
| server_total | 5192 | 10170 | 8 |

## tts_mode = whole

| Stage | p50 ms | p95 ms | n |
|---|---|---|---|
| nlu | 1014 | 1330 | 5 |
| search | 3 | 3 | 5 |
| rank | 0 | 0 | 5 |
| compose | 10999 | 22114 | 5 |
| pipeline | 12363 | 23185 | 5 |
| first_audio_ready | 13490 | 24487 | 5 |
| tts | 1127 | 1429 | 5 |
| server_total | 13494 | 24493 | 5 |

