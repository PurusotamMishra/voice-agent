# Audio eval (STT subset, J1)

| Clip | STT | Synthetic | WER | Transcript | Result |
|---|---|---|---|---|---|
| en-01.wav | groq | True | 0.1 | I need a small truck under 5 Lakaik in Pune | PASS |
| en-02.wav | groq | True | 0.0 | Show me diesel pickups in Mumbai. | PASS |
| en-03-noisy.wav | groq | True | 0.125 | Any CNG vehicle in Delhi below 4 lakhs | PASS |
| hi-01.wav | sarvam | True | 0.111 | Pune mine paanch lakh tak ka chhota truck chahiye. | PASS |
| hi-01.wav | groq | True | 1.667 | पुने माइन पांच लख ता का छोटा ट्रक चहिए. | FAIL: filters {} != {'budget_max': 500000, 'body_type': 'mini_truck', 'city': 'pune'} |
| hi-02.wav | sarvam | True | 0.0 | Mumbai mein diesel pickup dikhao. | FAIL: validator not clean on first try (llm, ['regenerated']) |
| hi-02.wav | groq | True | 1.4 | ممبائی میں ڈیزل پک اپ دکھا ہو. | FAIL: filters {} != {'fuel': 'diesel', 'body_type': 'pickup', 'city': 'mumbai'} |

**4/7 clip x provider runs passed.**
A failure with high WER is an STT miss; low WER plus FAIL is an understanding miss.
