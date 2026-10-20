# Latency report

## tts_mode = sentence

| Stage | p50 ms | p95 ms | n |
|---|---|---|---|
| stt | 1242 | 2358 | 13 |
| nlu | 815 | 2195 | 15 |
| search | 3 | 41 | 13 |
| rank | 0 | 0 | 12 |
| relax | 2 | 2 | 1 |
| compose | 834 | 8731 | 15 |
| pipeline | 1828 | 9185 | 17 |
| first_audio_ready | 2859 | 9465 | 19 |
| tts | 1444 | 2313 | 19 |
| server_total | 3915 | 10170 | 19 |
| speech_end_to_first_audio | 3282 | 4586 | 7 |

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

