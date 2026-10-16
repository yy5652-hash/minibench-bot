# ShelfCast inference benchmark

- Endpoint model: `Qwen/Qwen3-30B-A3B-Instruct-2507`
- Samples per forecast: 5; GPU price used for cost: $2.99/hour
- Generated 2026-10-16T05:35:37+00:00

| Concurrent forecasts | Forecasts/min | Output tok/s | p50 latency | p95 latency | $ per 1,000 forecasts | Parsed |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 19 | 428 | 3.47s | 4.08s | $2.586 | 100.0% |
| 8 | 82 | 1,780 | 5.19s | 6.44s | $0.606 | 100.0% |
| 32 | 198 | 3,597 | 7.24s | 12.91s | $0.252 | 100.0% |
| 64 | 242 | 4,754 | 13.71s | 20.43s | $0.206 | 100.0% |
| 128 | 256 | 4,722 | 24.11s | 47.78s | $0.194 | 100.0% |

## GPU

```
$ amd-smi static --asic --vram
GPU: 0
    ASIC:
        MARKET_NAME: AMD Instinct MI300X VF
        VENDOR_ID: 0x1002
        VENDOR_NAME: Advanced Micro Devices Inc. [AMD/ATI]
        SUBVENDOR_ID: 0x1002
        DEVICE_ID: 0x74b5
        SUBSYSTEM_ID: 0x74a1
        REV_ID: 0x00
        ASIC_SERIAL: 0x858A4298FF49744C
        OAM_ID: 6
        NUM_COMPUTE_UNITS: 304
        TARGET_GRAPHICS_VERSION: gfx942
    VRAM:
        TYPE: HBM
        VENDOR: MICRON
        SIZE: 196288 MB
        BIT_WIDTH: 2048
        MAX_BANDWIDTH: 5325 GB/s
```
